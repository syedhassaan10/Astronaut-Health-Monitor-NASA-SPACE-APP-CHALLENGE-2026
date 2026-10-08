// Simplified PROTOTYPE model of gravity-dependent resistance training.
// We SIMULATE an ARED-style target; we do not control hardware, and every
// constant below is a demonstration value, not clinically validated.

export type ExerciseId = 'squat' | 'deadlift' | 'heelRaise'

export interface ExerciseSpec {
  id: ExerciseId
  label: string
  /** Fraction of the "missing" body weight the device should replace (0..1). */
  exerciseFactor: number
  /** Training load (kg) prescribed at 1 g, before gravity compensation. */
  baseTrainingLoadKg: number
}

export const EXERCISES: Record<ExerciseId, ExerciseSpec> = {
  squat: { id: 'squat', label: 'Squat', exerciseFactor: 1.0, baseTrainingLoadKg: 40 },
  deadlift: { id: 'deadlift', label: 'Deadlift', exerciseFactor: 0.6, baseTrainingLoadKg: 50 },
  heelRaise: { id: 'heelRaise', label: 'Heel raise', exerciseFactor: 0.8, baseTrainingLoadKg: 20 },
}

export const EXERCISE_IDS = Object.keys(EXERCISES) as ExerciseId[]

/** Standard gravity used by the model (m/s²). */
export const G0 = 9.81
/** Approximate ARED maximum load, ~600 lb ≈ 272 kg. */
export const ARED_MAX_KG = 272

export interface Tempo {
  eccentricS: number
  concentricS: number
  holdS: number
}

export interface VolumeGuidance {
  sessionsPerWeek: number
  sets: number
  reps: number
  minutesPerDay: number
}

export interface Plan {
  g: number
  effectiveBodyweightN: number
  targetLoadKg: number
  capped: boolean
  tempo: Tempo
  volume: VolumeGuidance
}

/** Clamp gravity to the model's valid range, 0..1 g (fraction of Earth). */
export function clampG(g: number): number {
  return Number.isFinite(g) ? Math.min(1, Math.max(0, g)) : 1
}

/** Linear interpolation: returns `atEarth` when g = 1 and `atZero` when g = 0. */
export function lerpByG(g: number, atZero: number, atEarth: number): number {
  const x = clampG(g)
  return atZero + (atEarth - atZero) * x
}

/**
 * Body weight the musculoskeletal system actually carries:
 *   effectiveBodyweightN = massKg × g × 9.81
 */
export function effectiveBodyweightN(massKg: number, g: number): number {
  return massKg * clampG(g) * G0
}

/**
 * Simulated ARED target load. The device must replace the "missing" gravity
 * load, plus the normal training load:
 *   targetLoadKg = massKg × (1 − g) × exerciseFactor + baseTrainingLoadKg
 * capped at ARED_MAX_KG.
 */
export function targetAredLoadKg(massKg: number, g: number, ex: ExerciseSpec): { kg: number; capped: boolean } {
  const raw = massKg * (1 - clampG(g)) * ex.exerciseFactor + ex.baseTrainingLoadKg
  return { kg: Math.min(raw, ARED_MAX_KG), capped: raw > ARED_MAX_KG }
}

/**
 * Tempo / time under tension, interpolated linearly in g:
 *   1 g → 2 s eccentric / 1 s concentric / 0 s hold
 *   0 g → 4 s eccentric / 2 s concentric / 1 s hold
 * Lower g means slower, more controlled reps to keep tension on the muscle.
 */
export function tempoForG(g: number): Tempo {
  return {
    eccentricS: lerpByG(g, 4, 2),
    concentricS: lerpByG(g, 2, 1),
    holdS: lerpByG(g, 1, 0),
  }
}

/**
 * Weekly volume guidance, interpolated linearly in g and rounded:
 *   1 g → 3 sessions/wk, 3 × 8, 30 min/day
 *   0 g → 6 sessions/wk, 4 × 10, 120 min/day (ISS crews exercise ~2 h/day)
 */
export function volumeForG(g: number): VolumeGuidance {
  return {
    sessionsPerWeek: Math.round(lerpByG(g, 6, 3)),
    sets: Math.round(lerpByG(g, 4, 3)),
    reps: Math.round(lerpByG(g, 10, 8)),
    minutesPerDay: Math.round(lerpByG(g, 120, 30)),
  }
}

/** Full prescription for one exercise at gravity g. */
export function buildPlan(massKg: number, g: number, exerciseId: ExerciseId): Plan {
  const ex = EXERCISES[exerciseId]
  const load = targetAredLoadKg(massKg, g, ex)
  return {
    g: clampG(g),
    effectiveBodyweightN: effectiveBodyweightN(massKg, g),
    targetLoadKg: load.kg,
    capped: load.capped,
    tempo: tempoForG(g),
    volume: volumeForG(g),
  }
}
