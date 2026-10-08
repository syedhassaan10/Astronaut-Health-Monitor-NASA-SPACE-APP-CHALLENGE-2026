import 'fake-indexeddb/auto'
import { beforeEach, describe, expect, it } from 'vitest'
import { CREW } from '../data/crew'
import { DEMO_CHECKINS, DEMO_DAYS, DEMO_SESSIONS } from '../data/demoSeed'
import { toLogbookCsv } from '../data/logbookCsv'
import { HEALTH_RULES } from '../config/healthRules'
import { assessCrew } from '../engine/changeDetection'
import { OrbitDB } from './db'
import { exportLogbookCsv, importLogbookCsv } from './logbookIO'
import {
  TODAY, addAlertEntries, addRep, ensureSeeded, finishSession, getNote, listActiveSessions, loadSessionRecords,
  repId, resetDemoData, saveCheckin, seedDemoData, sessionReps, setAcknowledged, setNote, startSession,
} from './repo'
import type { RepRow } from './schema'

let n = 0
let dbName = ''
let db: OrbitDB
beforeEach(() => {
  dbName = `orbitfit-test-${n++}`
  db = new OrbitDB(dbName)
})

const rep = (sessionId: string, repNo: number, o: Partial<RepRow> = {}): RepRow => ({
  id: repId(sessionId, repNo), sessionId, crewId: 'c1', exercise: 'squat', timestamp: 1_000_000 + repNo * 1000, gravityG: 0,
  targetLoadKg: 110, repNo, minKneeAngle: 95, eccentricS: 3, concentricS: 1, asymmetry: 2, confidence: 0.9,
  formScore: 90, flags: [], level: 'green', ...o,
})
const live = (crewId = 'c1') => ({ crewId, exercise: 'squat' as const, gravityG: 0, targetLoadKg: 110, prescribedReps: 24, source: 'webcam' as const })

describe('crash-proof recording', () => {
  it('a rep is in IndexedDB the moment addRep resolves: a brand-new connection (a reload) sees it', async () => {
    await db.crew.bulkPut(CREW.map((c) => ({ id: c.id, name: c.name, role: c.role, massKg: c.massKg })))
    const s = await startSession(live(), db)
    await addRep(rep(s.id, 1), db)
    await addRep(rep(s.id, 2), db)
    db.close() // "close the tab" without ever calling finishSession

    const afterReload = new OrbitDB(dbName)
    expect(await sessionReps(s.id, afterReload)).toHaveLength(2)
    const active = await listActiveSessions(afterReload)
    expect(active.map((x) => x.id)).toEqual([s.id]) // -> the "Resume session" prompt
    expect(active[0]?.status).toBe('active')
  })

  it('reps keep their order and numbering across a resume', async () => {
    const s = await startSession(live(), db)
    for (const k of [3, 1, 2]) await addRep(rep(s.id, k), db)
    expect((await sessionReps(s.id, db)).map((r) => r.repNo)).toEqual([1, 2, 3])
    await addRep(rep(s.id, 4), db) // continues after "resume"
    expect(await db.reps.count()).toBe(4)
  })

  it('writing the same rep twice is idempotent', async () => {
    const s = await startSession(live(), db)
    await addRep(rep(s.id, 1), db)
    await addRep(rep(s.id, 1, { minKneeAngle: 99 }), db)
    const rows = await sessionReps(s.id, db)
    expect(rows).toHaveLength(1)
    expect(rows[0]?.minKneeAngle).toBe(99)
  })

  it('stores every field the logbook needs on each rep', async () => {
    const s = await startSession(live(), db)
    await addRep(rep(s.id, 1, { flags: ['shallow'], formScore: 70, level: 'amber' }), db)
    const r = (await sessionReps(s.id, db))[0]!
    for (const k of ['timestamp', 'sessionId', 'crewId', 'exercise', 'gravityG', 'targetLoadKg', 'repNo', 'minKneeAngle',
      'eccentricS', 'concentricS', 'asymmetry', 'confidence', 'formScore', 'flags'] as const) {
      expect(r[k]).toBeDefined()
    }
  })

  it('finishSession closes a session so it is no longer offered for resume', async () => {
    const s = await startSession(live(), db)
    await addRep(rep(s.id, 1), db)
    await finishSession(s.id, db)
    expect(await listActiveSessions(db)).toEqual([])
    const row = await db.sessions.get(s.id)
    expect(row?.status).toBe('completed')
    expect(row?.endedAt).not.toBeNull()
  })

  it('a live session with zero reps is deleted on finish (no phantom skipped workout)', async () => {
    const s = await startSession(live(), db)
    await finishSession(s.id, db)
    expect(await db.sessions.get(s.id)).toBeUndefined()
  })

  it('finishing an unknown session is harmless', async () => {
    await expect(finishSession('nope', db)).resolves.toBeUndefined()
  })
})

