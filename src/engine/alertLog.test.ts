import { describe, expect, it } from 'vitest'
import { DEMO_CHECKINS, DEMO_DAYS, DEMO_SESSIONS } from '../data/demoSeed'
import { alertKey, newLogEntries, replayAlertLog, toLogEntry } from './alertLog'
import { assessCrew } from './changeDetection'

const crew = ['c1', 'c2', 'c3']
const log = replayAlertLog(DEMO_SESSIONS, DEMO_CHECKINS, crew, DEMO_DAYS)
const find = (crewId: string, rule: string, level: string) => log.find((e) => e.crewId === crewId && e.rule === rule && e.level === level)

describe('replayAlertLog', () => {
  it('records the first day each alert appeared, per level, in chronological order', () => {
    const days = log.map((e) => e.day)
    expect([...days].sort((a, b) => a - b)).toEqual(days)
    expect(new Set(log.map((e) => e.key)).size).toBe(log.length) // no duplicate keys
  })

  it('logs an escalation as its own entry (WATCH first, ACT later)', () => {
    const w = find('c1', 'concentric', 'WATCH')
    const a = find('c1', 'concentric', 'ACT')
    expect(w).toBeDefined()
    expect(a).toBeDefined()
    expect(a!.day).toBeGreaterThan(w!.day)
  })

  it('never logs anything for the nominal crew member', () => {
    expect(log.filter((e) => e.crewId === 'c2')).toHaveLength(0)
  })

  it('knee pain + asymmetry is logged before asymmetry alone', () => {
    expect(find('c3', 'pain-asymmetry', 'WATCH')!.day).toBeLessThan(find('c3', 'asymmetry', 'WATCH')!.day)
  })

  it('every alert active on the last day is in the log', () => {
    const keys = new Set(log.map((e) => e.key))
    for (const c of crew) {
      for (const a of assessCrew(DEMO_SESSIONS, c, undefined, DEMO_CHECKINS).alerts) expect(keys.has(alertKey(a))).toBe(true)
    }
  })
})

describe('newLogEntries', () => {
  const alerts = assessCrew(DEMO_SESSIONS, 'c1', undefined, DEMO_CHECKINS).alerts

  it('returns only alerts whose key is not known yet', () => {
    const known = new Set([alertKey(alerts[0]!)])
    const fresh = newLogEntries(alerts, known, 31)
    expect(fresh).toHaveLength(alerts.length - 1)
    expect(fresh.every((e) => e.day === 31)).toBe(true)
  })

  it('returns nothing when everything is already logged', () => {
    expect(newLogEntries(alerts, new Set(alerts.map(alertKey)), 31)).toEqual([])
  })

  it('toLogEntry copies the what-changed summary', () => {
    const e = toLogEntry(alerts[0]!, 12)
    expect(e.summary).toBe(alerts[0]!.what.summary)
    expect(e.day).toBe(12)
  })
})
