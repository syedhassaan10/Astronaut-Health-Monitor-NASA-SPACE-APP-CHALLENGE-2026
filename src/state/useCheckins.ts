import { useMemo, useSyncExternalStore } from 'react'
import { SEED_CHECKINS, getUserCheckins, mergeCheckins, subscribe } from './checkinStore'
import type { CheckIn } from '../engine/healthTypes'

/** All check-ins (seeded + user entered), live-updating when a check-in is saved. */
export function useCheckins(): CheckIn[] {
  const user = useSyncExternalStore(subscribe, getUserCheckins, getUserCheckins)
  return useMemo(() => mergeCheckins(SEED_CHECKINS, user), [user])
}
