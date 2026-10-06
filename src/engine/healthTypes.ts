import type { ExerciseId } from './gravityEngine'

/** One counted rep as stored in the logbook (Phase 6 persists these). */
export interface RepSample {
  minKneeAngle: number
  eccentricS: number
  concentricS: number
  asymmetryDeg: number
  /** Mean landmark confidence 0..1. */
  confidence: number
}

/** One prescribed training session. A skipped session has reps = []. */
export interface SessionRecord {
  id: string
  crewId: string
  exercise: ExerciseId
  /** Mission day (integer), used as the time axis. */
  day: number
  gravityG: number
  prescribedReps: number
  reps: RepSample[]
}

/** Per-session summary statistics (all robust: medians, not means, where possible). */
export interface SessionMetrics {
  id: string
  day: number
  gravityG: number
  prescribedReps: number
  /** Reps counted at all (any confidence). */
  completedReps: number
  /** Reps above the confidence threshold. */
  validReps: number
  /** Median of the minimum knee angle (deg). Higher = shallower squat. */
  depthDeg: number
  concentricS: number
  eccentricS: number
  /** Mean |left − right| knee angle (deg). */
  asymmetryDeg: number
  /** Standard deviation of the minimum knee angle across reps (deg). */
  variabilityDeg: number
  meanConfidence: number
  /** True when this session is trustworthy enough to feed baselines and rules. */
  usable: boolean
}

export type Status = 'NOMINAL' | 'WATCH' | 'ACT'
export type RuleId =
  | 'depth' | 'concentric' | 'asymmetry' | 'variability' | 'adherence' | 'escalation'
  // Daily check-in rules (Phase 5)
  | 'pain' | 'recovery' | 'stress' | 'pain-asymmetry'

export type BodyLocation = 'knee' | 'hip' | 'ankle-foot' | 'lower-back' | 'upper-back-neck' | 'shoulder' | 'other'

/** Daily 30-second self-check. All sliders are 0-10. One per crew member per mission day. */
export interface CheckIn {
  id: string
  crewId: string
  day: number
  /** 10 = slept very well. */
  sleep: number
  /** 10 = exhausted. */
  fatigue: number
  /** 0 = no pain, 10 = worst imaginable. */
  pain: number
  /** Where it hurts; null when pain is 0. */
  painLocation: BodyLocation | null
  /** 10 = very stressed / low mood. */
  stress: number
}

export interface Baseline {
  depthDeg: number
  concentricS: number
  asymmetryDeg: number
  variabilityDeg: number
  gravityG: number
  /** Mission days of the sessions the baseline was built from. */
  days: number[]
}

export interface SeriesPoint {
  day: number
  value: number
}

/** The three-part alert: what changed, why it matters, what to do. */
export interface Alert {
  id: string
  crewId: string
  /** Null for crew-level (check-in) alerts that do not belong to one exercise. */
  exercise: ExerciseId | null
  rule: RuleId
  level: Exclude<Status, 'NOMINAL'>
  title: string
  what: {
    metric: string
    unit: string
    baseline: number | null
    now: number
    /** Signed change (now − baseline), or the shortfall for adherence. */
    delta: number
    summary: string
    series: SeriesPoint[]
  }
  why: { text: string; sourceId: string }
  actions: string[]
  /** Optional context from other signals, e.g. "recent check-ins report high fatigue". */
  context?: string[]
  /** Latest mission day contributing to the alert. */
  day: number
}

export interface ExerciseAssessment {
  crewId: string
  exercise: ExerciseId
  status: Status
  baseline: Baseline | null
  usableSessions: number
  alerts: Alert[]
  /** Change vs baseline for each metric (null until a comparable baseline exists). */
  asymmetrySeries: SeriesPoint[]
  deltas: { depthDeg: number; concentricPct: number; asymmetryDeg: number; variabilityDeg: number } | null
  /** Plain-language notes, e.g. "Building baseline (2/3)" or why a comparison was paused. */
  notes: string[]
}

export interface CrewAssessment {
  crewId: string
  status: Status
  exercises: ExerciseAssessment[]
  alerts: Alert[]
}
