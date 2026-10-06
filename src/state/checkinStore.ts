import { DEMO_CHECKINS, DEMO_DAYS } from '../data/demoSeed'
import type { CheckIn } from '../engine/healthTypes'

// Check-ins the user enters live in localStorage for now; Phase 6 moves them into the
// IndexedDB `checkins` table behind this same small API.
const KEY = 'orbitfit.checkins'

/** The mission day a newly saved check-in is stamped with (the latest seeded day). */
export const TODAY = DEMO_DAYS

let cache: CheckIn[] | null = null
const listeners = new Set<() => void>()

function read(): CheckIn[] {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as CheckIn[]) : []
  } catch {
    return [] // storage blocked: the app still works for this session
  }
}

export function getUserCheckins(): CheckIn[] {
  cache ??= read()
  return cache
}

function write(next: CheckIn[]): void {
  cache = next
  try {
    localStorage.setItem(KEY, JSON.stringify(next))
  } catch {
    /* keep the in-memory copy */
  }
  listeners.forEach((l) => l())
}

/** One check-in per crew member per day: saving again replaces it. */
export function saveCheckin(c: Omit<CheckIn, 'id'>): void {
  const id = `user-${c.crewId}-d${c.day}`
  write([...getUserCheckins().filter((x) => !(x.crewId === c.crewId && x.day === c.day)), { ...c, id }])
}

export function clearUserCheckins(): void {
  write([])
}

export function subscribe(l: () => void): () => void {
  listeners.add(l)
  return () => listeners.delete(l)
}

/** Seeded history plus user entries; a user entry replaces the seeded one for the same crew + day. */
export function mergeCheckins(seed: CheckIn[], user: CheckIn[]): CheckIn[] {
  const key = (c: CheckIn) => `${c.crewId}:${c.day}`
  const taken = new Set(user.map(key))
  return [...seed.filter((c) => !taken.has(key(c))), ...user]
}

export const SEED_CHECKINS = DEMO_CHECKINS
