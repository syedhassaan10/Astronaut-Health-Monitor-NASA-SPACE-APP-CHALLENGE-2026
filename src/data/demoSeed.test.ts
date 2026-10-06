import { describe, expect, it } from 'vitest'
import { HEALTH_RULES } from '../config/healthRules'
import { assessCrew } from '../engine/changeDetection'
import { DEMO_CHECKINS, DEMO_DAYS, DEMO_SESSIONS, generateDemoCheckins, generateDemoSessions } from './demoSeed'

const upTo = (day: number) => DEMO_SESSIONS.filter((s) => s.day <= day)
const status = (crewId: string, day: number) => assessCrew(upTo(day), crewId).status

describe('demo seed', () => {
  it('is deterministic', () => {
    expect(generateDemoSessions()).toEqual(generateDemoSessions())
  })

  it('has 3 crew x 30 days', () => {
    expect(DEMO_SESSIONS).toHaveLength(3 * DEMO_DAYS)
  })

  it('c1 (deconditioning) progresses NOMINAL -> WATCH -> ACT', () => {
    expect(status('c1', 8)).toBe('NOMINAL')
    const seen = Array.from({ length: DEMO_DAYS }, (_, i) => status('c1', i + 1))
    const firstWatch = seen.indexOf('WATCH')
    const firstAct = seen.indexOf('ACT')
    expect(firstWatch).toBeGreaterThan(8)
    expect(firstAct).toBeGreaterThan(firstWatch)
    expect(seen[DEMO_DAYS - 1]).toBe('ACT')
  })

  it('c2 (nominal) never leaves NOMINAL', () => {
    for (let d = 1; d <= DEMO_DAYS; d++) expect(status('c2', d)).toBe('NOMINAL')
  })

  it('c3 (asymmetry) reaches WATCH from the asymmetry rule alone', () => {
    const a = assessCrew(DEMO_SESSIONS, 'c3')
    expect(a.status).not.toBe('NOMINAL')
    expect(a.alerts.map((x) => x.rule)).toContain('asymmetry')
  })

  it('every final alert has what, why and an action', () => {
    for (const crewId of ['c1', 'c3']) {
      for (const al of assessCrew(DEMO_SESSIONS, crewId).alerts) {
        expect(al.what.summary.length).toBeGreaterThan(10)
        expect(al.what.series.length).toBeGreaterThan(3)
        expect(al.why.text.length).toBeGreaterThan(20)
        expect(al.actions.length).toBeGreaterThan(0)
      }
    }
  })
})

describe('demo seed with daily check-ins', () => {
  const run = (crewId: string) => {
    const first: Record<string, number> = {}
    const statuses = Array.from({ length: DEMO_DAYS }, (_, i) => {
      const d = i + 1
      const a = assessCrew(upTo(d), crewId, HEALTH_RULES, DEMO_CHECKINS.filter((c) => c.day <= d))
      for (const al of a.alerts) first[al.rule] ??= d
      return a.status
    })
    return { first, statuses }
  }

  it('check-ins are deterministic, one per crew per day, all within 0-10', () => {
    expect(DEMO_CHECKINS).toHaveLength(3 * DEMO_DAYS)
    expect(generateDemoCheckins()).toEqual(generateDemoCheckins())
    for (const c of DEMO_CHECKINS) {
      for (const v of [c.sleep, c.fatigue, c.pain, c.stress]) {
        expect(v).toBeGreaterThanOrEqual(0)
        expect(v).toBeLessThanOrEqual(10)
      }
      expect(c.painLocation === null).toBe(c.pain === 0)
    }
  })

  it('c2 stays NOMINAL with no alerts of any kind', () => {
    const { first, statuses } = run('c2')
    expect(first).toEqual({})
    expect(statuses.every((s) => s === 'NOMINAL')).toBe(true)
  })

  it('c3: knee pain + rising asymmetry raises WATCH BEFORE asymmetry alone would', () => {
    const { first, statuses } = run('c3')
    expect(first['pain-asymmetry']).toBeDefined()
    expect(first['asymmetry']).toBeDefined()
    expect(first['pain-asymmetry']!).toBeLessThan(first['asymmetry']!)
    expect(statuses[DEMO_DAYS - 1]).toBe('WATCH')
  })

  it('c1 still goes NOMINAL -> WATCH -> ACT, and the late poor sleep/fatigue is flagged', () => {
    const { first, statuses } = run('c1')
    expect(statuses[8]).toBe('NOMINAL')
    expect(statuses[DEMO_DAYS - 1]).toBe('ACT')
    expect(first['recovery']).toBeDefined()
  })

  it('c1 slow-rep alerts carry a fatigue context note once fatigue is high', () => {
    const a = assessCrew(DEMO_SESSIONS, 'c1', HEALTH_RULES, DEMO_CHECKINS)
    const slow = a.alerts.find((x) => x.rule === 'concentric')
    expect(slow?.context?.join(' ')).toMatch(/fatigue/)
  })
})
