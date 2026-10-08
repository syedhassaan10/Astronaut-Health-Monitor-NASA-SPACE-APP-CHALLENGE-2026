import Dexie, { type EntityTable } from 'dexie'
import type { AlertRow, CheckIn, CrewRow, NoteRow, QueueRow, RepRow, SessionRow } from './schema'

/**
 * OrbitFit's local logbook. Everything lives in the browser's IndexedDB, so it survives
 * reloads, crashes and going offline. Tables: crew, sessions, reps, checkins, alerts,
 * downlinkQueue (+ cmoNotes for the Crew Medical Officer's notes).
 */
export class OrbitDB extends Dexie {
  crew!: EntityTable<CrewRow, 'id'>
  sessions!: EntityTable<SessionRow, 'id'>
  reps!: EntityTable<RepRow, 'id'>
  checkins!: EntityTable<CheckIn, 'id'>
  alerts!: EntityTable<AlertRow, 'key'>
  downlinkQueue!: EntityTable<QueueRow, 'id'>
  cmoNotes!: EntityTable<NoteRow, 'crewId'>

  constructor(name = 'orbitfit') {
    super(name)
    this.version(1).stores({
      crew: 'id',
      sessions: 'id, crewId, status, day, [crewId+exercise]',
      reps: 'id, sessionId, crewId, timestamp',
      checkins: 'id, crewId, [crewId+day]',
      alerts: 'key, crewId, level, day',
      downlinkQueue: 'id, status, createdAt',
      cmoNotes: 'crewId',
    })
  }
}

export const db = new OrbitDB()

/** Ask the browser not to evict our data under storage pressure (best effort). */
export async function requestPersistentStorage(): Promise<boolean> {
  try {
    return (await navigator.storage?.persist?.()) ?? false
  } catch {
    return false
  }
}