describe('loadSessionRecords', () => {
  it('joins sessions with their reps for the health rules', async () => {
    const s = await startSession(live(), db)
    await addRep(rep(s.id, 1, { minKneeAngle: 90, asymmetry: 4 }), db)
    await finishSession(s.id, db)
    const [r] = await loadSessionRecords(db)
    expect(r).toMatchObject({ id: s.id, crewId: 'c1', exercise: 'squat', day: TODAY, prescribedReps: 24 })
    expect(r?.reps).toEqual([{ minKneeAngle: 90, eccentricS: 3, concentricS: 1, asymmetryDeg: 4, confidence: 0.9 }])
  })

  it('ignores empty live sessions but keeps empty seeded (skipped) sessions', async () => {
    await startSession(live(), db) // empty + live
    await db.sessions.put({ id: 'seed-skip', crewId: 'c1', exercise: 'squat', day: 5, gravityG: 0, targetLoadKg: 100, prescribedReps: 24,
      status: 'completed', startedAt: 1, endedAt: 2, source: 'demo-seed' })
    const recs = await loadSessionRecords(db)
    expect(recs.map((r) => r.id)).toEqual(['seed-skip'])
    expect(recs[0]?.reps).toEqual([])
  })

  it('an unfinished session only counts what it has done so far against adherence', async () => {
    const s = await startSession(live(), db)
    await addRep(rep(s.id, 1), db)
    await addRep(rep(s.id, 2), db)
    const [r] = await loadSessionRecords(db)
    expect(r?.prescribedReps).toBe(2) // not 24: it is still in progress
    await finishSession(s.id, db)
    expect((await loadSessionRecords(db))[0]?.prescribedReps).toBe(24)
  })

  it('orders by mission day then start time', async () => {
    const mk = (id: string, day: number, startedAt: number) => db.sessions.put({ id, crewId: 'c1', exercise: 'squat', day, gravityG: 0,
      targetLoadKg: 1, prescribedReps: 1, status: 'completed', startedAt, endedAt: null, source: 'demo-seed' })
    await mk('b', 2, 50); await mk('a', 1, 90); await mk('c', 2, 10)
    expect((await loadSessionRecords(db)).map((r) => r.id)).toEqual(['a', 'c', 'b'])
  })
})

describe('check-ins, notes and alert log', () => {
  it('saves one check-in per crew member per day (a second save replaces it)', async () => {
    const base = { crewId: 'c1', day: 30, sleep: 7, fatigue: 3, pain: 0, painLocation: null, stress: 2 } as const
    await saveCheckin(base, db)
    await saveCheckin({ ...base, pain: 6, painLocation: 'knee' }, db)
    const rows = await db.checkins.toArray()
    expect(rows).toHaveLength(1)
    expect(rows[0]).toMatchObject({ id: 'c1:d30', pain: 6, painLocation: 'knee' })
  })

  it('CMO notes persist per crew member and update in place', async () => {
    expect(await getNote('c1', db)).toBeUndefined()
    await setNote('c1', 'Review knee on day 31', db)
    await setNote('c1', 'Reviewed. Reduce load.', db)
    await setNote('c2', 'All good', db)
    expect((await getNote('c1', db))?.text).toBe('Reviewed. Reduce load.')
    expect((await getNote('c2', db))?.text).toBe('All good')
    expect(await db.cmoNotes.count()).toBe(2)
  })

  it('alert log only adds new keys and keeps the acknowledged flag', async () => {
    const e = { key: 'c1:squat:depth|WATCH', crewId: 'c1', exercise: 'squat' as const, rule: 'depth' as const, level: 'WATCH' as const,
      title: 'Depth', summary: 's', day: 20 }
    expect(await addAlertEntries([e], db)).toBe(1)
    await setAcknowledged(e.key, true, db)
    expect(await addAlertEntries([e, { ...e, key: 'c1:squat:depth|ACT', level: 'ACT' }], db)).toBe(1) // only the escalation
    expect((await db.alerts.get(e.key))?.acknowledged).toBe(true)
    expect(await db.alerts.count()).toBe(2)
  })
})

