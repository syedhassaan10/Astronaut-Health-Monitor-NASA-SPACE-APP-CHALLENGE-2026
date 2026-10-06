import { describe, expect, it } from 'vitest'
import { HEALTH_RULES } from '../config/healthRules'
import { adherenceRatio, assessCrew, assessExercise, computeBaseline, levelFor } from './changeDetection'
import type { RepSample, SessionRecord } from './healthTypes'
import { median, slopePerDay, stdDev, summarizeSession } from './sessionMetrics'

interface Opts {
  day: number
  depth?: number
  concentric?: number
  asym?: number
  /** Spread of depth across reps (deg), creates variability. */
  spread?: number
  conf?: number
  nReps?: number
  prescribed?: number
  g?: number
  crewId?: string
  exercise?: 'squat' | 'deadlift'
}

/** Builds a session whose summary equals the requested values (symmetric depth spread). */
function session(o: Opts): SessionRecord {
  const n = o.nReps ?? 8
  const spread = o.spread ?? 2
  const reps: RepSample[] = Array.from({ length: n }, (_, i) => {
    const offset = n === 1 ? 0 : (i / (n - 1) - 0.5) * 2 * spread // -spread..+spread
    return {
      minKneeAngle: (o.depth ?? 95) + offset,
      eccentricS: 2,
      concentricS: o.concentric ?? 1,
      asymmetryDeg: o.asym ?? 2,
      confidence: o.conf ?? 0.9,
    }
  })
  return {
    id: `s${o.day}`, crewId: o.crewId ?? 'c1', exercise: o.exercise ?? 'squat', day: o.day,
    gravityG: o.g ?? 0, prescribedReps: o.prescribed ?? n, reps,
  }
}

/** Three healthy baseline sessions on days 1-3 plus the supplied later ones. */
const withBaseline = (...later: Opts[]): SessionRecord[] =>
  [1, 2, 3].map((d) => session({ day: d })).concat(later.map(session))

const rules = (recs: SessionRecord[]) => assessExercise(recs, 'c1', 'squat')
const ruleLevels = (recs: SessionRecord[]) => Object.fromEntries(rules(recs).alerts.map((a) => [a.rule, a.level]))

describe('statistics helpers', () => {
  it('median, stdDev and slope', () => {
    expect(median([3, 1, 2])).toBe(2)
    expect(median([1, 2, 3, 4])).toBe(2.5)
    expect(median([])).toBeNaN()
    expect(stdDev([2, 4, 4, 4, 5, 5, 7, 9])).toBeCloseTo(2.138, 3)
    expect(stdDev([5])).toBe(0)
    expect(slopePerDay([{ day: 0, value: 1 }, { day: 1, value: 3 }, { day: 2, value: 5 }])).toBeCloseTo(2, 9)
  })
})

describe('levelFor', () => {
  it('maps deterioration to WATCH / ACT with inclusive thresholds', () => {
    const t = { watch: 5, act: 10 }
    expect(levelFor(4.99, t)).toBeNull()
    expect(levelFor(5, t)).toBe('WATCH')
    expect(levelFor(9.99, t)).toBe('WATCH')
    expect(levelFor(10, t)).toBe('ACT')
    expect(levelFor(-3, t)).toBeNull() // improvement is never an alert
    expect(levelFor(NaN, t)).toBeNull()
  })
})

