import { DEFAULT_STEP, stepQueue, type QueueItem } from '../engine/downlinkQueue'
import { db as defaultDb, type OrbitDB } from '../db/db'
import { parseMessage, type ChannelLike } from './protocol'

export interface SenderConfig {
  /** True while the comms window is open. */
  windowOpen: boolean
  /** Simulated one-way latency, in real milliseconds (the UI uses 1 simulated minute = 1 second). */
  latencyMs: number
  /** Optional override of the extra wait before a missing ACK triggers a retry. */
  retryMarginMs?: number
}

export interface SenderOptions {
  channel: ChannelLike
  getConfig: () => SenderConfig
  db?: OrbitDB
  now?: () => number
}

/** Earth is considered "online" if its heartbeat was seen this recently. */
export const EARTH_ONLINE_WINDOW_MS = 10_000

/**
 * The astronaut side of the downlink. Every tick it asks the pure queue state machine what to
 * do, applies the changes to the persisted queue (in one transaction, so two astronaut tabs
 * cannot both claim a packet) and broadcasts whatever is due. Earth's ACK marks a packet done.
 */
export class DownlinkSender {
  private readonly db: OrbitDB
  private readonly channel: ChannelLike
  private readonly now: () => number
  private readonly getConfig: () => SenderConfig
  private busy = false
  private timer: ReturnType<typeof setInterval> | null = null
  private earthLastSeen = 0

  constructor(o: SenderOptions) {
    this.db = o.db ?? defaultDb
    this.channel = o.channel
    this.now = o.now ?? Date.now
    this.getConfig = o.getConfig
    this.channel.addEventListener('message', this.onMessage)
  }

  get earthOnline(): boolean {
    return this.now() - this.earthLastSeen < EARTH_ONLINE_WINDOW_MS
  }

  start(intervalMs = 500): void {
    if (this.timer) return
    this.timer = setInterval(() => void this.tick().catch((e) => console.error('Downlink tick failed', e)), intervalMs)
    void this.tick().catch((e) => console.error('Downlink tick failed', e))
  }

  stop(): void {
    if (this.timer) clearInterval(this.timer)
    this.timer = null
    this.channel.removeEventListener('message', this.onMessage)
  }

  /** One scheduling step. Safe to call at any time; overlapping calls are ignored. */
  async tick(): Promise<void> {
    if (this.busy) return
    this.busy = true
    try {
      const cfg = this.getConfig()
      const now = this.now()
      const toSend: { payload: string }[] = []
      await this.db.transaction('rw', this.db.downlinkQueue, async () => {
        const rows = await this.db.downlinkQueue.toArray()
        const step = stepQueue(rows as QueueItem[], {
          now, windowOpen: cfg.windowOpen, latencyMs: cfg.latencyMs,
          retryMarginMs: cfg.retryMarginMs ?? DEFAULT_STEP.retryMarginMs, maxAttempts: DEFAULT_STEP.maxAttempts,
        })
        for (const u of step.updates) await this.db.downlinkQueue.update(u.id, u.patch)
        for (const id of step.transmit) {
          const row = rows.find((r) => r.id === id)
          if (row) toSend.push({ payload: row.payload })
        }
      })
      // Broadcast only after the transaction committed, so state and radio never disagree.
      for (const { payload } of toSend) {
        this.channel.postMessage({ type: 'packet', packet: JSON.parse(payload), latencyMs: cfg.latencyMs })
      }
    } finally {
      this.busy = false
    }
  }

  private readonly onMessage = (e: MessageEvent): void => {
    const m = parseMessage(e.data)
    if (!m) return
    if (m.type === 'earth-online') {
      this.earthLastSeen = this.now()
      return
    }
    if (m.type === 'ack') {
      // In a blackout the return signal is lost too; the packet will simply be re-sent (and de-duplicated) later.
      if (!this.getConfig().windowOpen) return
      void this.db
        .transaction('rw', this.db.downlinkQueue, async () => {
          const row = await this.db.downlinkQueue.get(m.id)
          if (row && row.status !== 'acked') await this.db.downlinkQueue.update(m.id, { status: 'acked', ackedAt: this.now() })
        })
        .catch((err) => console.error('Could not record ACK', err))
    }
  }
}
