import { earthDb, storePacket, type EarthDB } from '../db/earthDb'
import { parseMessage, type ChannelLike } from './protocol'

export interface ReceiverOptions {
  channel: ChannelLike
  db?: EarthDB
  /** Called after every accepted packet (also for duplicates, with duplicate = true). */
  onPacket?: (id: string, duplicate: boolean) => void
  /** Heartbeat interval so astronaut tabs can show "Earth online". */
  heartbeatMs?: number
}

/**
 * The Earth side. Stores each delivered packet in Earth's own database (idempotent by id)
 * and sends an ACK after the simulated return-leg delay. A duplicate delivery is stored
 * zero times but still ACKed, so a sender whose first ACK was lost can finish.
 */
export class EarthReceiver {
  private readonly db: EarthDB
  private readonly channel: ChannelLike
  private readonly onPacket?: (id: string, duplicate: boolean) => void
  private readonly heartbeatMs: number
  private beat: ReturnType<typeof setInterval> | null = null
  private readonly pendingAcks = new Set<ReturnType<typeof setTimeout>>()
  private stopped = true

  constructor(o: ReceiverOptions) {
    this.db = o.db ?? earthDb
    this.channel = o.channel
    this.onPacket = o.onPacket
    this.heartbeatMs = o.heartbeatMs ?? 4000
  }

  start(): void {
    this.stopped = false
    this.channel.addEventListener('message', this.onMessage)
    this.announce()
    this.beat = setInterval(() => this.announce(), this.heartbeatMs)
  }

  stop(): void {
    this.stopped = true
    this.channel.removeEventListener('message', this.onMessage)
    if (this.beat) clearInterval(this.beat)
    this.beat = null
    // Pending ACKs are dropped: a closed Earth tab sends nothing, and the sender will retry.
    for (const t of this.pendingAcks) clearTimeout(t)
    this.pendingAcks.clear()
  }

  announce(): void {
    this.channel.postMessage({ type: 'earth-online' })
  }

  private readonly onMessage = (e: MessageEvent): void => {
    const m = parseMessage(e.data)
    if (m?.type !== 'packet') return
    void this.receive(m.packet, m.latencyMs).catch((err) => console.error('Could not store packet', err))
  }

  async receive(packet: Parameters<typeof storePacket>[0], latencyMs: number): Promise<void> {
    const { duplicate } = await storePacket(packet, 'link', this.db)
    this.onPacket?.(packet.id, duplicate)
    // If the Earth tab was closed while the packet was being stored, there is nobody to send the ACK.
    if (this.stopped) return
    const t = setTimeout(() => {
      this.pendingAcks.delete(t)
      if (!this.stopped) this.channel.postMessage({ type: 'ack', id: packet.id })
    }, latencyMs) // the ACK travels back over the same simulated delay
    this.pendingAcks.add(t)
  }
}
