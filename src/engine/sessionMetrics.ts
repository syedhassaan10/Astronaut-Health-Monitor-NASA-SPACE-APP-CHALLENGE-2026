import { HEALTH_RULES, type HealthRulesConfig } from '../config/healthRules'
import type { SessionMetrics, SessionRecord } from './healthTypes'

export function median(xs: number[]): number {
  if (xs.length === 0) return NaN
  const s = [...xs].sort((a, b) => a - b)
  const m = Math.floor(s.length / 2)
  return s.length % 2 ? (s[m] as number) : ((s[m - 1] as number) + (s[m] as number)) / 2
}

export function mean(xs: number[]): number {
  return xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : NaN
}

/** Sample standard deviation (n − 1); 0 for fewer than two values. */
export function stdDev(xs: number[]): number {
  if (xs.length < 2) return 0
  const m = mean(xs)
  return Math.sqrt(xs.reduce((a, b) => a + (b - m) ** 2, 0) / (xs.length - 1))
}

/**
 * Summarise one session. Low-confidence reps are dropped first, so they can never
 * influence a baseline or a rule. A session is `usable` only with at least
 * `minValidReps` valid reps (guard K) and a mean confidence above the threshold.
 */
export function summarizeSession(rec: SessionRecord, cfg: HealthRulesConfig = HEALTH_RULES): SessionMetrics {
  const valid = rec.reps.filter((r) => r.confidence >= cfg.minConfidence)
  const col = (f: (r: (typeof valid)[number]) => number) => valid.map(f)
  const meanConfidence = mean(rec.reps.map((r) => r.confidence))
  return {
    id: rec.id,
    day: rec.day,
    gravityG: rec.gravityG,
    prescribedReps: rec.prescribedReps,
    completedReps: rec.reps.length,
    validReps: valid.length,
    depthDeg: median(col((r) => r.minKneeAngle)),
    concentricS: median(col((r) => r.concentricS)),
    eccentricS: median(col((r) => r.eccentricS)),
    asymmetryDeg: mean(col((r) => r.asymmetryDeg)),
    variabilityDeg: stdDev(col((r) => r.minKneeAngle)),
    meanConfidence,
    usable: valid.length >= cfg.minValidReps && meanConfidence >= cfg.minConfidence,
  }
}

/** Least-squares slope of value against day (units per mission day); 0 if undefined. */
export function slopePerDay(points: { day: number; value: number }[]): number {
  if (points.length < 2) return 0
  const mx = mean(points.map((p) => p.day))
  const my = mean(points.map((p) => p.value))
  let num = 0
  let den = 0
  for (const p of points) {
    num += (p.day - mx) * (p.value - my)
    den += (p.day - mx) ** 2
  }
  return den === 0 ? 0 : num / den
}
