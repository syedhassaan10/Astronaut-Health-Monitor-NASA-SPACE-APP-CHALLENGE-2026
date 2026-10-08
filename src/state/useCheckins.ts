import { db } from '../db/db'
import type { CheckIn } from '../engine/healthTypes'
import { useLive } from './useLive'

/** All check-ins from the logbook, live-updating when one is saved (here or in another tab). */
export function useCheckins(): CheckIn[] {
  return useLive(() => db.checkins.toArray()) ?? EMPTY
}

const EMPTY: CheckIn[] = []
