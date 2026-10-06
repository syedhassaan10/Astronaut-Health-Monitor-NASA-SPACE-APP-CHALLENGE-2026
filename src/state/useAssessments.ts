import { useMemo } from 'react'
import { CREW } from '../data/crew'
import { DEMO_SESSIONS } from '../data/demoSeed'
import { assessCrew } from '../engine/changeDetection'
import type { CrewAssessment } from '../engine/healthTypes'

/**
 * Assessments for every crew member as of a mission day, computed from the seeded demo
 * sessions (Phase 6 swaps the source for the IndexedDB logbook).
 */
export function useAssessments(day: number): Record<string, CrewAssessment> {
  return useMemo(() => {
    const upTo = DEMO_SESSIONS.filter((s) => s.day <= day)
    return Object.fromEntries(CREW.map((c) => [c.id, assessCrew(upTo, c.id)]))
  }, [day])
}
