import { HEALTH_RULES, type HealthRulesConfig } from '../config/healthRules'
import { encodeCsv, parseCsv } from '../data/csv'
import { assessCrew } from './changeDetection'
import type { BodyLocation, CheckIn, SessionRecord, Status } from './healthTypes'
import { summarizeSession } from './sessionMetrics'

// The "flight surgeon packet": what an astronaut would downlink to Earth in a short comms
// window. Compact on purpose (a few KB): a summary for a quick read plus a session-level CSV
// for analysis. Nothing here is a diagnosis; it carries decision-support estimates.

export const PACKET_VERSION = 1
export const DISCLAIMER =
  'Decision-support estimates from a prototype tool. Not a diagnosis or a medical device. Thresholds are demonstration values.'

export interface PacketAlert {
  rule: string
  level: 'WATCH' | 'ACT'
  title: string
  summary: string
  exercise: string | null
  day: number
}

export interface PacketExercise {
  exercise: string
  status: Status
  baseline: { depthDeg: number; concentricS: number; asymmetryDeg: number; variabilityDeg: number } | null
  /** now − baseline for each metric (depth/asymmetry/variability in degrees, concentric in %). */
  deltas: { depthDeg: number; concentricPct: number; asymmetryDeg: number; variabilityDeg: number } | null
}

export interface PacketCrew {
  crewId: string
  name: string
  role: string
  status: Status
  alerts: PacketAlert[]
  exercises: PacketExercise[]
  latestCheckin: { day: number; sleep: number; fatigue: number; pain: number; painLocation: BodyLocation | null; stress: number } | null
}

export interface PacketSummary {
  missionDay: number
  windowDays: number
  disclaimer: string
  crew: PacketCrew[]
}

export interface DownlinkPacket {
  version: typeof PACKET_VERSION
  id: string
  /** Epoch ms when the astronaut built the packet (before any simulated delay). */
  createdAt: number
  missionDay: number
  summary: PacketSummary
  /** Session-level CSV for the same window (see CSV_COLUMNS). */
  csv: string
}

export const CSV_COLUMNS = [
  'record', 'day', 'crewId', 'exercise', 'reps', 'prescribedReps', 'depthDeg', 'concentricS', 'asymmetryDeg',
  'variabilityDeg', 'confidence', 'sleep', 'fatigue', 'pain', 'painLocation', 'stress',
] as const

export interface CrewInfo {
  id: string
  name: string
  role: string
}

export interface BuildInput {
  sessions: SessionRecord[]
  checkins: CheckIn[]
  crew: CrewInfo[]
  /** Latest mission day to include. */
  day: number
  /** Number of mission days of detail in the CSV (summaries always use the full history). */
  windowDays: number
  id: string
  now: number
  cfg?: HealthRulesConfig
}

const r4 = (n: number): string => (Number.isFinite(n) ? String(Math.round(n * 10_000) / 10_000) : '')

/** Session-level CSV for the last `windowDays` mission days: one row per session and per check-in. */
export function packetCsv(sessions: SessionRecord[], checkins: CheckIn[], day: number, windowDays: number, cfg: HealthRulesConfig = HEALTH_RULES): string {
  const rows: string[][] = [[...CSV_COLUMNS]]
  const inWindow = (d: number) => d <= day && d > day - windowDays
  for (const rec of sessions.filter((s) => inWindow(s.day)).sort((a, b) => a.day - b.day || a.crewId.localeCompare(b.crewId))) {
    const m = summarizeSession(rec, cfg)
    rows.push([
      'session', String(m.day), rec.crewId, rec.exercise, String(m.completedReps), String(m.prescribedReps),
      r4(m.depthDeg), r4(m.concentricS), r4(m.asymmetryDeg), r4(m.variabilityDeg), r4(m.meanConfidence), '', '', '', '', '',
    ])
  }
  for (const c of checkins.filter((x) => inWindow(x.day)).sort((a, b) => a.day - b.day || a.crewId.localeCompare(b.crewId))) {
    rows.push(['checkin', String(c.day), c.crewId, '', '', '', '', '', '', '', '', String(c.sleep), String(c.fatigue), String(c.pain), c.painLocation ?? '', String(c.stress)])
  }
  return encodeCsv(rows)
}

