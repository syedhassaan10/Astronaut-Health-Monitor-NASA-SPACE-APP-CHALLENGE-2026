import type { BodyLocation, CheckIn, RepSample, SessionRecord } from '../engine/healthTypes'

// Deterministic demo data: 3 crew x 30 mission days of squat sessions at 0 g (LEO).
// On first run src/db/repo.ts (seedDemoData) writes this into the IndexedDB logbook, which the
// CMO and Crew views read from; "Reset demo data" on /cmo restores it.
//   c1 Rivera : gradual deconditioning (depth, speed, asymmetry, adherence slip)
//   c2 Okafor : nominal (noise only)
//   c3 Tanaka : left/right asymmetry rising

export const DEMO_DAYS = 30
const PRESCRIBED_REPS = 24 // 3 sets x 8

/** Small seeded PRNG so the demo is identical on every device (mulberry32). */
function rng(seed: number) {
  let a = seed >>> 0
  return () => {
    a = (a + 0x6d2b79f5) >>> 0
    let t = a
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** Standard normal sample via Box-Muller. */
function gauss(r: () => number): number {
  const u = Math.max(r(), 1e-9)
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * r())
}

interface Profile {
  crewId: string
  seed: number
  depth: (day: number) => number
  concentric: (day: number) => number
  asymmetry: (day: number) => number
  /** Fraction of prescribed reps actually completed. */
  completion: (day: number) => number
}

const after = (d: number, start: number) => Math.max(0, d - start)

const PROFILES: Profile[] = [
  {
    crewId: 'c1',
    seed: 101,
    depth: (d) => 94 + 0.9 * after(d, 10),
    concentric: (d) => 0.9 * (1 + 0.022 * after(d, 10)),
    asymmetry: (d) => 2.5 + 0.12 * after(d, 12),
    completion: (d) => (d <= 21 ? 1 : Math.max(0.45, 1 - 0.07 * (d - 21))),
  },
  {
    crewId: 'c2',
    seed: 202,
    depth: () => 92,
    concentric: () => 0.85,
    asymmetry: () => 2.2,
    completion: () => 1,
  },
  {
    crewId: 'c3',
    seed: 303,
    depth: () => 96,
    concentric: () => 0.95,
    asymmetry: (d) => 2.8 + 0.4 * after(d, 12),
    completion: () => 1,
  },
]

function makeSession(p: Profile, day: number, r: () => number): SessionRecord {
  const completed = Math.round(PRESCRIBED_REPS * p.completion(day))
  const reps: RepSample[] = Array.from({ length: completed }, () => ({
    minKneeAngle: p.depth(day) + gauss(r) * 2.5,
    eccentricS: Math.max(1, 3.2 + gauss(r) * 0.2),
    concentricS: Math.max(0.3, p.concentric(day) * (1 + gauss(r) * 0.04)),
    asymmetryDeg: Math.max(0, p.asymmetry(day) + gauss(r) * 1.0),
    // ~5% of reps are poor-confidence frames, which the rules must ignore.
    confidence: r() < 0.05 ? 0.35 + r() * 0.15 : 0.86 + r() * 0.11,
  }))
  return { id: `${p.crewId}-d${day}`, crewId: p.crewId, exercise: 'squat', day, gravityG: 0, prescribedReps: PRESCRIBED_REPS, reps }
}

export function generateDemoSessions(): SessionRecord[] {
  const out: SessionRecord[] = []
  for (const p of PROFILES) {
    const r = rng(p.seed)
    for (let day = 1; day <= DEMO_DAYS; day++) out.push(makeSession(p, day, r))
  }
  return out
}

export const DEMO_SESSIONS: SessionRecord[] = generateDemoSessions()

// ---- Daily check-ins (Phase 5) ----------------------------------------------------------
//   c1 Rivera : sleep falls, fatigue and stress climb late in the mission
//   c2 Okafor : steady and well
//   c3 Tanaka : knee pain builds from day 9 (alongside the rising asymmetry)

interface CheckinProfile {
  crewId: string
  seed: number
  sleep: (d: number) => number
  fatigue: (d: number) => number
  pain: (d: number) => number
  painLocation: BodyLocation | null
  stress: (d: number) => number
}

const clamp10 = (x: number) => Math.max(0, Math.min(10, Math.round(x)))

const CHECKIN_PROFILES: CheckinProfile[] = [
  {
    crewId: 'c1', seed: 11,
    sleep: (d) => 7.5 - 0.3 * after(d, 18),
    fatigue: (d) => 3 + 0.45 * after(d, 16),
    pain: () => 0,
    painLocation: null,
    stress: (d) => 3 + 0.25 * after(d, 19),
  },
  {
    crewId: 'c2', seed: 22,
    sleep: () => 7.5, fatigue: () => 3, pain: () => 0, painLocation: null, stress: () => 3,
  },
  {
    crewId: 'c3', seed: 33,
    sleep: () => 7, fatigue: () => 3.5,
    pain: (d) => 0.25 * after(d, 8),
    painLocation: 'knee',
    stress: () => 4,
  },
]

export function generateDemoCheckins(): CheckIn[] {
  const out: CheckIn[] = []
  for (const p of CHECKIN_PROFILES) {
    const r = rng(p.seed)
    for (let day = 1; day <= DEMO_DAYS; day++) {
      const pain = clamp10(p.pain(day) + (p.pain(day) > 0 ? gauss(r) * 0.4 : 0))
      out.push({
        id: `${p.crewId}-ci${day}`, crewId: p.crewId, day,
        sleep: clamp10(p.sleep(day) + gauss(r) * 0.7),
        fatigue: clamp10(p.fatigue(day) + gauss(r) * 0.7),
        pain,
        painLocation: pain > 0 ? p.painLocation : null,
        stress: clamp10(p.stress(day) + gauss(r) * 0.7),
      })
    }
  }
  return out
}

export const DEMO_CHECKINS: CheckIn[] = generateDemoCheckins()
