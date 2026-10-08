import type { RepRow, SessionRow, SessionSource } from '../db/schema'
import { EXERCISE_IDS, type ExerciseId } from '../engine/gravityEngine'
import type { BodyLocation, CheckIn } from '../engine/healthTypes'
import { BOM, encodeCsv, guardText, parseCsv, unguardText } from './csv'

// One flat table, one row per record, with a `record` column (session | rep | checkin).
// It opens directly in Excel and can be filtered by `record`. Unused cells are empty.
export const COLUMNS = [
  'record', 'id', 'timestamp', 'day', 'sessionId', 'crewId', 'exercise', 'gravityG', 'targetLoadKg',
  'prescribedReps', 'repNo', 'minKneeAngle', 'eccentricS', 'concentricS', 'asymmetry', 'confidence',
  'formScore', 'flags', 'level', 'sessionStatus', 'startedAt', 'endedAt', 'source',
  'sleep', 'fatigue', 'pain', 'painLocation', 'stress',
] as const

type Col = (typeof COLUMNS)[number]
type Cells = Partial<Record<Col, string>>

/** Hard limits so a hostile or corrupt file cannot exhaust memory. */
export const MAX_ROWS = 200_000
export const MAX_CHARS = 60_000_000

const num = (n: number): string => String(Math.round(n * 10_000) / 10_000)
const iso = (ms: number): string => new Date(ms).toISOString()

function line(cells: Cells): string[] {
  return COLUMNS.map((c) => cells[c] ?? '')
}

export interface LogbookData {
  sessions: SessionRow[]
  reps: RepRow[]
  checkins: CheckIn[]
}

/** Serialises the logbook. The BOM + CRLF make it open correctly in Excel. */
export function toLogbookCsv(d: LogbookData): string {
  const rows: string[][] = [[...COLUMNS]]
  for (const s of d.sessions) {
    rows.push(line({
      record: 'session', id: guardText(s.id), day: String(s.day), crewId: guardText(s.crewId), exercise: s.exercise,
      gravityG: num(s.gravityG), targetLoadKg: num(s.targetLoadKg), prescribedReps: String(s.prescribedReps),
      sessionStatus: s.status, startedAt: iso(s.startedAt), endedAt: s.endedAt === null ? '' : iso(s.endedAt), source: s.source,
    }))
  }
  for (const r of d.reps) {
    rows.push(line({
      record: 'rep', id: guardText(r.id), timestamp: iso(r.timestamp), sessionId: guardText(r.sessionId), crewId: guardText(r.crewId),
      exercise: r.exercise, gravityG: num(r.gravityG), targetLoadKg: num(r.targetLoadKg), repNo: String(r.repNo),
      minKneeAngle: num(r.minKneeAngle), eccentricS: num(r.eccentricS), concentricS: num(r.concentricS),
      asymmetry: num(r.asymmetry), confidence: num(r.confidence), formScore: String(Math.round(r.formScore)),
      flags: r.flags.join(';'), level: r.level,
    }))
  }
  for (const c of d.checkins) {
    rows.push(line({
      record: 'checkin', id: guardText(c.id), day: String(c.day), crewId: guardText(c.crewId),
      sleep: String(c.sleep), fatigue: String(c.fatigue), pain: String(c.pain),
      painLocation: c.painLocation ?? '', stress: String(c.stress),
    }))
  }
  return BOM + encodeCsv(rows)
}

// ---- parsing & validation ------------------------------------------------------------------

export interface RowError {
  /** 1-based line number in the file (header = line 1). */
  line: number
  message: string
}

export interface ParsedLogbook extends LogbookData {
  errors: RowError[]
  totalRows: number
}

const SOURCES: SessionSource[] = ['webcam', 'video', 'demo-seed', 'import']
const LEVELS = ['green', 'amber', 'red'] as const
const LOCATIONS: BodyLocation[] = ['knee', 'hip', 'ankle-foot', 'lower-back', 'upper-back-neck', 'shoulder', 'other']

class Bad extends Error {}

function text(c: Cells, k: Col, required = true): string {
  const v = unguardText((c[k] ?? '').trim())
  if (required && v === '') throw new Bad(`"${k}" is required`)
  return v
}
function number(c: Cells, k: Col, min: number, max: number): number {
  const raw = (c[k] ?? '').trim()
  if (raw === '') throw new Bad(`"${k}" is required`)
  const n = Number(raw)
  if (!Number.isFinite(n)) throw new Bad(`"${k}" is not a number (${raw})`)
  if (n < min || n > max) throw new Bad(`"${k}" must be between ${min} and ${max} (got ${n})`)
  return n
}
function integer(c: Cells, k: Col, min: number, max: number): number {
  const n = number(c, k, min, max)
  if (!Number.isInteger(n)) throw new Bad(`"${k}" must be a whole number (got ${n})`)
  return n
}
function date(c: Cells, k: Col, required = true): number | null {
  const raw = (c[k] ?? '').trim()
  if (raw === '') {
    if (required) throw new Bad(`"${k}" is required`)
    return null
  }
  const t = Date.parse(raw)
  if (!Number.isFinite(t)) throw new Bad(`"${k}" is not a valid date (${raw})`)
  return t
}
function exercise(c: Cells): ExerciseId {
  const v = text(c, 'exercise')
  if (!(EXERCISE_IDS as string[]).includes(v)) throw new Bad(`unknown exercise "${v}"`)
  return v as ExerciseId
}

