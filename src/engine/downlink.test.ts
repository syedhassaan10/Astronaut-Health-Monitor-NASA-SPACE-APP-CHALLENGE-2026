import { describe, expect, it } from 'vitest'
import { CREW } from '../data/crew'
import { DEMO_CHECKINS, DEMO_DAYS, DEMO_SESSIONS } from '../data/demoSeed'
import { parseCsv } from '../data/csv'
import { HEALTH_RULES } from '../config/healthRules'
import { assessCrew } from './changeDetection'
import {
  CSV_COLUMNS, DISCLAIMER, MAX_PACKET_CSV_CHARS, buildPacket, formatKb, packetCsv, packetSizeBytes, parsePacket, parsePacketJson,
} from './downlink'

const crew = CREW.map((c) => ({ id: c.id, name: c.name, role: c.role }))
const build = (o: { day?: number; windowDays?: number } = {}) =>
  buildPacket({ sessions: DEMO_SESSIONS, checkins: DEMO_CHECKINS, crew, day: o.day ?? DEMO_DAYS, windowDays: o.windowDays ?? 14, id: 'pkt-test', now: 1_700_000_000_000 })

describe('buildPacket', () => {
  const p = build()

  it('is deterministic', () => {
    expect(build()).toEqual(p)
  })

  it('summarises every crew member with the same status the rules give', () => {
    expect(p.summary.crew.map((c) => c.crewId)).toEqual(['c1', 'c2', 'c3'])
    for (const c of CREW) {
      const direct = assessCrew(DEMO_SESSIONS, c.id, HEALTH_RULES, DEMO_CHECKINS)
      const inPacket = p.summary.crew.find((x) => x.crewId === c.id)!
      expect(inPacket.status).toBe(direct.status)
      expect(inPacket.alerts.map((a) => `${a.rule}:${a.level}`).sort()).toEqual(direct.alerts.map((a) => `${a.rule}:${a.level}`).sort())
    }
  })

  it('carries what changed for every alert, never a diagnosis', () => {
    const c1 = p.summary.crew.find((c) => c.crewId === 'c1')!
    expect(c1.alerts.length).toBeGreaterThan(0)
    for (const a of c1.alerts) expect(a.summary.length).toBeGreaterThan(10)
    expect(p.summary.disclaimer).toBe(DISCLAIMER)
    // Wording rule: outside the disclaimer ("Not a diagnosis") the packet never uses diagnostic language.
    const withoutDisclaimer = JSON.stringify({ ...p, summary: { ...p.summary, disclaimer: '' } }).toLowerCase()
    expect(withoutDisclaimer).not.toContain('diagnos')
  })

  it('includes baseline and deltas for exercises with a baseline, and the latest check-in', () => {
    const c3 = p.summary.crew.find((c) => c.crewId === 'c3')!
    expect(c3.exercises[0]?.baseline).not.toBeNull()
    expect(c3.exercises[0]?.deltas?.asymmetryDeg).toBeGreaterThan(2)
    expect(c3.latestCheckin?.day).toBe(DEMO_DAYS)
    expect(c3.latestCheckin?.painLocation).toBe('knee')
  })

  it('is compact: a few KB, far smaller than the full logbook', () => {
    const bytes = packetSizeBytes(p)
    expect(bytes).toBeGreaterThan(1000)
    expect(bytes).toBeLessThan(25 * 1024)
  })

  it('can be built as of an earlier mission day (statuses differ)', () => {
    const early = build({ day: 12 })
    expect(early.missionDay).toBe(12)
    expect(early.summary.crew.every((c) => c.status === 'NOMINAL')).toBe(true)
    expect(p.summary.crew.some((c) => c.status !== 'NOMINAL')).toBe(true)
  })

  it('survives a JSON round trip unchanged', () => {
    const back = parsePacketJson(JSON.stringify(p))
    expect(back.ok).toBe(true)
    if (back.ok) expect(back.packet).toEqual(p)
  })
})