/** Builds a packet from the logbook's contents. Pure: the same input gives the same packet. */
export function buildPacket(i: BuildInput): DownlinkPacket {
  const cfg = i.cfg ?? HEALTH_RULES
  const sessions = i.sessions.filter((s) => s.day <= i.day)
  const checkins = i.checkins.filter((c) => c.day <= i.day)
  const crew: PacketCrew[] = i.crew.map((c) => {
    const a = assessCrew(sessions, c.id, cfg, checkins)
    const latest = checkins.filter((x) => x.crewId === c.id).reduce<CheckIn | undefined>((m, x) => (!m || x.day > m.day ? x : m), undefined)
    return {
      crewId: c.id, name: c.name, role: c.role, status: a.status,
      alerts: a.alerts.map((al) => ({
        rule: al.rule, level: al.level, title: al.title, summary: al.what.summary, exercise: al.exercise, day: al.day,
      })),
      exercises: a.exercises.map((e) => ({
        exercise: e.exercise, status: e.status,
        baseline: e.baseline
          ? { depthDeg: e.baseline.depthDeg, concentricS: e.baseline.concentricS, asymmetryDeg: e.baseline.asymmetryDeg, variabilityDeg: e.baseline.variabilityDeg }
          : null,
        deltas: e.deltas,
      })),
      latestCheckin: latest
        ? { day: latest.day, sleep: latest.sleep, fatigue: latest.fatigue, pain: latest.pain, painLocation: latest.painLocation, stress: latest.stress }
        : null,
    }
  })
  return {
    version: PACKET_VERSION, id: i.id, createdAt: i.now, missionDay: i.day,
    summary: { missionDay: i.day, windowDays: i.windowDays, disclaimer: DISCLAIMER, crew },
    csv: packetCsv(sessions, checkins, i.day, i.windowDays, cfg),
  }
}

/** Serialised size in bytes (what would actually cross the link). */
export function packetSizeBytes(p: DownlinkPacket): number {
  return new TextEncoder().encode(JSON.stringify(p)).length
}

export const formatKb = (bytes: number): string => `${(bytes / 1024).toFixed(1)} KB`

// ---- validation of untrusted packets (BroadcastChannel messages and imported files) --------------

export const MAX_PACKET_CSV_CHARS = 1_000_000
export const MAX_CREW = 50
export const MAX_ALERTS_PER_CREW = 100

const isObj = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)
const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)
const isStatus = (v: unknown): v is Status => v === 'NOMINAL' || v === 'WATCH' || v === 'ACT'

export type ParseResult = { ok: true; packet: DownlinkPacket } | { ok: false; error: string }

/** Strictly validates a value claiming to be a DownlinkPacket. Never throws. */
export function parsePacket(v: unknown): ParseResult {
  const bad = (error: string): ParseResult => ({ ok: false, error })
  if (!isObj(v)) return bad('Not a packet: expected an object.')
  if (v.version !== PACKET_VERSION) return bad(`Unsupported packet version (${String(v.version)}).`)
  if (typeof v.id !== 'string' || !/^[A-Za-z0-9_.:-]{1,80}$/.test(v.id)) return bad('Packet id is missing or malformed.')
  if (!isNum(v.createdAt) || v.createdAt <= 0) return bad('Packet createdAt is invalid.')
  if (!Number.isInteger(v.missionDay) || (v.missionDay as number) < 0 || (v.missionDay as number) > 36_500) return bad('Packet missionDay is invalid.')
  if (typeof v.csv !== 'string') return bad('Packet csv is missing.')
  if (v.csv.length > MAX_PACKET_CSV_CHARS) return bad('Packet csv is too large.')
  const s = v.summary
  if (!isObj(s) || !Array.isArray(s.crew)) return bad('Packet summary is missing.')
  if (s.crew.length > MAX_CREW) return bad('Packet lists too many crew members.')
  for (const c of s.crew) {
    if (!isObj(c) || typeof c.crewId !== 'string' || typeof c.name !== 'string' || !isStatus(c.status)) return bad('A crew entry in the summary is malformed.')
    if (!Array.isArray(c.alerts) || c.alerts.length > MAX_ALERTS_PER_CREW) return bad('A crew entry has invalid alerts.')
    for (const a of c.alerts) {
      if (!isObj(a) || typeof a.title !== 'string' || typeof a.summary !== 'string' || (a.level !== 'WATCH' && a.level !== 'ACT') || !isNum(a.day)) {
        return bad('An alert in the summary is malformed.')
      }
    }
    if (!Array.isArray(c.exercises)) return bad('A crew entry has no exercises list.')
  }
  return { ok: true, packet: v as unknown as DownlinkPacket }
}

