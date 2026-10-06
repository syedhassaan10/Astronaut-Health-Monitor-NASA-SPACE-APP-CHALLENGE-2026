import { describe, expect, it } from 'vitest'
import { HEALTH_RULES } from '../config/healthRules'
import { assessCrew } from './changeDetection'
import { assessCheckins, contextFor, recentCheckins } from './checkinRules'
import type { BodyLocation, CheckIn, RepSample, SessionRecord } from './healthTypes'

let n = 0
function ci(day: number, o: Partial<Omit<CheckIn, 'id' | 'day'>> = {}): CheckIn {
  return {
    id: `ci${n++}`, crewId: 'c1', day,
    sleep: 7, fatigue: 3, pain: 0, painLocation: null, stress: 3, ...o,
  }
}
const pain = (day: number, p: number, loc: BodyLocation = 'knee') => ci(day, { pain: p, painLocation: loc })

function session(day: number, o: { depth?: number; asym?: number; concentric?: number } = {}): SessionRecord {
  const reps: RepSample[] = Array.from({ length: 8 }, (_, i) => ({
    minKneeAngle: (o.depth ?? 95) + (i / 7 - 0.5) * 4,
    eccentricS: 2, concentricS: o.concentric ?? 1, asymmetryDeg: o.asym ?? 2, confidence: 0.9,
  }))
  return { id: `s${day}`, crewId: 'c1', exercise: 'squat', day, gravityG: 0, prescribedReps: 8, reps }
}
/** Healthy baseline on days 1-3, then two later sessions with the given values. */
const sessions = (later: { depth?: number; asym?: number; concentric?: number } = {}) =>
  [session(1), session(2), session(3), session(4, later), session(5, later)]

const alertsOf = (checkins: CheckIn[], recs: SessionRecord[] = []) => assessCrew(recs, 'c1', HEALTH_RULES, checkins).alerts
const rule = (checkins: CheckIn[], r: string, recs: SessionRecord[] = []) => alertsOf(checkins, recs).find((a) => a.rule === r)

describe('recentCheckins', () => {
  it('returns the latest N for one crew member, oldest first', () => {
    const all = [ci(5), ci(1), ci(3), { ...ci(4), crewId: 'c2' }, ci(2)]
    // c1 days sorted are 1, 2, 3, 5 (day 4 belongs to c2), so the latest three are 2, 3, 5.
    expect(recentCheckins(all, 'c1', 3).map((c) => c.day)).toEqual([2, 3, 5])
  })
})

describe('pain rule', () => {
  it('no alert for no / mild pain', () => {
    expect(rule([ci(1), ci(2), ci(3)], 'pain')).toBeUndefined()
    expect(rule([pain(1, 2), pain(2, 3), pain(3, 3)], 'pain')).toBeUndefined()
  })

  it('WATCH when pain >= 4 in at least 2 of the latest 3', () => {
    expect(rule([pain(1, 0), pain(2, 4), pain(3, 5)], 'pain')?.level).toBe('WATCH')
  })

  it('one moderate report alone is not enough', () => {
    expect(rule([ci(1), ci(2), pain(3, 5)], 'pain')).toBeUndefined()
  })

  it('a single acute report (>= 7) raises WATCH immediately', () => {
    expect(rule([ci(1), ci(2), pain(3, 7)], 'pain')?.level).toBe('WATCH')
  })

  it('ACT when pain >= 7 in at least 2 of the latest 3', () => {
    expect(rule([pain(1, 7), pain(2, 8), pain(3, 2)], 'pain')?.level).toBe('ACT')
  })

  it('names the body location and carries what / why / action', () => {
    const a = rule([pain(1, 5, 'lower-back'), pain(2, 5, 'lower-back'), pain(3, 6, 'lower-back')], 'pain')!
    expect(a.title).toMatch(/lower back/)
    expect(a.exercise).toBeNull()
    expect(a.what.summary).toMatch(/6\/10/)
    expect(a.why.sourceId).toBe('hrp-muscle-bone')
    expect(a.actions.length).toBeGreaterThan(0)
    expect(a.what.series).toHaveLength(3)
  })

  it('old pain falls out of the window', () => {
    expect(rule([pain(1, 8), pain(2, 8), ci(3), ci(4), ci(5)], 'pain')).toBeUndefined()
  })
})

describe('recovery rule', () => {
  const bad = (d: number) => ci(d, { sleep: 3, fatigue: 8 })
  it('WATCH when poor sleep AND high fatigue are sustained', () => {
    expect(rule([ci(1), bad(2), bad(3)], 'recovery')?.level).toBe('WATCH')
  })
  it('needs both poor sleep and high fatigue', () => {
    expect(rule([ci(1, { sleep: 3 }), ci(2, { sleep: 3 }), ci(3, { sleep: 3 })], 'recovery')).toBeUndefined()
    expect(rule([ci(1, { fatigue: 9 }), ci(2, { fatigue: 9 }), ci(3, { fatigue: 9 })], 'recovery')).toBeUndefined()
  })
  it('a single bad night is not an alert', () => {
    expect(rule([ci(1), ci(2), bad(3)], 'recovery')).toBeUndefined()
  })
})

describe('stress rule', () => {
  it('WATCH when stress >= 8 in at least 2 of the latest 3', () => {
    expect(rule([ci(1), ci(2, { stress: 8 }), ci(3, { stress: 9 })], 'stress')?.level).toBe('WATCH')
    expect(rule([ci(1), ci(2), ci(3, { stress: 9 })], 'stress')).toBeUndefined()
  })
  it('points to the behavioural-health source', () => {
    expect(rule([ci(1, { stress: 9 }), ci(2, { stress: 9 })], 'stress')?.why.sourceId).toBe('hrp-behavioral')
  })
})