describe('packetCsv', () => {
  it('has the documented header and consistent column counts', () => {
    const rows = parseCsv(packetCsv(DEMO_SESSIONS, DEMO_CHECKINS, DEMO_DAYS, 14))
    expect(rows[0]).toEqual([...CSV_COLUMNS])
    for (const r of rows) expect(r).toHaveLength(CSV_COLUMNS.length)
  })

  it('covers exactly the requested window: one session and one check-in per crew per day', () => {
    const rows = parseCsv(packetCsv(DEMO_SESSIONS, DEMO_CHECKINS, DEMO_DAYS, 7)).slice(1)
    const sessions = rows.filter((r) => r[0] === 'session')
    const checkins = rows.filter((r) => r[0] === 'checkin')
    expect(sessions).toHaveLength(3 * 7)
    expect(checkins).toHaveLength(3 * 7)
    const days = rows.map((r) => Number(r[1]))
    expect(Math.min(...days)).toBe(DEMO_DAYS - 6)
    expect(Math.max(...days)).toBe(DEMO_DAYS)
  })

  it('a longer window makes a bigger packet', () => {
    expect(packetSizeBytes(build({ windowDays: 30 }))).toBeGreaterThan(packetSizeBytes(build({ windowDays: 7 })))
  })

  it('uses CRLF line endings so it opens cleanly in Excel', () => {
    const t = packetCsv(DEMO_SESSIONS, DEMO_CHECKINS, DEMO_DAYS, 3)
    expect(t.endsWith('\r\n')).toBe(true)
    expect(t.replace(/\r\n/g, '').includes('\n')).toBe(false)
  })
})

describe('parsePacket (untrusted input)', () => {
  const good = () => JSON.parse(JSON.stringify(build())) as Record<string, unknown>

  it('accepts a real packet', () => {
    expect(parsePacket(good()).ok).toBe(true)
  })

  it.each([
    ['null', null],
    ['an array', []],
    ['a string', 'x'],
    ['wrong version', { ...good(), version: 2 }],
    ['missing id', { ...good(), id: undefined }],
    ['id with illegal characters', { ...good(), id: 'a b/c' }],
    ['id too long', { ...good(), id: 'x'.repeat(81) }],
    ['bad createdAt', { ...good(), createdAt: 'yesterday' }],
    ['negative createdAt', { ...good(), createdAt: -1 }],
    ['fractional missionDay', { ...good(), missionDay: 1.5 }],
    ['missing csv', { ...good(), csv: undefined }],
    ['no summary', { ...good(), summary: undefined }],
    ['crew not an array', { ...good(), summary: { crew: 'x' } }],
  ])('rejects %s', (_label, v) => {
    expect(parsePacket(v).ok).toBe(false)
  })

  it('rejects an oversized CSV', () => {
    expect(parsePacket({ ...good(), csv: 'x'.repeat(MAX_PACKET_CSV_CHARS + 1) }).ok).toBe(false)
  })

  it('rejects malformed crew or alert entries', () => {
    const p = good() as { summary: { crew: Record<string, unknown>[] } }
    p.summary.crew[0]!.status = 'FINE'
    expect(parsePacket(p).ok).toBe(false)
    const q = good() as { summary: { crew: { alerts: Record<string, unknown>[] }[] } }
    q.summary.crew[0]!.alerts = [{ title: 1 }]
    expect(parsePacket(q).ok).toBe(false)
  })

  it('reports invalid JSON text without throwing', () => {
    const r = parsePacketJson('{not json')
    expect(r.ok).toBe(false)
    if (!r.ok) expect(r.error).toMatch(/not valid JSON/)
  })

  it('formatKb prints kilobytes with one decimal', () => {
    expect(formatKb(2048)).toBe('2.0 KB')
    expect(formatKb(1536)).toBe('1.5 KB')
  })
})
