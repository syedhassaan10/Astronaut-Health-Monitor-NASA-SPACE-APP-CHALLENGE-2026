// Pure state machine for the downlink queue. No timers, no I/O: given the queue, the comms
// state and the clock, it says what to change and which packets to transmit right now.
//
//   queued ──(window open)──▶ sent(in transit) ──(latency elapsed)──▶ transmitted ──ACK──▶ acked
//      ▲                          │ BLACKOUT before arrival: link lost │ no ACK in time: retry
//      └──────────────────────────┴────────────────────────────────────┘

export type QueueStatus = 'queued' | 'sent' | 'acked'

export interface QueueItem {
  id: string
  createdAt: number
  status: QueueStatus
  /** When this transmission attempt started / when the packet reaches Earth (simulated one-way delay). */
  sentAt: number | null
  deliverAt: number | null
  /** Set once the packet has actually been broadcast to Earth. */
  transmittedAt: number | null
  ackedAt: number | null
  attempts: number
}

export interface StepConfig {
  now: number
  windowOpen: boolean
  /** Simulated one-way latency in (real) milliseconds. */
  latencyMs: number
  /** Extra wait beyond the 2 x latency round trip before a missing ACK triggers a retry. */
  retryMarginMs: number
  maxAttempts: number
}

export const DEFAULT_STEP: Omit<StepConfig, 'now' | 'windowOpen' | 'latencyMs'> = { retryMarginMs: 3000, maxAttempts: 20 }

export interface StepResult {
  updates: { id: string; patch: Partial<QueueItem> }[]
  /** Packets to broadcast to Earth now. */
  transmit: string[]
}

const CLEARED = { sentAt: null, deliverAt: null, transmittedAt: null } as const

/** What to do next for every unacknowledged item. Items are handled oldest first. */
export function stepQueue(items: QueueItem[], cfg: StepConfig): StepResult {
  const updates: StepResult['updates'] = []
  const transmit: string[] = []
  const pending = items.filter((i) => i.status !== 'acked').sort((a, b) => a.createdAt - b.createdAt)

  for (const it of pending) {
    if (!cfg.windowOpen) {
      // BLACKOUT: a packet that has not reached Earth yet is lost in the dark; it goes back to the queue.
      if (it.status === 'sent' && it.transmittedAt === null) {
        updates.push({ id: it.id, patch: { status: 'queued', ...CLEARED } })
      }
      continue
    }

    if (it.status === 'queued') {
      if (it.attempts >= cfg.maxAttempts) continue // gave up: left in the queue for the operator to see
      updates.push({
        id: it.id,
        patch: { status: 'sent', sentAt: cfg.now, deliverAt: cfg.now + cfg.latencyMs, transmittedAt: null, attempts: it.attempts + 1 },
      })
      continue
    }

    // status === 'sent'
    if (it.transmittedAt === null) {
      if (it.deliverAt !== null && cfg.now >= it.deliverAt) {
        transmit.push(it.id)
        updates.push({ id: it.id, patch: { transmittedAt: cfg.now } })
      }
    } else if (cfg.now >= it.transmittedAt + cfg.latencyMs + cfg.retryMarginMs) {
      // Delivered but no ACK came back in time (Earth tab closed, ACK lost in a blackout): send again.
      updates.push({ id: it.id, patch: { status: 'queued', ...CLEARED } })
    }
  }
  return { updates, transmit }
}

/** Status text for the UI. */
export type Phase = 'waiting-for-window' | 'starting' | 'in-transit' | 'awaiting-ack' | 'acked' | 'gave-up'

export function phaseOf(it: QueueItem, windowOpen: boolean, maxAttempts = DEFAULT_STEP.maxAttempts): Phase {
  if (it.status === 'acked') return 'acked'
  if (it.status === 'queued') return it.attempts >= maxAttempts ? 'gave-up' : windowOpen ? 'starting' : 'waiting-for-window'
  return it.transmittedAt === null ? 'in-transit' : 'awaiting-ack'
}
