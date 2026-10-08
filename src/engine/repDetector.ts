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
  /** Recent samples used to learn this person's own standing (top) angle. */
  private hist: Sample[] = []
  /** Effective thresholds for the current rep; frozen while a rep is in progress. */
  private top: number
  private descend: number

  /** Gap (ms) between samples above which tracking is considered lost. */
  static readonly MAX_GAP_MS = 1500
  /** Samples within this many degrees of the minimum count as "at the bottom". */
  static readonly BOTTOM_BAND_DEG = 4
  /** Window (ms) over which the person's standing angle is learned. */
  static readonly CALIB_WINDOW_MS = 8000
  /** Need at least this much history before the configured top is adapted. */
  static readonly CALIB_MIN_MS = 1500
  /** The learned top sits this many degrees below the person's typical standing angle. */
  static readonly TOP_MARGIN_DEG = 4
  /** Never learn a top lower than bottomDeg + this (a deep-squat hold must not count as "standing"). */
  static readonly MIN_TOP_ABOVE_BOTTOM_DEG = 25

  constructor(private cfg: RepConfig) {
    this.top = cfg.topDeg
    this.descend = cfg.descendDeg
  }

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
    this.hist = []
    this.top = this.cfg.topDeg
    this.descend = this.cfg.descendDeg
  }

  /**
   * Person-relative thresholds. Real people rarely straighten to a textbook 160-180°
   * (camera angle and landmark bias also shift it), so "top" is learned as the 90th
   * percentile of the knee angles seen in the last few seconds minus a small margin,
   * never above the configured topDeg nor below bottomDeg + MIN_TOP_ABOVE_BOTTOM_DEG.
   * The hysteresis gap (topDeg - descendDeg) is preserved.
   */
  private recalibrate(s: Sample): void {
    const c = this.cfg
    this.hist.push(s)
    while (this.hist.length > 1 && s.tMs - (this.hist[0]?.tMs ?? s.tMs) > RepDetector.CALIB_WINDOW_MS) this.hist.shift()
    const first = this.hist[0]
    if (!first || s.tMs - first.tMs < RepDetector.CALIB_MIN_MS) return
    const sorted = this.hist.map((h) => h.knee).sort((a, b) => a - b)
    const ref = sorted[Math.min(sorted.length - 1, Math.floor(0.9 * sorted.length))] ?? c.topDeg
    const floor = c.bottomDeg + RepDetector.MIN_TOP_ABOVE_BOTTOM_DEG
    this.top = Math.min(c.topDeg, Math.max(floor, ref - RepDetector.TOP_MARGIN_DEG))
    this.descend = this.top - (c.topDeg - c.descendDeg)
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
      this.hist = []
    }
    if (this.phase !== 'moving') this.recalibrate(s) // thresholds stay frozen during a rep

    if (this.phase === 'idle') {
      if (s.knee >= this.top) {
        this.phase = 'top'
        this.lastAtTop = s
        this.firstBelowTop = null
      }
      return null
    }

    if (this.phase === 'top') {
      if (s.knee >= this.top) {
        this.lastAtTop = s
        this.firstBelowTop = null
      } else if (!this.firstBelowTop) {
        this.firstBelowTop = s
      }
      if (s.knee < this.descend && prev) {
        this.phase = 'moving'
        this.descentStartMs =
          this.lastAtTop && this.firstBelowTop
            ? crossTime(this.lastAtTop, this.firstBelowTop, this.top)
            : crossTime(prev, s, this.descend)
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

    if (s.knee < this.top) {
      this.lastBelowTop = s
      return null
    }

    // Back at the top: the rep is complete.
    this.phase = 'top'
    this.lastAtTop = s
    this.firstBelowTop = null
    if (!this.reachedBottom) return { kind: 'partial' }
    const endMs = this.lastBelowTop ? crossTime(this.lastBelowTop, s, this.top) : s.tMs
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
