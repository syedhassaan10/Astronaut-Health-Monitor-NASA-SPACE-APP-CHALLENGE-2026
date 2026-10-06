import { describe, expect, it } from 'vitest'
import { RepDetector, REP_CONFIGS, type RepMetrics, type RepResult } from './repDetector'

const cfg = REP_CONFIGS.squat!

/** Build samples for one smooth rep: top → bottom → top (cosine easing). */
function repSamples(t0: number, ecc: number, hold: number, con: number, bottom: number, fps = 30, conf = 0.9, asym = 2) {
  const out: { tMs: number; knee: number; asymmetryDeg: number; confidence: number }[] = []
  const top = 172
  const dt = 1000 / fps
  const total = ecc + hold + con
  for (let t = 0; t <= total + 0.5 / fps; t += 1 / fps) {
    let k: number
    if (t < ecc) k = top - ((top - bottom) * (1 - Math.cos((Math.PI * t) / ecc))) / 2
    else if (t < ecc + hold) k = bottom
    else k = bottom + ((top - bottom) * (1 - Math.cos((Math.PI * (t - ecc - hold)) / con))) / 2
    out.push({ tMs: t0 + t * 1000 + 0 * dt, knee: k, asymmetryDeg: asym, confidence: conf })
  }
  return out
}

function run(samples: ReturnType<typeof repSamples>): RepResult[] {
  const d = new RepDetector(cfg)
  const res: RepResult[] = []
  for (const s of samples) {
    const r = d.push(s)
    if (r) res.push(r)
  }
  return res
}

describe('RepDetector', () => {
  it('counts one rep with correct depth and tempo', () => {
    const lead = [{ tMs: 0, knee: 172, asymmetryDeg: 2, confidence: 0.9 }]
    const res = run([...lead, ...repSamples(500, 2, 0, 1, 95)])
    expect(res).toHaveLength(1)
    const r = res[0]!
    expect(r.kind).toBe('rep')
    const m = (r as { rep: RepMetrics }).rep
    expect(m.repNo).toBe(1)
    expect(m.minKneeAngle).toBeCloseTo(95, 0)
    expect(m.eccentricS).toBeGreaterThan(1.0)
    expect(m.eccentricS).toBeLessThan(2.0)
    expect(m.concentricS).toBeGreaterThan(0.4)
    expect(m.concentricS).toBeLessThan(1.0)
    expect(m.asymmetryDeg).toBeCloseTo(2, 5)
  })

  it('counts several consecutive reps', () => {
    const s = [{ tMs: 0, knee: 172, asymmetryDeg: 2, confidence: 0.9 }]
    let t = 500
    for (let i = 0; i < 5; i++) {
      s.push(...repSamples(t, 2, 0.5, 1, 98))
      t += 4500
    }
    const reps = run(s).filter((r) => r.kind === 'rep')
    expect(reps).toHaveLength(5)
  })

  it('does not count a shallow dip that never reaches the bottom gate', () => {
    const res = run([{ tMs: 0, knee: 172, asymmetryDeg: 2, confidence: 0.9 }, ...repSamples(500, 2, 0, 1, 135)])
    expect(res.filter((r) => r.kind === 'rep')).toHaveLength(0)
    expect(res.some((r) => r.kind === 'partial')).toBe(true)
  })

  it('has hysteresis: jitter around the descend threshold makes no rep', () => {
    const d = new RepDetector(cfg)
    let t = 0
    const out: (RepResult | null)[] = []
    out.push(d.push({ tMs: t, knee: 172, asymmetryDeg: 1, confidence: 0.9 }))
    for (let i = 0; i < 60; i++) {
      t += 33
      out.push(d.push({ tMs: t, knee: 150 + (i % 2 ? 4 : -2), asymmetryDeg: 1, confidence: 0.9 }))
    }
    expect(out.filter((r) => r?.kind === 'rep')).toHaveLength(0)
  })

  it('rejects low-confidence reps as unreliable', () => {
    const res = run([{ tMs: 0, knee: 172, asymmetryDeg: 2, confidence: 0.3 }, ...repSamples(500, 2, 0, 1, 95, 30, 0.3)])
    expect(res.filter((r) => r.kind === 'rep')).toHaveLength(0)
    expect(res.filter((r) => r.kind === 'unreliable')).toHaveLength(1)
  })

  it('resets after a long tracking gap instead of inventing a rep', () => {
    const d = new RepDetector(cfg)
    d.push({ tMs: 0, knee: 172, asymmetryDeg: 1, confidence: 0.9 })
    d.push({ tMs: 33, knee: 140, asymmetryDeg: 1, confidence: 0.9 })
    d.push({ tMs: 66, knee: 100, asymmetryDeg: 1, confidence: 0.9 })
    // 5 s of lost tracking, then the person is standing again.
    expect(d.push({ tMs: 5066, knee: 172, asymmetryDeg: 1, confidence: 0.9 })).toBeNull()
  })

  it('reports asymmetry as the mean left/right difference', () => {
    const res = run([{ tMs: 0, knee: 172, asymmetryDeg: 12, confidence: 0.9 }, ...repSamples(500, 2, 0, 1, 95, 30, 0.9, 12)])
    const m = (res[0] as { rep: RepMetrics }).rep
    expect(m.asymmetryDeg).toBeCloseTo(12, 5)
  })
})

