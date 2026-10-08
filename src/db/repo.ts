import { CREW } from '../data/crew'
import { DEMO_CHECKINS, DEMO_DAYS, DEMO_SESSIONS } from '../data/demoSeed'
import { replayAlertLog, type AlertLogEntry } from '../engine/alertLog'
import { assessRep, targetsFor } from '../engine/formFeedback'
import { buildPlan, tempoForG } from '../engine/gravityEngine'
import type { CheckIn, SessionRecord } from '../engine/healthTypes'
import { REP_CONFIGS, type RepMetrics } from '../engine/repDetector'
import { db as defaultDb, type OrbitDB } from './db'
import type { AlertRow, NoteRow, RepRow, SessionRow, SessionSource } from './schema'

/** The mission day that live sessions and check-ins are stamped with (latest seeded day). */
export const TODAY = DEMO_DAYS

export const repId = (sessionId: string, repNo: number): string => `${sessionId}#${repNo}`
export const checkinId = (crewId: string, day: number): string => `${crewId}:d${day}`

// ---- sessions & reps (crash-proof recording) ----------------------------------------------

export async function startSession(
  p: Pick<SessionRow, 'crewId' | 'exercise' | 'gravityG' | 'targetLoadKg' | 'prescribedReps'> & { source: SessionSource },
  database: OrbitDB = defaultDb,
): Promise<SessionRow> {
  const row: SessionRow = {
    id: `s-${crypto.randomUUID()}`,
    ...p,
    day: TODAY,
    status: 'active',
    startedAt: Date.now(),
    endedAt: null,
  }
  await database.sessions.put(row)
  return row
}

/** Write one rep immediately. Idempotent: the same session + repNo overwrites itself. */
export async function addRep(row: RepRow, database: OrbitDB = defaultDb): Promise<void> {
  await database.reps.put(row)
}

/**
 * Close a session. A live session with no reps (the user opened the camera and stopped) is
 * deleted so it cannot register as a skipped workout.
 */
export async function finishSession(id: string, database: OrbitDB = defaultDb): Promise<void> {
  const s = await database.sessions.get(id)
  if (!s) return
  const n = await database.reps.where('sessionId').equals(id).count()
  if (n === 0 && (s.source === 'webcam' || s.source === 'video')) {
    await database.sessions.delete(id)
    return
  }
  await database.sessions.update(id, { status: 'completed', endedAt: Date.now() })
}

export function listActiveSessions(database: OrbitDB = defaultDb): Promise<SessionRow[]> {
  return database.sessions.where('status').equals('active').toArray()
}

export async function sessionReps(sessionId: string, database: OrbitDB = defaultDb): Promise<RepRow[]> {
  const rows = await database.reps.where('sessionId').equals(sessionId).toArray()
  return rows.sort((a, b) => a.repNo - b.repNo)
}

/** Sessions + reps joined into the shape the health rules consume. */
export async function loadSessionRecords(database: OrbitDB = defaultDb): Promise<SessionRecord[]> {
  const [sessions, reps] = await Promise.all([database.sessions.toArray(), database.reps.toArray()])
  const byS = new Map<string, RepRow[]>()
  for (const r of reps) {
    const list = byS.get(r.sessionId)
    if (list) list.push(r)
    else byS.set(r.sessionId, [r])
  }
  const out: { rec: SessionRecord; startedAt: number }[] = []
  for (const s of sessions) {
    const rs = (byS.get(s.id) ?? []).sort((a, b) => a.repNo - b.repNo)
    const live = s.source === 'webcam' || s.source === 'video'
    if (live && rs.length === 0) continue
    out.push({
      startedAt: s.startedAt,
      rec: {
        id: s.id, crewId: s.crewId, exercise: s.exercise, day: s.day, gravityG: s.gravityG,
        // A session still in progress is not a shortfall yet: only count what is prescribed so far.
        prescribedReps: s.status === 'active' ? Math.min(s.prescribedReps, rs.length) : s.prescribedReps,
        reps: rs.map((r) => ({
          minKneeAngle: r.minKneeAngle, eccentricS: r.eccentricS, concentricS: r.concentricS,
          asymmetryDeg: r.asymmetry, confidence: r.confidence,
        })),
      },
    })
  }
  return out.sort((a, b) => a.rec.day - b.rec.day || a.startedAt - b.startedAt).map((x) => x.rec)
}

// ---- check-ins -----------------------------------------------------------------------------

/** One check-in per crew member per mission day: saving again replaces it. */
export async function saveCheckin(c: Omit<CheckIn, 'id'>, database: OrbitDB = defaultDb): Promise<void> {
  await database.checkins.put({ ...c, id: checkinId(c.crewId, c.day) })
}

// ---- CMO notes -----------------------------------------------------------------------------

export async function getNote(crewId: string, database: OrbitDB = defaultDb): Promise<NoteRow | undefined> {
  return database.cmoNotes.get(crewId)
}

export async function setNote(crewId: string, text: string, database: OrbitDB = defaultDb): Promise<void> {
  await database.cmoNotes.put({ crewId, text, updatedAt: Date.now() })
}

// ---- alert log -----------------------------------------------------------------------------

const toAlertRow = (e: AlertLogEntry, raisedAt: number): AlertRow => ({
  key: e.key, crewId: e.crewId, exercise: e.exercise, rule: e.rule, level: e.level,
  title: e.title, summary: e.summary, day: e.day, raisedAt, acknowledged: false,
})