function toSession(c: Cells): SessionRow {
  const source = text(c, 'source', false) as SessionSource
  return {
    id: text(c, 'id'), crewId: text(c, 'crewId'), exercise: exercise(c),
    day: integer(c, 'day', 0, 36_500), gravityG: number(c, 'gravityG', 0, 1),
    targetLoadKg: number(c, 'targetLoadKg', 0, 1000), prescribedReps: integer(c, 'prescribedReps', 0, 10_000),
    // An imported session is finished by definition: it must not trigger "Resume session".
    status: 'completed',
    startedAt: date(c, 'startedAt') as number,
    endedAt: date(c, 'endedAt', false),
    source: SOURCES.includes(source) ? source : 'import',
  }
}

function toRep(c: Cells): RepRow {
  const sessionId = text(c, 'sessionId')
  const repNo = integer(c, 'repNo', 1, 100_000)
  const level = text(c, 'level', false)
  if (level !== '' && !(LEVELS as readonly string[]).includes(level)) throw new Bad(`unknown level "${level}"`)
  return {
    id: text(c, 'id', false) || `${sessionId}#${repNo}`, sessionId, crewId: text(c, 'crewId'), exercise: exercise(c),
    timestamp: date(c, 'timestamp') as number, gravityG: number(c, 'gravityG', 0, 1),
    targetLoadKg: number(c, 'targetLoadKg', 0, 1000), repNo,
    minKneeAngle: number(c, 'minKneeAngle', 0, 200), eccentricS: number(c, 'eccentricS', 0, 120),
    concentricS: number(c, 'concentricS', 0, 120), asymmetry: number(c, 'asymmetry', 0, 180),
    confidence: number(c, 'confidence', 0, 1), formScore: number(c, 'formScore', 0, 100),
    flags: text(c, 'flags', false).split(';').map((f) => f.trim()).filter(Boolean),
    level: (level || 'green') as RepRow['level'],
  }
}

function toCheckin(c: Cells): CheckIn {
  const loc = text(c, 'painLocation', false)
  if (loc !== '' && !(LOCATIONS as string[]).includes(loc)) throw new Bad(`unknown pain location "${loc}"`)
  const crewId = text(c, 'crewId')
  const day = integer(c, 'day', 0, 36_500)
  const pain = integer(c, 'pain', 0, 10)
  return {
    id: `${crewId}:d${day}`, crewId, day, sleep: integer(c, 'sleep', 0, 10), fatigue: integer(c, 'fatigue', 0, 10),
    pain, painLocation: pain > 0 ? ((loc || 'other') as BodyLocation) : null, stress: integer(c, 'stress', 0, 10),
  }
}

/** Parses and validates a logbook CSV. Bad rows are reported, never silently imported. */
export function parseLogbookCsv(input: string): ParsedLogbook {
  const out: ParsedLogbook = { sessions: [], reps: [], checkins: [], errors: [], totalRows: 0 }
  if (input.length > MAX_CHARS) {
    out.errors.push({ line: 0, message: 'File is too large to import.' })
    return out
  }
  let rows: string[][]
  try {
    rows = parseCsv(input)
  } catch (e) {
    out.errors.push({ line: 0, message: e instanceof Error ? e.message : 'Could not read the file as CSV.' })
    return out
  }
  const header = rows[0]?.map((h) => h.trim())
  if (!header || !header.includes('record') || !header.includes('id')) {
    out.errors.push({ line: 1, message: 'Not an OrbitFit logbook CSV: the header must include "record" and "id".' })
    return out
  }
  if (rows.length - 1 > MAX_ROWS) {
    out.errors.push({ line: 0, message: `Too many rows (limit ${MAX_ROWS}).` })
    return out
  }
  const index = new Map(header.map((h, i) => [h, i]))
  for (let r = 1; r < rows.length; r++) {
    const cells: Cells = {}
    for (const col of COLUMNS) {
      const i = index.get(col)
      if (i !== undefined) cells[col] = rows[r]?.[i] ?? ''
    }
    out.totalRows++
    try {
      const kind = (cells.record ?? '').trim()
      if (kind === 'session') out.sessions.push(toSession(cells))
      else if (kind === 'rep') out.reps.push(toRep(cells))
      else if (kind === 'checkin') out.checkins.push(toCheckin(cells))
      else throw new Bad(`unknown record type "${kind}"`)
    } catch (e) {
      if (!(e instanceof Bad)) throw e
      out.errors.push({ line: r + 1, message: e.message })
    }
  }
  return out
}