describe('demo seed', () => {
  it('seeds crew, sessions, reps, check-ins and the alert log exactly once', async () => {
    await ensureSeeded(db)
    await ensureSeeded(db)
    expect(await db.crew.count()).toBe(CREW.length)
    expect(await db.sessions.count()).toBe(DEMO_SESSIONS.length)
    expect(await db.reps.count()).toBe(DEMO_SESSIONS.reduce((a, s) => a + s.reps.length, 0))
    expect(await db.checkins.count()).toBe(DEMO_CHECKINS.length)
    expect(await db.alerts.count()).toBeGreaterThan(0)
    expect(await db.downlinkQueue.count()).toBe(0)
  })

  it('stored data gives the SAME crew statuses as the in-memory demo data (nothing lost in storage)', async () => {
    await seedDemoData(db)
    const records = await loadSessionRecords(db)
    const checkins = await db.checkins.toArray()
    for (const c of CREW) {
      const fromDb = assessCrew(records, c.id, HEALTH_RULES, checkins)
      const fromMemory = assessCrew(DEMO_SESSIONS, c.id, HEALTH_RULES, DEMO_CHECKINS)
      expect(fromDb.status).toBe(fromMemory.status)
      expect(fromDb.alerts.map((a) => `${a.rule}:${a.level}`).sort()).toEqual(fromMemory.alerts.map((a) => `${a.rule}:${a.level}`).sort())
    }
  })

  it('the stored alert log records when each alert was first raised', async () => {
    await seedDemoData(db)
    const first = await db.alerts.toArray()
    const c1 = first.filter((a) => a.crewId === 'c1')
    expect(c1.length).toBeGreaterThan(0)
    expect(Math.min(...c1.map((a) => a.day))).toBeGreaterThan(5)
    expect(Math.max(...first.map((a) => a.day))).toBeLessThanOrEqual(DEMO_DAYS)
    expect(first.filter((a) => a.crewId === 'c2')).toHaveLength(0) // the nominal crew member never alerted
  })

  it('resetDemoData wipes live sessions, notes and queue, then re-seeds', async () => {
    await seedDemoData(db)
    const s = await startSession(live(), db)
    await addRep(rep(s.id, 1), db)
    await setNote('c1', 'x', db)
    await resetDemoData(db)
    expect(await db.sessions.get(s.id)).toBeUndefined()
    expect(await getNote('c1', db)).toBeUndefined()
    expect(await db.sessions.count()).toBe(DEMO_SESSIONS.length)
  })
})

