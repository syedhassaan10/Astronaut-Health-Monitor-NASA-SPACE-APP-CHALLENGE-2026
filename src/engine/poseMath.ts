// Orientation-independent joint angles from MediaPipe 3D WORLD landmarks.
// World landmarks are metric (metres) with the origin at the hip centre, and the
// angle between two bone vectors is invariant to rotation, so nothing here uses
// the screen's "up" direction or vertical position (safe in microgravity).

export interface Vec3 {
  x: number
  y: number
  z: number
  visibility?: number
}

/** MediaPipe Pose landmark indices used by OrbitFit. */
export const LM = {
  L_SHOULDER: 11, R_SHOULDER: 12,
  L_HIP: 23, R_HIP: 24,
  L_KNEE: 25, R_KNEE: 26,
  L_ANKLE: 27, R_ANKLE: 28,
  L_FOOT: 31, R_FOOT: 32,
} as const

/** Landmarks that must be visible for a lower-body measurement to be trusted. */
export const KEY_LANDMARKS: number[] = [11, 12, 23, 24, 25, 26, 27, 28]

/**
 * Interior angle (degrees) at joint b between segments b→a and b→c:
 *   θ = acos( (a−b)·(c−b) / (|a−b| |c−b|) )
 * 180° = fully extended, smaller = more flexed. Returns null for degenerate input.
 */
export function angleDeg(a: Vec3, b: Vec3, c: Vec3): number | null {
  const ux = a.x - b.x, uy = a.y - b.y, uz = a.z - b.z
  const vx = c.x - b.x, vy = c.y - b.y, vz = c.z - b.z
  const nu = Math.hypot(ux, uy, uz)
  const nv = Math.hypot(vx, vy, vz)
  if (nu < 1e-6 || nv < 1e-6) return null
  const cos = (ux * vx + uy * vy + uz * vz) / (nu * nv)
  return (Math.acos(Math.max(-1, Math.min(1, cos))) * 180) / Math.PI
}

export interface JointAngles {
  kneeL: number
  kneeR: number
  /** Mean of left and right knee angles. */
  knee: number
  hipL: number
  hipR: number
  ankleL: number
  ankleR: number
}

/** Knee (hip-knee-ankle), hip (shoulder-hip-knee) and ankle (knee-ankle-toe) angles. */
export function jointAngles(w: Vec3[]): JointAngles | null {
  const p = (i: number) => w[i]
  const g = (a: number, b: number, c: number): number | null => {
    const A = p(a), B = p(b), C = p(c)
    return A && B && C ? angleDeg(A, B, C) : null
  }
  const kneeL = g(LM.L_HIP, LM.L_KNEE, LM.L_ANKLE)
  const kneeR = g(LM.R_HIP, LM.R_KNEE, LM.R_ANKLE)
  const hipL = g(LM.L_SHOULDER, LM.L_HIP, LM.L_KNEE)
  const hipR = g(LM.R_SHOULDER, LM.R_HIP, LM.R_KNEE)
  const ankleL = g(LM.L_KNEE, LM.L_ANKLE, LM.L_FOOT)
  const ankleR = g(LM.R_KNEE, LM.R_ANKLE, LM.R_FOOT)
  if (kneeL === null || kneeR === null || hipL === null || hipR === null || ankleL === null || ankleR === null) return null
  return { kneeL, kneeR, knee: (kneeL + kneeR) / 2, hipL, hipR, ankleL, ankleR }
}

/** Mean landmark visibility (0..1) over the given indices; 0 if none are present. */
export function meanVisibility(lms: Vec3[], idx: number[] = KEY_LANDMARKS): number {
  let sum = 0
  for (const i of idx) sum += lms[i]?.visibility ?? 0
  return idx.length ? sum / idx.length : 0
}
