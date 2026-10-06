import type { ExerciseId } from './gravityEngine'

// Knee-angle state machine: top → bottom → top, with hysteresis between the
// "leave top" and "back at top" thresholds so jitter around one value cannot
// create phantom reps. All thresholds are demonstration values.

export interface RepConfig {
  /** Knee angle at/above which the body counts as "at the top" (extended). */
  topDeg: number
  /** Knee angle below which a descent has started (hysteresis gap below topDeg). */
  descendDeg: number
  /** Must go below this for the rep to count (depth gate). */
  bottomDeg: number
  /** Target depth for form feedback (green when at or below). */
  depthTargetDeg: number
  /** Minimum mean landmark confidence for a rep to be trusted. */
  minConfidence: number
}

export const REP_CONFIGS: Partial<Record<ExerciseId, RepConfig>> = {
  squat: { topDeg: 160, descendDeg: 150, bottomDeg: 120, depthTargetDeg: 100, minConfidence: 0.6 },
  deadlift: { topDeg: 165, descendDeg: 155, bottomDeg: 145, depthTargetDeg: 130, minConfidence: 0.6 },
}

export interface Sample {
  tMs: number
  knee: number
  /** |left knee − right knee| in degrees. */
  asymmetryDeg: number
  /** Mean landmark confidence 0..1 for this frame. */
  confidence: number
}

export interface RepMetrics {
  repNo: number
  startMs: number
  endMs: number
  minKneeAngle: number
  eccentricS: number
  concentricS: number
  /** Time spent within the bottom band (pause at depth), seconds. */
  holdS: number
  asymmetryDeg: number
  confidence: number
}

export type RepResult =
  | { kind: 'rep'; rep: RepMetrics }
  | { kind: 'unreliable'; rep: RepMetrics }
  | { kind: 'partial' }

type Phase = 'idle' | 'top' | 'moving'

/** Time at which the line prev→cur crosses `level` (linear interpolation). */
function crossTime(p: Sample, c: Sample, level: number): number {
  const d = c.knee - p.knee
  if (Math.abs(d) < 1e-9) return c.tMs
  const f = Math.min(1, Math.max(0, (level - p.knee) / d))
  return p.tMs + f * (c.tMs - p.tMs)
}

export class RepDetector {
  private phase: Phase = 'idle'
  private prev: Sample | null = null
  private repNo = 0
  private descentStartMs = 0
  private buf: Sample[] = []
  private reachedBottom = false
  private lastAtTop: Sample | null = null
  private firstBelowTop: Sample | null = null
  private lastBelowTop: Sample | null = null
  private sumConf = 0
  private sumAsym = 0
  private n = 0

  /** Gap (ms) between samples above which tracking is considered lost. */
  static readonly MAX_GAP_MS = 1500
  /** Samples within this many degrees of the minimum count as "at the bottom". */
  static readonly BOTTOM_BAND_DEG = 4

  constructor(private cfg: RepConfig) {}

  get currentPhase(): Phase {
    return this.phase
  }

  setConfig(cfg: RepConfig): void {
    this.cfg = cfg
    this.reset()
  }

  reset(): void {
    this.phase = 'idle'
    this.prev = null
    this.lastAtTop = this.firstBelowTop = this.lastBelowTop = null
  }

  /**
   * Feed one sample; returns a result when a rep (or partial/unreliable rep) completes.
   * Eccentric/concentric durations are measured between crossings of `topDeg`
   * (interpolated), so they describe the full excursion and are repeatable.
   */
  push(s: Sample): RepResult | null {
    const c = this.cfg
    const prev = this.prev
    this.prev = s
    if (prev && s.tMs - prev.tMs > RepDetector.MAX_GAP_MS) {
      this.phase = 'idle' // person left the frame / tracking lost
    }

    if (this.phase === 'idle') {
      if (s.knee >= c.topDeg) {
        this.phase = 'top'
        this.lastAtTop = s
        this.firstBelowTop = null
      }
      return null
    }

    if (this.phase === 'top') {
      if (s.knee >= c.topDeg) {
        this.lastAtTop = s
        this.firstBelowTop = null
      } else if (!this.firstBelowTop) {
        this.firstBelowTop = s
      }
      if (s.knee < c.descendDeg && prev) {
        this.phase = 'moving'
        this.descentStartMs =
          this.lastAtTop && this.firstBelowTop
            ? crossTime(this.lastAtTop, this.firstBelowTop, c.topDeg)
            : crossTime(prev, s, c.descendDeg)
        this.buf = [s]
        this.reachedBottom = s.knee < c.bottomDeg
        this.lastBelowTop = s
        this.sumConf = s.confidence
        this.sumAsym = s.asymmetryDeg
        this.n = 1
      }
      return null
    }

    // phase === 'moving'
    this.sumConf += s.confidence
    this.sumAsym += s.asymmetryDeg
    this.n += 1
    this.buf.push(s)
    if (s.knee < c.bottomDeg) this.reachedBottom = true

    if (s.knee < c.topDeg) {
      this.lastBelowTop = s
      return null
    }

    // Back at the top: the rep is complete.
    this.phase = 'top'
    this.lastAtTop = s
    this.firstBelowTop = null
    if (!this.reachedBottom) return { kind: 'partial' }
    const endMs = this.lastBelowTop ? crossTime(this.lastBelowTop, s, c.topDeg) : s.tMs
    // Bottom = band within BOTTOM_BAND_DEG of the minimum. A noisy plateau makes the
    // single minimum sample arbitrary, so the eccentric phase ends when the band is
    // first entered and the concentric phase starts when it is last left.
    const minKnee = Math.min(...this.buf.map((b) => b.knee))
    const inBand = this.buf.filter((b) => b.knee <= minKnee + RepDetector.BOTTOM_BAND_DEG)
    const bandStartMs = inBand[0]?.tMs ?? s.tMs
    const bandEndMs = inBand[inBand.length - 1]?.tMs ?? s.tMs
    const rep: RepMetrics = {
      repNo: ++this.repNo,
      startMs: this.descentStartMs,
      endMs,
      minKneeAngle: minKnee,
      eccentricS: Math.max(0, (bandStartMs - this.descentStartMs) / 1000),
      concentricS: Math.max(0, (endMs - bandEndMs) / 1000),
      holdS: Math.max(0, (bandEndMs - bandStartMs) / 1000),
      asymmetryDeg: this.sumAsym / this.n,
      confidence: this.sumConf / this.n,
    }
    return { kind: rep.confidence >= c.minConfidence ? 'rep' : 'unreliable', rep }
  }
}