describe('summarizeSession (guards)', () => {
  it('drops low-confidence reps before computing anything', () => {
    const rec = session({ day: 1, nReps: 8 })
    rec.reps[0] = { ...rec.reps[0]!, confidence: 0.2, minKneeAngle: 170 } // garbage rep
    const m = summarizeSession(rec)
    expect(m.completedReps).toBe(8)
    expect(m.validReps).toBe(7)
    expect(m.depthDeg).toBeLessThan(100) // the 170° outlier was excluded
  })

  it('is not usable with fewer than K valid reps', () => {
    expect(summarizeSession(session({ day: 1, nReps: HEALTH_RULES.minValidReps - 1 })).usable).toBe(false)
    expect(summarizeSession(session({ day: 1, nReps: HEALTH_RULES.minValidReps })).usable).toBe(true)
  })

  it('is not usable at low confidence', () => {
    expect(summarizeSession(session({ day: 1, conf: 0.5 })).usable).toBe(false)
  })

  it('handles an empty (skipped) session', () => {
    const m = summarizeSession({ ...session({ day: 1 }), reps: [] })
    expect(m.usable).toBe(false)
    expect(m.validReps).toBe(0)
  })
})

describe('baseline', () => {
  it('is the median of the first 3 usable sessions', () => {
    const recs = [
      session({ day: 1, depth: 90 }),
      session({ day: 2, depth: 100 }),
      session({ day: 3, depth: 95 }),
      session({ day: 4, depth: 130 }),
    ]
    const usable = recs.map((r) => summarizeSession(r)).filter((m) => m.usable)
    expect(computeBaseline(usable)?.depthDeg).toBeCloseTo(95, 5)
    expect(computeBaseline(usable)?.days).toEqual([1, 2, 3])
  })

  it('skips unusable sessions (too few reps) when building the baseline', () => {
    const recs = [
      session({ day: 1, depth: 90 }),
      session({ day: 2, nReps: 2 }), // too few valid reps -> skipped
      session({ day: 3, depth: 100 }),
      session({ day: 4, depth: 95 }),
    ]
    const a = assessExercise(recs, 'c1', 'squat')
    expect(a.baseline?.days).toEqual([1, 3, 4])
  })

  it('is not ready (NOMINAL, with a note) until N usable sessions exist', () => {
    const a = rules([session({ day: 1 }), session({ day: 2 })])
    expect(a.baseline).toBeNull()
    expect(a.status).toBe('NOMINAL')
    expect(a.notes.join(' ')).toMatch(/Building baseline \(2\/3 valid sessions\)/)
  })

  it('honours a configurable baseline size', () => {
    const cfg = { ...HEALTH_RULES, baselineSessions: 2 }
    const a = assessExercise([session({ day: 1 }), session({ day: 2 })], 'c1', 'squat', cfg)
    expect(a.baseline).not.toBeNull()
  })
})

describe('rules: depth decline', () => {
  it('stays quiet below the WATCH threshold', () => {
    expect(ruleLevels(withBaseline({ day: 4, depth: 95 + 7 }, { day: 5, depth: 95 + 7 }))).toEqual({})
  })
  it('WATCH at +8°, ACT at +16°', () => {
    expect(ruleLevels(withBaseline({ day: 4, depth: 103 }, { day: 5, depth: 103 })).depth).toBe('WATCH')
    expect(ruleLevels(withBaseline({ day: 4, depth: 111 }, { day: 5, depth: 111 })).depth).toBe('ACT')
  })
  it('deeper than baseline is never an alert', () => {
    expect(ruleLevels(withBaseline({ day: 4, depth: 80 }, { day: 5, depth: 80 }))).toEqual({})
  })
  it('alert carries what / why / action and a trend series', () => {
    const a = rules(withBaseline({ day: 4, depth: 105 }, { day: 5, depth: 105 })).alerts[0]!
    expect(a.what.baseline).toBeCloseTo(95, 5)
    expect(a.what.now).toBeCloseTo(105, 5)
    expect(a.what.summary).toMatch(/shallower/)
    expect(a.what.series).toHaveLength(5)
    expect(a.why.sourceId).toBe('hrp-muscle-bone')
    expect(a.why.text.length).toBeGreaterThan(20)
    expect(a.actions.length).toBeGreaterThan(0)
  })
})

