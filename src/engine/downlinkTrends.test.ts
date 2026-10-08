import { describe, expect, it } from 'vitest'
import { CREW } from '../data/crew'
import { DEMO_CHECKINS, DEMO_DAYS, DEMO_SESSIONS } from '../data/demoSeed'
import { encodeCsv } from '../data/csv'
import { CSV_COLUMNS, adherencePct, buildPacket, hashText, mergeTrends, packetCsv, parsePacketCsv, type TrendRow } from './downlink'

const crew = CREW.map((c) => ({ id: c.id, name: c.name, role: c.role }))
const csvFor = (day: number, windowDays = 7) => buildPacket({ sessions: DEMO_SESSIONS, checkins: DEMO_CHECKINS, crew, day, windowDays, id: `p${day}`, now: 1 }).csv

describe('parsePacketCsv', () => {
  it('reads back the session rows a packet wrote', () => {
    const r = parsePacketCsv(packetCsv(DEMO_SESSIONS, DEMO_CHECKINS, DEMO_DAYS, 7))
    expect(r.ok).toBe(true)
    if (!r.ok) return
    expect(r.rows).toHaveLength(3 * 7) // check-in rows are skipped
    const c3 = r.rows.filter((x) => x.crewId === 'c3' && x.day === DEMO_DAYS)[0]!
    const src = DEMO_SESSIONS.find((s) => s.crewId === 'c3' && s.day === DEMO_DAYS)!
    expect(c3.exercise).toBe('squat')
    expect(c3.reps).toBe(src.reps.length)
    expect(c3.asymmetryDeg).toBeGreaterThan(5)
  })

  it('treats empty metric cells as null (a skipped session has no depth)', () => {
    const rows = [[...CSV_COLUMNS], ['session', '5', 'c1', 'squat', '0', '24', '', '', '', '', '', '', '', '', '', '']]
    const r = parsePacketCsv(encodeCsv(rows))
    expect(r.ok && r.rows[0]).toMatchObject({ reps: 0, prescribedReps: 24, depthDeg: null, concentricS: null })
  })

  it.each([
    ['empty text', ''],
    ['wrong header', 'a,b,c\r\n1,2,3\r\n'],
    ['unterminated quote', `${CSV_COLUMNS.join(',')}\r\nsession,"x`],
  ])('rejects %s', (_l, text) => {
    expect(parsePacketCsv(text).ok).toBe(false)
  })

  it('rejects non-numeric values, negative or fractional days, and a missing crew id', () => {
    const base = ['session', '5', 'c1', 'squat', '10', '24', '95', '1', '2', '1', '0.9', '', '', '', '', '']
    for (const bad of [
      [...base.slice(0, 6), 'abc', ...base.slice(7)],
      ['session', '-1', ...base.slice(2)],
      ['session', '2.5', ...base.slice(2)],
      ['session', '5', '', ...base.slice(3)],
    ]) {
      expect(parsePacketCsv(encodeCsv([[...CSV_COLUMNS], bad])).ok).toBe(false)
    }
    expect(parsePacketCsv(encodeCsv([[...CSV_COLUMNS], base])).ok).toBe(true)
  })

  it('rejects an unknown record type with its line number', () => {
    const r = parsePacketCsv(encodeCsv([[...CSV_COLUMNS], ['banana', ...Array(15).fill('')]]))
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error).toMatch(/Line 2/)
  })
})

describe('mergeTrends', () => {
  it('stitches overlapping packets into one continuous series with no duplicate days', () => {
    const merged = mergeTrends([csvFor(20), csvFor(27), csvFor(30)])
    const c1 = merged.filter((r) => r.crewId === 'c1')
    const days = c1.map((r) => r.day)
    expect(new Set(days).size).toBe(days.length)
    expect(Math.min(...days)).toBe(14)
    expect(Math.max(...days)).toBe(30)
    expect(days).toEqual([...days].sort((a, b) => a - b))
  })

  it('a later packet overrides an earlier one for the same crew, exercise and day', () => {
    const mk = (depth: number) => encodeCsv([[...CSV_COLUMNS], ['session', '9', 'c1', 'squat', '8', '24', String(depth), '1', '2', '1', '0.9', '', '', '', '', '']])
    const merged = mergeTrends([mk(90), mk(111)])
    expect(merged).toHaveLength(1)
    expect(merged[0]?.depthDeg).toBe(111)
  })

  it('skips an unreadable packet instead of failing the whole series', () => {
    expect(mergeTrends(['garbage', csvFor(30)]).length).toBeGreaterThan(0)
  })

  it('returns nothing for no packets', () => {
    expect(mergeTrends([])).toEqual([])
  })
})

describe('adherencePct / hashText', () => {
  const row = (reps: number, prescribedReps: number): TrendRow => ({ day: 1, crewId: 'c1', exercise: 'squat', reps, prescribedReps, depthDeg: 1, concentricS: 1, asymmetryDeg: 1, variabilityDeg: 1 })
  it('computes completed / prescribed in percent', () => {
    expect(adherencePct(row(12, 24))).toBe(50)
    expect(adherencePct(row(0, 24))).toBe(0)
    expect(adherencePct(row(5, 0))).toBeNull()
  })

  it('hashText is deterministic and sensitive to content', () => {
    expect(hashText('abc')).toBe(hashText('abc'))
    expect(hashText('abc')).not.toBe(hashText('abd'))
    expect(hashText('')).toMatch(/^[0-9a-f]{8}$/)
  })
})
