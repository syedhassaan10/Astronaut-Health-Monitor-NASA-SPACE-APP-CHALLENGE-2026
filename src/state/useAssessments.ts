import { useMemo } from 'react'
import { CREW } from '../data/crew'
import { DEMO_SESSIONS } from '../data/demoSeed'
import { assessCrew } from '../engine/changeDetection'
import { HEALTH_RULES } from '../config/healthRules'
import type { CrewAssessment } from '../engine/healthTypes'
import { useCheckins } from './useCheckins'

/**
 * Assessments for every crew member as of a mission day, from the seeded demo sessions and
 * the daily check-ins (Phase 6 swaps the session source for the IndexedDB logbook).
 */
export function useAssessments(day: number): Record<string, CrewAssessment> {
  const checkins = useCheckins()
  return useMemo(() => {
    const sessions = DEMO_SESSIONS.filter((s) => s.day <= day)
    const cis = checkins.filter((c) => c.day <= day)
    return Object.fromEntries(CREW.map((c) => [c.id, assessCrew(sessions, c.id, HEALTH_RULES, cis)]))
  }, [day, checkins])
}