describe('rules: concentric slowing', () => {
  it('WATCH from +15%, ACT from +30%', () => {
    expect(ruleLevels(withBaseline({ day: 4, concentric: 1.14 }, { day: 5, concentric: 1.14 }))).toEqual({})
    expect(ruleLevels(withBaseline({ day: 4, concentric: 1.16 }, { day: 5, concentric: 1.16 })).concentric).toBe('WATCH')
    expect(ruleLevels(withBaseline({ day: 4, concentric: 1.31 }, { day: 5, concentric: 1.31 })).concentric).toBe('ACT')
  })
  it('faster than baseline is not an alert', () => {
    expect(ruleLevels(withBaseline({ day: 4, concentric: 0.7 }, { day: 5, concentric: 0.7 }))).toEqual({})
  })
})

describe('rules: rising asymmetry', () => {
  it('WATCH at +4°, ACT at +8°', () => {
    expect(ruleLevels(withBaseline({ day: 4, asym: 5.9 }, { day: 5, asym: 5.9 }))).toEqual({})
    expect(ruleLevels(withBaseline({ day: 4, asym: 6 }, { day: 5, asym: 6 })).asymmetry).toBe('WATCH')
    expect(ruleLevels(withBaseline({ day: 4, asym: 10 }, { day: 5, asym: 10 })).asymmetry).toBe('ACT')
  })
})

describe('rules: rising variability', () => {
  it('fires when depth spread across reps grows', () => {
    // spread s => SD of 8 evenly spaced reps ≈ 0.6 × s
    const calm = withBaseline({ day: 4 }, { day: 5 })
    expect(ruleLevels(calm)).toEqual({})
    const loose = withBaseline({ day: 4, spread: 14 }, { day: 5, spread: 14 })
    expect(['WATCH', 'ACT']).toContain(ruleLevels(loose).variability)
  })
})

describe('rules: adherence', () => {
  const days = (reps: number) => [1, 2, 3, 4, 5, 6, 7].map((d) => session({ day: d, nReps: reps, prescribed: 10 }))
  it('NOMINAL at full adherence', () => {
    expect(ruleLevels(days(10))).toEqual({})
  })
  it('WATCH below 80% and ACT below 60% of prescribed volume', () => {
    expect(ruleLevels(days(7)).adherence).toBe('WATCH') // 70%
    expect(ruleLevels(days(5)).adherence).toBe('ACT') // 50%
  })
  it('counts skipped sessions against adherence', () => {
    const recs = days(10).map((r, i) => (i >= 4 ? { ...r, reps: [] } : r)) // 3 of 7 skipped
    expect(adherenceRatio(recs.map((r) => summarizeSession(r)), 7, 7)).toBeCloseTo(40 / 70, 5)
    expect(ruleLevels(recs).adherence).toBe('ACT') // 57% is below the 60% ACT line
  })
  it('low camera confidence is not counted as skipped exercise', () => {
    const recs = [1, 2, 3, 4, 5, 6, 7].map((d) => session({ day: d, conf: 0.3, prescribed: 8 }))
    expect(ruleLevels(recs).adherence).toBeUndefined()
  })
  it('works before any baseline exists', () => {
    const a = rules([session({ day: 1, nReps: 4, prescribed: 10 })])
    expect(a.baseline).toBeNull()
    expect(a.alerts[0]?.rule).toBe('adherence')
  })
  it('ignores sessions older than the adherence window', () => {
    const old = session({ day: 1, nReps: 0, prescribed: 10 })
    const recent = [20, 21, 22].map((d) => session({ day: d, nReps: 10, prescribed: 10 }))
    expect(adherenceRatio([old, ...recent].map((r) => summarizeSession(r)), 22, 7)).toBe(1)
  })
})

