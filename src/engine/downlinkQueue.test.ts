import { describe, expect, it } from 'vitest'
import { DEFAULT_STEP, phaseOf, stepQueue, type QueueItem, type StepConfig } from './downlinkQueue'

const L = 10_000 // 10 s simulated one-way latency (10 min at 1 min = 1 s)
const item = (id: string, o: Partial<QueueItem> = {}): QueueItem => ({
  id, createdAt: 1000, status: 'queued', sentAt: null, deliverAt: null, transmittedAt: null, ackedAt: null, attempts: 0, ...o,
})
const cfg = (o: Partial<StepConfig> = {}): StepConfig => ({ now: 100_000, windowOpen: true, latencyMs: L, ...DEFAULT_STEP, ...o })
const apply = (i: QueueItem, r: ReturnType<typeof stepQueue>): QueueItem => ({ ...i, ...(r.updates.find((u) => u.id === i.id)?.patch ?? {}) })

describe('BLACKOUT', () => {
  it('leaves queued packets queued, indefinitely', () => {
    let q = item('a')
    for (let t = 0; t < 10; t++) {
      const r = stepQueue([q], cfg({ now: 100_000 + t * 60_000, windowOpen: false }))
      expect(r.updates).toEqual([])
      expect(r.transmit).toEqual([])
      q = apply(q, r)
    }
    expect(q.status).toBe('queued')
    expect(q.attempts).toBe(0)
  })

  it('a packet still in transit when the window closes goes back to the queue (link lost)', () => {
    const inFlight = item('a', { status: 'sent', sentAt: 100_000, deliverAt: 110_000, attempts: 1 })
    const r = stepQueue([inFlight], cfg({ now: 105_000, windowOpen: false }))
    expect(r.transmit).toEqual([])
    expect(apply(inFlight, r)).toMatchObject({ status: 'queued', sentAt: null, deliverAt: null, transmittedAt: null, attempts: 1 })
  })

  it('a packet already delivered (awaiting ACK) is not recalled by a later blackout', () => {
    const delivered = item('a', { status: 'sent', sentAt: 100_000, deliverAt: 110_000, transmittedAt: 110_000, attempts: 1 })
    expect(stepQueue([delivered], cfg({ now: 115_000, windowOpen: false })).updates).toEqual([])
  })
})

describe('WINDOW OPEN', () => {
  it('starts sending a queued packet, but does NOT transmit before the simulated latency has passed', () => {
    const q = item('a')
    const r1 = stepQueue([q], cfg({ now: 100_000 }))
    expect(r1.transmit).toEqual([])
    const sent = apply(q, r1)
    expect(sent).toMatchObject({ status: 'sent', sentAt: 100_000, deliverAt: 110_000, attempts: 1 })
    expect(stepQueue([sent], cfg({ now: 109_999 })).transmit).toEqual([])
  })

  it('transmits exactly when the latency has elapsed, and only once', () => {
    const sent = item('a', { status: 'sent', sentAt: 100_000, deliverAt: 110_000, attempts: 1 })
    const r = stepQueue([sent], cfg({ now: 110_000 }))
    expect(r.transmit).toEqual(['a'])
    const done = apply(sent, r)
    expect(done.transmittedAt).toBe(110_000)
    expect(stepQueue([done], cfg({ now: 111_000 })).transmit).toEqual([]) // no re-broadcast while waiting for the ACK
  })

  it('retries when no ACK arrives within the round trip plus the margin', () => {
    const delivered = item('a', { status: 'sent', sentAt: 100_000, deliverAt: 110_000, transmittedAt: 110_000, attempts: 1 })
    const waitUntil = 110_000 + L + DEFAULT_STEP.retryMarginMs
    expect(stepQueue([delivered], cfg({ now: waitUntil - 1 })).updates).toEqual([])
    const r = stepQueue([delivered], cfg({ now: waitUntil }))
    expect(apply(delivered, r)).toMatchObject({ status: 'queued', transmittedAt: null, attempts: 1 })
    // ...and the next step sends it again with attempts incremented
    const again = apply(apply(delivered, r), stepQueue([apply(delivered, r)], cfg({ now: waitUntil + 100 })))
    expect(again).toMatchObject({ status: 'sent', attempts: 2 })
  })

  it('gives up after maxAttempts and stops resending', () => {
    const stuck = item('a', { attempts: DEFAULT_STEP.maxAttempts })
    expect(stepQueue([stuck], cfg()).updates).toEqual([])
    expect(phaseOf(stuck, true)).toBe('gave-up')
  })

  it('never touches acknowledged packets', () => {
    const done = item('a', { status: 'acked', ackedAt: 5, attempts: 1 })
    expect(stepQueue([done], cfg({ windowOpen: true })).updates).toEqual([])
    expect(stepQueue([done], cfg({ windowOpen: false })).updates).toEqual([])
  })

  it('handles several packets independently, oldest first', () => {
    const items = [item('late', { createdAt: 3000 }), item('early', { createdAt: 1000 }), item('mid', { createdAt: 2000 })]
    const r = stepQueue(items, cfg())
    expect(r.updates.map((u) => u.id)).toEqual(['early', 'mid', 'late'])
  })

  it('a longer latency delays transmission proportionally', () => {
    const q = item('a')
    const s = apply(q, stepQueue([q], cfg({ now: 0, latencyMs: 40_000 })))
    expect(s.deliverAt).toBe(40_000)
    expect(stepQueue([s], cfg({ now: 39_999, latencyMs: 40_000 })).transmit).toEqual([])
    expect(stepQueue([s], cfg({ now: 40_000, latencyMs: 40_000 })).transmit).toEqual(['a'])
  })
})

describe('phaseOf', () => {
  it('describes each stage for the UI', () => {
    expect(phaseOf(item('a'), false)).toBe('waiting-for-window')
    expect(phaseOf(item('a'), true)).toBe('starting')
    expect(phaseOf(item('a', { status: 'sent', deliverAt: 1 }), true)).toBe('in-transit')
    expect(phaseOf(item('a', { status: 'sent', transmittedAt: 1 }), true)).toBe('awaiting-ack')
    expect(phaseOf(item('a', { status: 'acked' }), false)).toBe('acked')
  })
})
