import { describe, expect, it } from 'vitest'
import { AdaptiveSampler, DEFAULT_SAMPLER, type SamplingMode } from './adaptiveSampler'
import { RepDetector, REP_CONFIGS, type RepMetrics } from './repDetector'
import { asymmetryLevel, assessRep, depthLevel, tempoLevel } from './formFeedback'
import { tempoForG } from './gravityEngine'

const FPS = 30
/** Deterministic jitter so tests are repeatable (LCG), ±0.8°. */
function rng(seed = 7) {
  let s = seed
  return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32 - 0.5) * 1.6
}

/** Knee angle at time t (s) for N reps with the given tempo, rest between reps. */
function kneeAt(t: number, reps: number, ecc: number, hold: number, con: number, rest: number, bottom = 95): number {
  const top = 172
  const period = ecc + hold + con + rest
  const lead = 1
  const u = t - lead
  if (u < 0 || u >= reps * period) return top
  const x = u % period
  if (x < ecc) return top - ((top - bottom) * (1 - Math.cos((Math.PI * x) / ecc))) / 2
  if (x < ecc + hold) return bottom
  if (x < ecc + hold + con) return bottom + ((top - bottom) * (1 - Math.cos((Math.PI * (x - ecc - hold)) / con))) / 2
  return top
}

function simulate(mode: SamplingMode, reps: number, ecc: number, hold: number, con: number, rest: number, stride = DEFAULT_SAMPLER.baseStride) {
  const sampler = new AdaptiveSampler(mode, { ...DEFAULT_SAMPLER, baseStride: stride })
  const det = new RepDetector(REP_CONFIGS.squat!)
  const jitter = rng()
  const found: RepMetrics[] = []
  const total = 1 + reps * (ecc + hold + con + rest) + 1
  let frames = 0
  let inferences = 0
  for (let f = 0; f / FPS < total; f++) {
    frames++
    const tMs = (f / FPS) * 1000
    if (!sampler.shouldRun(tMs)) continue
    inferences++
    const knee = kneeAt(f / FPS, reps, ecc, hold, con, rest) + jitter()
    sampler.onResult(knee, tMs)
    const r = det.push({ tMs, knee, asymmetryDeg: 2, confidence: 0.9 })
    if (r?.kind === 'rep') found.push(r.rep)
  }
  return { frames, inferences, found }
}

describe('AdaptiveSampler', () => {
  it('full mode runs on every frame', () => {
    const s = new AdaptiveSampler('full')
    for (let i = 0; i < 20; i++) expect(s.shouldRun(i * 33)).toBe(true)
  })

  it('adaptive mode runs on every 7th frame when nothing moves', () => {
    const s = new AdaptiveSampler('adaptive')
    let runs = 0
    for (let i = 0; i < 100; i++) if (s.shouldRun(i * 33)) runs++
    expect(runs).toBe(14)
  })

  it('bursts to every frame for ~300 ms after velocity falls to ~0', () => {
    const s = new AdaptiveSampler('adaptive')
    s.onResult(150, 0)
    s.onResult(120, 166) // fast: ~180 °/s
    s.onResult(119.5, 333) // nearly stopped → burst until 633 ms
    expect(s.shouldRun(366)).toBe(true)
    expect(s.shouldRun(400)).toBe(true)
    expect(s.shouldRun(600)).toBe(true)
    // after the burst we fall back to the base stride
    const after = [700, 733, 766, 800, 833, 866, 900].map((t) => s.shouldRun(t))
    expect(after.filter(Boolean)).toHaveLength(1)
  })

  it('makes ≥75% fewer inference calls than Full on a realistic set (with similar rep accuracy)', () => {
    // 0 g tempo from the gravity engine: slow, controlled reps; 8 reps with 1 s rest.
    const t = tempoForG(0)
    const full = simulate('full', 8, t.eccentricS, t.holdS, t.concentricS, 1)
    const adap = simulate('adaptive', 8, t.eccentricS, t.holdS, t.concentricS, 1)
    const reduction = 1 - adap.inferences / full.inferences
    console.log(`adaptive reduction (0 g tempo): ${(reduction * 100).toFixed(1)}%`)
    expect(full.found).toHaveLength(8)
    expect(adap.found).toHaveLength(8)
    expect(reduction).toBeGreaterThanOrEqual(0.75)
    // captured bottom and tempo stay close to the Full-mode measurement
    for (let i = 0; i < 8; i++) {
      expect(Math.abs(adap.found[i]!.minKneeAngle - full.found[i]!.minKneeAngle)).toBeLessThan(3)
      expect(Math.abs(adap.found[i]!.eccentricS - full.found[i]!.eccentricS)).toBeLessThan(0.35)
    }
  })

  it('also clears 75% at the faster 1 g and Mars tempos', () => {
    for (const g of [1, 0.38]) {
      const t = tempoForG(g)
      const full = simulate('full', 8, t.eccentricS, t.holdS, t.concentricS, 1)
      const adap = simulate('adaptive', 8, t.eccentricS, t.holdS, t.concentricS, 1)
      expect(1 - adap.inferences / full.inferences).toBeGreaterThanOrEqual(0.75)
      expect(adap.found).toHaveLength(full.found.length)
    }
  })
})

describe('sweep (informational)', () => {
  it('prints reduction by stride and tempo', () => {
    for (const g of [0, 0.38, 1]) for (const stride of [5, 6, 7]) {
      const t = tempoForG(g)
      const full = simulate('full', 8, t.eccentricS, t.holdS, t.concentricS, 1)
      const ad = simulate('adaptive', 8, t.eccentricS, t.holdS, t.concentricS, 1, stride)
      console.log('SWEEP g=' + g + ' stride=' + stride + ' reduction=' + ((1 - ad.inferences / full.inferences) * 100).toFixed(1) + '% reps=' + ad.found.length + '/' + full.found.length)
    }
  })
})

describe('formFeedback', () => {
  it('grades depth, tempo and asymmetry', () => {
    expect(depthLevel(98, 100)).toBe('green')
    expect(depthLevel(115, 100)).toBe('amber')
    expect(depthLevel(130, 100)).toBe('red')
    expect(tempoLevel(2, 2)).toBe('green')
    expect(tempoLevel(2.8, 2)).toBe('amber')
    expect(tempoLevel(1, 2)).toBe('amber')
    expect(tempoLevel(0.5, 2)).toBe('red')
    expect(asymmetryLevel(3)).toBe('green')
    expect(asymmetryLevel(7)).toBe('amber')
    expect(asymmetryLevel(12)).toBe('red')
  })

  it('assessRep combines levels into an overall level and score', () => {
    const rep: RepMetrics = { repNo: 1, startMs: 0, endMs: 3000, minKneeAngle: 130, eccentricS: 2, concentricS: 1, holdS: 0, asymmetryDeg: 12, confidence: 0.9 }
    const a = assessRep(rep, { depthDeg: 100, eccentricS: 2, concentricS: 1 })
    expect(a.depth).toBe('red')
    expect(a.asymmetry).toBe('red')
    expect(a.overall).toBe('red')
    expect(a.score).toBe(40)
    expect(a.flags).toEqual(expect.arrayContaining(['shallow', 'asymmetry']))
  })
})