/** Parses packet JSON text; returns a readable error instead of throwing. */
export function parsePacketJson(text: string): ParseResult {
  try {
    return parsePacket(JSON.parse(text))
  } catch {
    return { ok: false, error: 'The file is not valid JSON.' }
  }
}

// ---- reading a packet's CSV back (Earth side) ------------------------------------------------------

export interface TrendRow {
  day: number
  crewId: string
  exercise: string
  reps: number
  prescribedReps: number
  depthDeg: number | null
  concentricS: number | null
  asymmetryDeg: number | null
  variabilityDeg: number | null
}

export type CsvResult = { ok: true; rows: TrendRow[] } | { ok: false; error: string }

const optNum = (v: string | undefined): number | null => {
  if (v === undefined || v.trim() === '') return null
  const n = Number(v)
  return Number.isFinite(n) ? n : NaN
}

/** Reads the session rows of a packet CSV. Strict about the header and about every number. */
export function parsePacketCsv(csv: string): CsvResult {
  let rows: string[][]
  try {
    rows = parseCsv(csv)
  } catch (e) {
    return { ok: false, error: e instanceof Error ? e.message : 'Could not read the CSV.' }
  }
  const header = rows[0]?.map((h) => h.trim())
  if (!header || header.join(',') !== CSV_COLUMNS.join(',')) {
    return { ok: false, error: 'Not an OrbitFit downlink CSV: the header does not match the packet format.' }
  }
  const out: TrendRow[] = []
  for (let i = 1; i < rows.length; i++) {
    const r = rows[i] as string[]
    if (r[0] === 'checkin') continue
    if (r[0] !== 'session') return { ok: false, error: `Line ${i + 1}: unknown record type "${r[0] ?? ''}".` }
    const day = Number(r[1])
    const reps = Number(r[4])
    const prescribed = Number(r[5])
    // Columns: 6 depthDeg, 7 concentricS, 8 asymmetryDeg, 9 variabilityDeg (see CSV_COLUMNS).
    const depth = optNum(r[6])
    const con = optNum(r[7])
    const asym = optNum(r[8])
    const variability = optNum(r[9])
    const nums = [day, reps, prescribed, depth, con, asym, variability]
    if (!Number.isInteger(day) || day < 0 || day > 36_500 || !(r[2] ?? '').trim() || nums.some((n) => typeof n === 'number' && Number.isNaN(n))) {
      return { ok: false, error: `Line ${i + 1}: a value is missing or not a number.` }
    }
    out.push({
      day, crewId: (r[2] as string).trim(), exercise: (r[3] ?? '').trim(), reps, prescribedReps: prescribed,
      depthDeg: depth, concentricS: con, asymmetryDeg: asym, variabilityDeg: variability,
    })
  }
  return { ok: true, rows: out }
}

/** Completed / prescribed volume for one session row, in percent (null if nothing was prescribed). */
export const adherencePct = (r: TrendRow): number | null => (r.prescribedReps > 0 ? (100 * r.reps) / r.prescribedReps : null)

/**
 * Combines the session rows of several packets (oldest first) into one series. When two packets
 * contain the same crew member, exercise and day, the later packet wins (it is more up to date).
 */
export function mergeTrends(csvsOldestFirst: string[]): TrendRow[] {
  const byKey = new Map<string, TrendRow>()
  for (const csv of csvsOldestFirst) {
    const parsed = parsePacketCsv(csv)
    if (!parsed.ok) continue
    for (const row of parsed.rows) byKey.set(`${row.crewId}|${row.exercise}|${row.day}`, row)
  }
  return [...byKey.values()].sort((a, b) => a.day - b.day || a.crewId.localeCompare(b.crewId))
}

/** Small deterministic content hash (FNV-1a, 32 bit) used to give CSV-only imports a stable id. */
export function hashText(text: string): string {
  let h = 0x811c9dc5
  for (let i = 0; i < text.length; i++) {
    h ^= text.charCodeAt(i)
    h = Math.imul(h, 0x01000193) >>> 0
  }
  return h.toString(16).padStart(8, '0')
}