describe('guards against false alerts', () => {
  it('a single bad session does not alert (rules use the median of recent sessions)', () => {
    const recs = withBaseline({ day: 4, depth: 95 }, { day: 5, depth: 125 }, { day: 6, depth: 95 })
    expect(ruleLevels(recs)).toEqual({})
  })

  it('needs at least minRecentSessions comparable sessions after the baseline', () => {
    const a = rules(withBaseline({ day: 4, depth: 130 }))
    expect(a.alerts).toHaveLength(0)
    expect(a.notes.join(' ')).toMatch(/Waiting for 2 comparable sessions/)
  })

  it('low-confidence deteriorated sessions never raise an alert', () => {
    const recs = withBaseline({ day: 4, depth: 140, conf: 0.4 }, { day: 5, depth: 140, conf: 0.4 })
    const a = rules(recs)
    expect(a.alerts).toHaveLength(0)
    expect(a.usableSessions).toBe(3)
  })

  it('sessions with fewer than K valid reps never raise an alert', () => {
    const recs = withBaseline({ day: 4, depth: 140, nReps: 3 }, { day: 5, depth: 140, nReps: 3 })
    expect(rules(recs).alerts.filter((a) => a.rule !== 'adherence')).toHaveLength(0)
  })

  it('pauses kinematic comparison when gravity differs from the baseline', () => {
    const recs = withBaseline({ day: 4, depth: 130, g: 0.38 }, { day: 5, depth: 130, g: 0.38 })
    const a = rules(recs)
    expect(a.alerts.filter((x) => x.rule !== 'adherence')).toHaveLength(0)
    expect(a.notes.join(' ')).toMatch(/different gravity/)
  })

  it('does not mix other crew members or exercises', () => {
    const recs = [
      ...withBaseline({ day: 4 }, { day: 5 }),
      ...[1, 2, 3, 4, 5].map((d) => session({ day: d, crewId: 'c2', depth: 150 })),
      ...[1, 2, 3, 4, 5].map((d) => session({ day: d, exercise: 'deadlift', depth: 150 })),
    ]
    expect(assessExercise(recs, 'c1', 'squat').status).toBe('NOMINAL')
  })
})

describe('status and escalation', () => {
  it('overall status is the worst alert level', () => {
    const recs = withBaseline({ day: 4, depth: 103 }, { day: 5, depth: 103 })
    expect(rules(recs).status).toBe('WATCH')
    expect(rules(withBaseline({ day: 4, depth: 120 }, { day: 5, depth: 120 })).status).toBe('ACT')
  })

  it('three concurrent WATCH rules escalate to ACT', () => {
    const recs = withBaseline(
      { day: 4, depth: 103, concentric: 1.2, asym: 6.5 },
      { day: 5, depth: 103, concentric: 1.2, asym: 6.5 },
    )
    const a = rules(recs)
    expect(a.alerts.every((x) => x.level === 'WATCH')).toBe(true)
    expect(a.alerts.length).toBeGreaterThanOrEqual(3)
    expect(a.status).toBe('ACT')
    expect(a.notes.join(' ')).toMatch(/escalates to ACT/)
  })

  it('two WATCH rules stay WATCH', () => {
    const recs = withBaseline({ day: 4, depth: 103, asym: 6.5 }, { day: 5, depth: 103, asym: 6.5 })
    expect(rules(recs).status).toBe('WATCH')
  })

  it('assessCrew takes the worst status across exercises', () => {
    const recs = [
      ...withBaseline({ day: 4 }, { day: 5 }),
      ...[1, 2, 3].map((d) => session({ day: d, exercise: 'deadlift' })),
      ...[4, 5].map((d) => session({ day: d, exercise: 'deadlift', depth: 125 })),
    ]
    const c = assessCrew(recs, 'c1')
    expect(c.exercises).toHaveLength(2)
    expect(c.status).toBe('ACT')
    expect(c.alerts.every((a) => a.exercise === 'deadlift')).toBe(true)
  })

  it('thresholds are configurable', () => {
    const strict = { ...HEALTH_RULES, depth: { watch: 2, act: 4 } }
    const recs = withBaseline({ day: 4, depth: 99 }, { day: 5, depth: 99 })
    expect(assessExercise(recs, 'c1', 'squat', strict).alerts[0]?.level).toBe('ACT')
  })
})
