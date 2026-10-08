import { HEALTH_RULES, type HealthRulesConfig } from '../config/healthRules'
import { assessCrew } from './changeDetection'
import type { Alert, CheckIn, SessionRecord } from './healthTypes'

/** A log entry is written the first time an alert appears at a given level (so escalations log too). */
export interface AlertLogEntry {
  key: string
  crewId: string
  exercise: Alert['exercise']
  rule: Alert['rule']
  level: Alert['level']
  title: string
  summary: string
  day: number
}

export const alertKey = (a: Pick<Alert, 'id' | 'level'>): string => `${a.id}|${a.level}`

export function toLogEntry(a: Alert, day: number): AlertLogEntry {
  return {
    key: alertKey(a),
    crewId: a.crewId,
    exercise: a.exercise,
    rule: a.rule,
    level: a.level,
    title: a.title,
    summary: a.what.summary,
    day,
  }
}

/** Entries for alerts whose key is not in `known` yet. */
export function newLogEntries(alerts: Alert[], known: ReadonlySet<string>, day: number): AlertLogEntry[] {
  return alerts.filter((a) => !known.has(alertKey(a))).map((a) => toLogEntry(a, day))
}

/**
 * Replays mission days 1..toDay and records the first day each alert (per level) appeared.
 * Used to build the alert log from stored history.
 */
export function replayAlertLog(
  sessions: SessionRecord[], checkins: CheckIn[], crewIds: string[], toDay: number, cfg: HealthRulesConfig = HEALTH_RULES,
): AlertLogEntry[] {
  const seen = new Map<string, AlertLogEntry>()
  for (let day = 1; day <= toDay; day++) {
    const s = sessions.filter((x) => x.day <= day)
    const c = checkins.filter((x) => x.day <= day)
    for (const crewId of crewIds) {
      for (const a of assessCrew(s, crewId, cfg, c).alerts) {
        const key = alertKey(a)
        if (!seen.has(key)) seen.set(key, toLogEntry(a, day))
      }
    }
  }
  return [...seen.values()].sort((a, b) => a.day - b.day || a.key.localeCompare(b.key))
}