/** Adds entries whose key is new; existing entries (and their acknowledged flag) are untouched. */
export async function addAlertEntries(entries: AlertLogEntry[], database: OrbitDB = defaultDb): Promise<number> {
  if (entries.length === 0) return 0
  const existing = new Set(await database.alerts.bulkGet(entries.map((e) => e.key)).then((r) => r.filter(Boolean).map((x) => (x as AlertRow).key)))
  const fresh = entries.filter((e) => !existing.has(e.key))
  await database.alerts.bulkPut(fresh.map((e) => toAlertRow(e, Date.now())))
  return fresh.length
}

export async function setAcknowledged(key: string, acknowledged: boolean, database: OrbitDB = defaultDb): Promise<void> {
  await database.alerts.update(key, { acknowledged })
}

// ---- demo seed -----------------------------------------------------------------------------

const MISSION_START = Date.UTC(2026, 8, 1)

/** Builds the stored rep rows for one seeded session (form score from the real rule code). */
function seededRepRows(rec: SessionRecord, sessionStart: number): RepRow[] {
  const cfg = REP_CONFIGS[rec.exercise]
  const mass = CREW.find((c) => c.id === rec.crewId)?.massKg ?? 70
  const target = buildPlan(mass, rec.gravityG, rec.exercise).targetLoadKg
  const tempo = tempoForG(rec.gravityG)
  return rec.reps.map((r, i) => {
    const m: RepMetrics = {
      repNo: i + 1, startMs: 0, endMs: 0, holdS: 0, minKneeAngle: r.minKneeAngle, eccentricS: r.eccentricS,
      concentricS: r.concentricS, asymmetryDeg: r.asymmetryDeg, confidence: r.confidence,
    }
    const a = cfg ? assessRep(m, targetsFor(cfg, tempo)) : null
    return {
      id: repId(rec.id, i + 1), sessionId: rec.id, crewId: rec.crewId, exercise: rec.exercise,
      timestamp: sessionStart + i * 6000, gravityG: rec.gravityG, targetLoadKg: target, repNo: i + 1,
      minKneeAngle: r.minKneeAngle, eccentricS: r.eccentricS, concentricS: r.concentricS,
      asymmetry: r.asymmetryDeg, confidence: r.confidence,
      formScore: a?.score ?? 0, flags: a?.flags ?? [], level: a?.overall ?? 'green',
    }
  })
}

/** Writes the 3-crew x 30-day demo dataset (sessions, reps, check-ins, alert log) into an empty DB. */
export async function seedDemoData(database: OrbitDB = defaultDb): Promise<void> {
  const sessions: SessionRow[] = []
  const reps: RepRow[] = []
  for (const rec of DEMO_SESSIONS) {
    const startedAt = MISSION_START + rec.day * 86_400_000
    const mass = CREW.find((c) => c.id === rec.crewId)?.massKg ?? 70
    sessions.push({
      id: rec.id, crewId: rec.crewId, exercise: rec.exercise, day: rec.day, gravityG: rec.gravityG,
      targetLoadKg: buildPlan(mass, rec.gravityG, rec.exercise).targetLoadKg,
      prescribedReps: rec.prescribedReps, status: 'completed', startedAt, endedAt: startedAt + 20 * 60_000, source: 'demo-seed',
    })
    reps.push(...seededRepRows(rec, startedAt))
  }
  const checkins = DEMO_CHECKINS.map((c) => ({ ...c, id: checkinId(c.crewId, c.day) }))
  const log = replayAlertLog(DEMO_SESSIONS, DEMO_CHECKINS, CREW.map((c) => c.id), DEMO_DAYS)

  await database.transaction('rw', [database.crew, database.sessions, database.reps, database.checkins, database.alerts], async () => {
    await database.crew.bulkPut(CREW.map((c) => ({ id: c.id, name: c.name, role: c.role, massKg: c.massKg })))
    await database.sessions.bulkPut(sessions)
    await database.reps.bulkPut(reps)
    await database.checkins.bulkPut(checkins)
    await database.alerts.bulkPut(log.map((e) => toAlertRow(e, MISSION_START + e.day * 86_400_000)))
  })
}

let seeding: Promise<void> | null = null

/** Seeds the demo data the first time the app runs (crew table empty). Safe to call repeatedly. */
export function ensureSeeded(database: OrbitDB = defaultDb): Promise<void> {
  if (database === defaultDb && seeding) return seeding
  const run = (async () => {
    if ((await database.crew.count()) === 0) await seedDemoData(database)
  })()
  if (database === defaultDb) seeding = run.catch((e) => { seeding = null; throw e })
  return run
}

/** Wipes every table and re-seeds the demo data. */
export async function resetDemoData(database: OrbitDB = defaultDb): Promise<void> {
  await database.transaction(
    'rw',
    [database.crew, database.sessions, database.reps, database.checkins, database.alerts, database.downlinkQueue, database.cmoNotes],
    async () => {
      await Promise.all([database.crew.clear(), database.sessions.clear(), database.reps.clear(), database.checkins.clear(),
        database.alerts.clear(), database.downlinkQueue.clear(), database.cmoNotes.clear()])
    },
  )
  await seedDemoData(database)
}