describe('CSV export / import', () => {
  it('importing our own export into the same logbook adds nothing (idempotent)', async () => {
    await seedDemoData(db)
    const csv = await exportLogbookCsv(db)
    const before = { s: await db.sessions.count(), r: await db.reps.count(), c: await db.checkins.count() }
    const report = await importLogbookCsv(csv, db)
    expect(report.errors).toEqual([])
    expect(report.added).toEqual({ sessions: 0, reps: 0, checkins: 0 })
    expect(report.alreadyPresent).toBe(before.s + before.r + before.c)
    expect({ s: await db.sessions.count(), r: await db.reps.count(), c: await db.checkins.count() }).toEqual(before)
  })

  it('a full export restores a wiped logbook (same crew table) with identical assessments', async () => {
    await seedDemoData(db)
    const csv = await exportLogbookCsv(db)
    const other = new OrbitDB(`${dbName}-restore`)
    await other.crew.bulkPut(await db.crew.toArray())
    const report = await importLogbookCsv(csv, other)
    expect(report.errors).toEqual([])
    expect(report.added.reps).toBe(await db.reps.count())
    const a = await loadSessionRecords(db)
    const b = await loadSessionRecords(other)
    // The export rounds numbers to 4 decimals, so values match to within that rounding...
    expect(b.map((r) => [r.id, r.crewId, r.day, r.prescribedReps, r.reps.length]))
      .toEqual(a.map((r) => [r.id, r.crewId, r.day, r.prescribedReps, r.reps.length]))
    for (let i = 0; i < a.length; i++) {
      a[i]!.reps.forEach((x, j) => {
        const y = b[i]!.reps[j]!
        for (const k of ['minKneeAngle', 'eccentricS', 'concentricS', 'asymmetryDeg', 'confidence'] as const) {
          expect(Math.abs(x[k] - y[k])).toBeLessThan(1e-4)
        }
      })
    }
    // ...and the health rules give exactly the same answers on the restored data.
    const checkinsA = await db.checkins.toArray()
    const checkinsB = await other.checkins.toArray()
    for (const c of CREW) {
      const ra = assessCrew(a, c.id, HEALTH_RULES, checkinsA)
      const rb = assessCrew(b, c.id, HEALTH_RULES, checkinsB)
      expect(rb.status).toBe(ra.status)
      expect(rb.alerts.map((x) => `${x.rule}:${x.level}`).sort()).toEqual(ra.alerts.map((x) => `${x.rule}:${x.level}`).sort())
    }
  })

  it('imported rows survive a reload', async () => {
    await db.crew.bulkPut(CREW.map((c) => ({ id: c.id, name: c.name, role: c.role, massKg: c.massKg })))
    const csv = toLogbookCsv({
      sessions: [{ id: 's-imp', crewId: 'c1', exercise: 'squat', day: 12, gravityG: 0, targetLoadKg: 100, prescribedReps: 24,
        status: 'completed', startedAt: 1_700_000_000_000, endedAt: null, source: 'webcam' }],
      reps: [rep('s-imp', 1)], checkins: [],
    })
    await importLogbookCsv(csv, db)
    db.close()
    expect(await sessionReps('s-imp', new OrbitDB(dbName))).toHaveLength(1)
  })

  it('an imported "active" session does not trigger a Resume prompt', async () => {
    await db.crew.bulkPut(CREW.map((c) => ({ id: c.id, name: c.name, role: c.role, massKg: c.massKg })))
    const csv = toLogbookCsv({
      sessions: [{ id: 's-act', crewId: 'c1', exercise: 'squat', day: 12, gravityG: 0, targetLoadKg: 100, prescribedReps: 24,
        status: 'active', startedAt: 1_700_000_000_000, endedAt: null, source: 'webcam' }],
      reps: [], checkins: [],
    })
    await importLogbookCsv(csv, db)
    expect(await listActiveSessions(db)).toEqual([])
  })

  it('skips reps for unknown sessions or unknown crew, but still imports the valid rows', async () => {
    await db.crew.bulkPut(CREW.map((c) => ({ id: c.id, name: c.name, role: c.role, massKg: c.massKg })))
    const csv = toLogbookCsv({
      sessions: [{ id: 's-ok', crewId: 'c1', exercise: 'squat', day: 3, gravityG: 0, targetLoadKg: 100, prescribedReps: 24,
        status: 'completed', startedAt: 1_700_000_000_000, endedAt: null, source: 'webcam' }],
      reps: [rep('s-ok', 1), rep('s-ghost', 1), rep('s-ok', 2, { crewId: 'zz' })],
      checkins: [{ id: 'x', crewId: 'nobody', day: 1, sleep: 5, fatigue: 5, pain: 0, painLocation: null, stress: 5 }],
    })
    const report = await importLogbookCsv(csv, db)
    expect(report.added).toEqual({ sessions: 1, reps: 1, checkins: 0 })
    const msgs = report.errors.map((e) => e.message).join(' | ')
    expect(msgs).toMatch(/unknown session "s-ghost"/)
    expect(msgs).toMatch(/unknown crew "zz"/)
    expect(msgs).toMatch(/unknown crew "nobody"/)
  })

  it('imports rep data into an existing session (resume-then-import scenario) without duplicates', async () => {
    const s = await startSession(live(), db)
    await addRep(rep(s.id, 1), db)
    await db.crew.bulkPut(CREW.map((c) => ({ id: c.id, name: c.name, role: c.role, massKg: c.massKg })))
    const csv = toLogbookCsv({ sessions: [], reps: [rep(s.id, 1), rep(s.id, 2)], checkins: [] })
    const report = await importLogbookCsv(csv, db)
    expect(report.added.reps).toBe(1)
    expect(await db.reps.count()).toBe(2)
  })

  it('the export keeps unusual text safe for Excel', async () => {
    await db.crew.bulkPut(CREW.map((c) => ({ id: c.id, name: c.name, role: c.role, massKg: c.massKg })))
    await db.sessions.put({ id: '=cmd', crewId: 'c1', exercise: 'squat', day: 1, gravityG: 0, targetLoadKg: 1, prescribedReps: 1,
      status: 'completed', startedAt: 1_700_000_000_000, endedAt: null, source: 'import' })
    const csv = await exportLogbookCsv(db)
    expect(csv).toContain("'=cmd")
    expect(csv.startsWith('﻿')).toBe(true)
  })
})
