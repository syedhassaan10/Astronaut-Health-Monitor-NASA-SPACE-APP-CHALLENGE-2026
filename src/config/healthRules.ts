// All thresholds are DEMONSTRATION values, not clinically validated.
// They are deliberately in one place so reviewers can read and change them.

export interface LevelThresholds {
  /** Deterioration at or above this raises WATCH. */
  watch: number
  /** Deterioration at or above this raises ACT. */
  act: number
}

export interface HealthRulesConfig {
  /** Baseline = median of the first N usable sessions. */
  baselineSessions: number
  /** K: a session needs at least this many valid reps to be usable. */
  minValidReps: number
  /** Reps (and sessions) below this mean confidence are never used. */
  minConfidence: number
  /** Rules compare the median of up to this many latest usable sessions with the baseline. */
  recentSessions: number
  /** Need at least this many usable sessions after the baseline before any kinematic rule fires. */
  minRecentSessions: number
  /** Sessions at a gravity further than this (in g) from the baseline's are not comparable. */
  gravityTolerance: number

  /** Depth decline: knee angle at the bottom is shallower than baseline by this many degrees. */
  depth: LevelThresholds
  /** Concentric slowing (power proxy): % longer lifting phase than baseline. */
  concentric: LevelThresholds
  /** Rising left/right asymmetry: degrees above baseline. */
  asymmetry: LevelThresholds
  /** Rising rep-to-rep variability: degrees of SD above baseline. */
  variability: LevelThresholds
  /** Adherence: completed ÷ prescribed volume. WATCH/ACT when the ratio drops BELOW these. */
  adherence: LevelThresholds & { windowDays: number }

  /** This many concurrent WATCH-level rules escalate the exercise to ACT. */
  escalateWatchCount: number
}

export const HEALTH_RULES: HealthRulesConfig = {
  baselineSessions: 3,
  minValidReps: 5,
  minConfidence: 0.6,
  recentSessions: 3,
  minRecentSessions: 2,
  gravityTolerance: 0.1,

  depth: { watch: 8, act: 16 },
  concentric: { watch: 15, act: 30 },
  asymmetry: { watch: 4, act: 8 },
  variability: { watch: 3, act: 6 },
  adherence: { watch: 0.8, act: 0.6, windowDays: 7 },

  escalateWatchCount: 3,
}
