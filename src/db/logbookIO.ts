import { parseLogbookCsv, toLogbookCsv, type RowError } from '../data/logbookCsv'
import { db as defaultDb, type OrbitDB } from './db'

export async function exportLogbookCsv(database: OrbitDB = defaultDb): Promise<string> {
  const [sessions, reps, checkins] = await Promise.all([
    database.sessions.toArray(), database.reps.toArray(), database.checkins.toArray(),
  ])
  sessions.sort((a, b) => a.day - b.day || a.startedAt - b.startedAt)
  reps.sort((a, b) => a.timestamp - b.timestamp || a.repNo - b.repNo)
  checkins.sort((a, b) => a.day - b.day || a.crewId.localeCompare(b.crewId))
  return toLogbookCsv({ sessions, reps, checkins })
}

export interface ImportReport {
  totalRows: number
  /** Rows written that were not in the logbook before. */
  added: { sessions: number; reps: number; checkins: number }
  /** Rows whose id was already in the logbook; they are left untouched (an import never overwrites). */
  alreadyPresent: number
  errors: RowError[]
}

/**
 * Imports a logbook CSV as a merge: every row has a stable id, rows already in the logbook are
 * left untouched (so importing the same file twice adds nothing, and an old file can never
 * overwrite newer data). Invalid rows, rows for unknown crew, and reps whose session is unknown
 * are reported and skipped; valid rows are still imported.
 */
export async function importLogbookCsv(text: string, database: OrbitDB = defaultDb): Promise<ImportReport> {
  const parsed = parseLogbookCsv(text)
  const errors = [...parsed.errors]
  const crewIds = new Set((await database.crew.toArray()).map((c) => c.id))

  /** Keeps rows for known crew; reports (and drops) the rest. */
  const forKnownCrew = <T extends { id: string; crewId: string }>(rows: T[], what: string): T[] =>
    rows.filter((r) => {
      if (crewIds.has(r.crewId)) return true
      errors.push({ line: 0, message: `${what} ${r.id}: unknown crew "${r.crewId}"` })
      return false
    })

  const sessions = forKnownCrew(parsed.sessions, 'session')
  const checkins = forKnownCrew(parsed.checkins, 'check-in')

  // One key scan per table (not one lookup per row): fast even for a 100k-row file.
  const keys = async (t: { toCollection(): { primaryKeys(): Promise<unknown[]> } }) => new Set((await t.toCollection().primaryKeys()) as string[])
  const [dbSessions, dbReps, dbCheckins] = await Promise.all([keys(database.sessions), keys(database.reps), keys(database.checkins)])

  const sessionIds = new Set(sessions.map((s) => s.id))
  const reps = forKnownCrew(parsed.reps, 'rep').filter((r) => {
    if (!sessionIds.has(r.sessionId) && !dbSessions.has(r.sessionId)) {
      errors.push({ line: 0, message: `rep ${r.id}: unknown session "${r.sessionId}"` })
      return false
    }
    return true
  })

  const presentS = sessions.filter((x) => dbSessions.has(x.id)).length
  const presentR = reps.filter((x) => dbReps.has(x.id)).length
  const presentC = checkins.filter((x) => dbCheckins.has(x.id)).length
  const alreadyPresent = presentS + presentR + presentC

  await database.transaction('rw', [database.sessions, database.reps, database.checkins], async () => {
    await database.sessions.bulkAdd(sessions.filter((x) => !dbSessions.has(x.id)))
    await database.reps.bulkAdd(reps.filter((x) => !dbReps.has(x.id)))
    await database.checkins.bulkAdd(checkins.filter((x) => !dbCheckins.has(x.id)))
  })

  return {
    totalRows: parsed.totalRows,
    added: {
      sessions: sessions.length - presentS,
      reps: reps.length - presentR,
      checkins: checkins.length - presentC,
    },
    alreadyPresent,
    errors,
  }
}
