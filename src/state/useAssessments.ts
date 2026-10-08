import { useMemo } from 'react'
import { HEALTH_RULES } from '../config/healthRules'
import { CREW } from '../data/crew'
import { db } from '../db/db'
import { loadSessionRecords } from '../db/repo'
import { assessCrew } from '../engine/changeDetection'
import type { CrewAssessment, SessionRecord } from '../engine/healthTypes'
import { useCheckins } from './useCheckins'
import { useLive } from './useLive'

/** Sessions + reps from the logbook as health-rule input. Re-runs whenever a rep is written. */
export function useSessionRecords(): SessionRecord[] {
  return useLive(() => loadSessionRecords(db)) ?? EMPTY
}
const EMPTY: SessionRecord[] = []

/** Assessments for every crew member as of a mission day, computed from the stored logbook. */
export function useAssessments(day: number): Record<string, CrewAssessment> {
  const records = useSessionRecords()
  const checkins = useCheckins()
  return useMemo(() => {
    const sessions = records.filter((s) => s.day <= day)
    const cis = checkins.filter((c) => c.day <= day)
    return Object.fromEntries(CREW.map((c) => [c.id, assessCrew(sessions, c.id, HEALTH_RULES, cis)]))
  }, [records, checkins, day])
}
