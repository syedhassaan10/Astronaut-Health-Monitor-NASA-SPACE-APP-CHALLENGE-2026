import { describe, expect, it } from 'vitest'
import { assessCrew } from '../engine/changeDetection'
import { DEMO_DAYS, DEMO_SESSIONS, generateDemoSessions } from './demoSeed'

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
