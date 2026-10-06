import type { RepConfig, RepMetrics } from './repDetector'

export type Level = 'green' | 'amber' | 'red'

export interface FormTargets {
  depthDeg: number
  /** Eccentric / concentric targets in seconds (from the gravity engine). */
  eccentricS: number
  concentricS: number
}

export interface FormAssessment {
  depth: Level
  tempo: Level
  asymmetry: Level
  overall: Level
  /** 0..100 simplified form score. */
  score: number
  flags: string[]
}

const RANK: Record<Level, number> = { green: 0, amber: 1, red: 2 }
export const worst = (...l: Level[]): Level => l.reduce((a, b) => (RANK[b] > RANK[a] ? b : a), 'green' as Level)

/** Depth: green at/below target (+5° tolerance), amber within +20°, else red. */
export function depthLevel(minKnee: number, targetDeg: number): Level {
  if (minKnee <= targetDeg + 5) return 'green'
  return minKnee <= targetDeg + 20 ? 'amber' : 'red'
}

/** Tempo: relative deviation |actual − target| / target; ≤25% green, ≤50% amber, else red. */
export function tempoLevel(actualS: number, targetS: number): Level {
  if (targetS <= 0) return 'green'
  const dev = Math.abs(actualS - targetS) / targetS
  return dev <= 0.25 ? 'green' : dev <= 0.5 ? 'amber' : 'red'
}

/** Left/right knee-angle asymmetry: <5° green, <10° amber, else red. */
export function asymmetryLevel(deg: number): Level {
  return deg < 5 ? 'green' : deg < 10 ? 'amber' : 'red'
}

export function targetsFor(cfg: RepConfig, tempo: { eccentricS: number; concentricS: number }): FormTargets {
  return { depthDeg: cfg.depthTargetDeg, eccentricS: tempo.eccentricS, concentricS: tempo.concentricS }
}

export function assessRep(m: RepMetrics, t: FormTargets): FormAssessment {
  const depth = depthLevel(m.minKneeAngle, t.depthDeg)
  const ecc = tempoLevel(m.eccentricS, t.eccentricS)
  const con = tempoLevel(m.concentricS, t.concentricS)
  const tempo = worst(ecc, con)
  const asymmetry = asymmetryLevel(m.asymmetryDeg)
  const flags: string[] = []
  if (depth !== 'green') flags.push('shallow')
  if (ecc !== 'green') flags.push(m.eccentricS < t.eccentricS ? 'fast-eccentric' : 'slow-eccentric')
  if (con !== 'green') flags.push(m.concentricS < t.concentricS ? 'fast-concentric' : 'slow-concentric')
  if (asymmetry !== 'green') flags.push('asymmetry')
  // Each aspect costs 10 (amber) or 30 (red) points.
  const penalty = (l: Level) => (l === 'red' ? 30 : l === 'amber' ? 10 : 0)
  const score = Math.max(0, 100 - penalty(depth) - penalty(tempo) - penalty(asymmetry))
  return { depth, tempo, asymmetry, overall: worst(depth, tempo, asymmetry), score, flags }
}
