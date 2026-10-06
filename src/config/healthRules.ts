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

  /** Daily check-in rules (self-reported, 0-10 sliders). */
  checkin: {
    /** Rules look at the latest N check-ins. */
    window: number
    /** Pain (0-10): sustained = at least minSustained of the window at/above the level. */
    pain: LevelThresholds
    minSustained: number
    /** A single report at/above this raises WATCH immediately (acute report). */
    acutePain: number
    /** Knee pain at/above this, in any of the latest check-ins, counts for the combined rule. */
    kneePainMin: number
    /** Combined rule: asymmetry must have risen at least this many degrees above baseline. */
    combinedAsymmetryDeg: number
    /** Recovery: sleep at/below AND fatigue at/above these, sustained. */
    sleepLow: number
    fatigueHigh: number
    /** Stress at/above this, sustained. */
    stressHigh: number
  }
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

  checkin: {
    window: 3,
    pain: { watch: 4, act: 7 },
    minSustained: 2,
    acutePain: 7,
    kneePainMin: 3,
    combinedAsymmetryDeg: 2,
    sleepLow: 4,
    fatigueHigh: 7,
    stressHigh: 8,
  },
}