describe('combined rule: knee pain + rising asymmetry', () => {
  it('WATCH when knee pain is reported and asymmetry is up by >= 2° (below its own alert threshold)', () => {
    const recs = sessions({ asym: 4.5 }) // +2.5° vs baseline 2, below the 4° WATCH line
    expect(recs.length).toBe(5)
    const all = alertsOf([ci(1), ci(2), pain(3, 3)], recs)
    expect(all.find((a) => a.rule === 'asymmetry')).toBeUndefined() // asymmetry alone is quiet
    const a = all.find((x) => x.rule === 'pain-asymmetry')!
    expect(a.level).toBe('WATCH')
    expect(a.exercise).toBe('squat')
    expect(a.what.delta).toBeCloseTo(2.5, 5)
    expect(a.what.summary).toMatch(/Knee pain/)
  })

  it('knee pain alone does not trigger it', () => {
    expect(rule([ci(1), ci(2), pain(3, 3)], 'pain-asymmetry', sessions({ asym: 2 }))).toBeUndefined()
  })

  it('rising asymmetry alone does not trigger it', () => {
    expect(rule([ci(1), ci(2), ci(3)], 'pain-asymmetry', sessions({ asym: 5 }))).toBeUndefined()
  })

  it('pain somewhere else does not count as knee pain', () => {
    expect(rule([ci(1), ci(2), pain(3, 5, 'shoulder')], 'pain-asymmetry', sessions({ asym: 5 }))).toBeUndefined()
  })

  it('needs knee pain of at least 3/10', () => {
    expect(rule([ci(1), ci(2), pain(3, 2)], 'pain-asymmetry', sessions({ asym: 5 }))).toBeUndefined()
  })

  it('escalates to ACT with sustained severe knee pain', () => {
    const a = rule([pain(1, 7), pain(2, 8), pain(3, 7)], 'pain-asymmetry', sessions({ asym: 5 }))
    expect(a?.level).toBe('ACT')
  })

  it('escalates to ACT when the asymmetry alert itself is ACT', () => {
    const a = rule([ci(1), ci(2), pain(3, 4)], 'pain-asymmetry', sessions({ asym: 11 }))
    expect(a?.level).toBe('ACT')
  })

  it('needs a baseline: no exercise history means no combined alert', () => {
    expect(rule([pain(1, 6), pain(2, 6), pain(3, 6)], 'pain-asymmetry', [])).toBeUndefined()
  })

  it('makes the crew status WATCH', () => {
    const c = assessCrew(sessions({ asym: 4.5 }), 'c1', HEALTH_RULES, [ci(1), ci(2), pain(3, 3)])
    expect(c.status).toBe('WATCH')
  })
})

describe('check-ins feed status', () => {
  it('a crew member with only check-ins can still be raised', () => {
    const c = assessCrew([], 'c1', HEALTH_RULES, [pain(1, 8), pain(2, 8), pain(3, 8)])
    expect(c.status).toBe('ACT')
  })

  it('other crew check-ins are ignored', () => {
    const others = [pain(1, 9), pain(2, 9), pain(3, 9)].map((c) => ({ ...c, crewId: 'c2' }))
    expect(assessCheckins(others, 'c1', [])).toEqual([])
  })

  it('no check-ins means no check-in alerts', () => {
    expect(assessCheckins([], 'c1', [])).toEqual([])
  })

  it('thresholds are configurable', () => {
    const strict = { ...HEALTH_RULES, checkin: { ...HEALTH_RULES.checkin, pain: { watch: 2, act: 3 }, acutePain: 9 } }
    const a = assessCheckins([pain(1, 3), pain(2, 3)], 'c1', [], strict)
    expect(a.find((x) => x.rule === 'pain')?.level).toBe('ACT')
  })
})

describe('context notes on exercise alerts', () => {
  it('adds a fatigue note to slowing alerts when recent check-ins report high fatigue', () => {
    const recs = sessions({ concentric: 1.4 })
    const c = assessCrew(recs, 'c1', HEALTH_RULES, [ci(1), ci(2, { fatigue: 8 }), ci(3, { fatigue: 8 })])
    const a = c.alerts.find((x) => x.rule === 'concentric')!
    expect(a.context?.join(' ')).toMatch(/high fatigue/)
  })

  it('adds a knee-pain note to depth alerts', () => {
    const recs = sessions({ depth: 115 })
    const c = assessCrew(recs, 'c1', HEALTH_RULES, [pain(1, 4), pain(2, 4), pain(3, 4)])
    expect(c.alerts.find((x) => x.rule === 'depth')?.context?.join(' ')).toMatch(/knee pain/)
  })

  it('adds no context when the person feels fine', () => {
    const c = assessCrew(sessions({ depth: 115 }), 'c1', HEALTH_RULES, [ci(1), ci(2), ci(3)])
    expect(c.alerts.find((x) => x.rule === 'depth')?.context).toBeUndefined()
  })

  it('contextFor ignores rules that self-report cannot explain', () => {
    expect(contextFor('adherence', [ci(1, { fatigue: 9 })], 'c1')).toEqual([])
    expect(contextFor('asymmetry', [ci(1, { fatigue: 9 })], 'c1')).toEqual([])
  })

  it('context never changes the status', () => {
    const recs = sessions({ concentric: 1.4 })
    const base = assessCrew(recs, 'c1', HEALTH_RULES, [])
    const tired = assessCrew(recs, 'c1', HEALTH_RULES, [ci(1, { fatigue: 9 }), ci(2, { fatigue: 9 })])
    expect(tired.status).toBe(base.status)
  })
})
