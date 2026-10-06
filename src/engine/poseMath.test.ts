import { describe, expect, it } from 'vitest'
import { LM, angleDeg, jointAngles, meanVisibility, type Vec3 } from './poseMath'

const v = (x: number, y: number, z: number, visibility = 1): Vec3 => ({ x, y, z, visibility })

/** Rotate a point about an arbitrary axis (Rodrigues) to test orientation independence. */
function rotate(p: Vec3, axis: Vec3, rad: number): Vec3 {
  const n = Math.hypot(axis.x, axis.y, axis.z)
  const k = { x: axis.x / n, y: axis.y / n, z: axis.z / n }
  const c = Math.cos(rad), s = Math.sin(rad)
  const dot = k.x * p.x + k.y * p.y + k.z * p.z
  const cr = { x: k.y * p.z - k.z * p.y, y: k.z * p.x - k.x * p.z, z: k.x * p.y - k.y * p.x }
  return {
    x: p.x * c + cr.x * s + k.x * dot * (1 - c),
    y: p.y * c + cr.y * s + k.y * dot * (1 - c),
    z: p.z * c + cr.z * s + k.z * dot * (1 - c),
    visibility: p.visibility,
  }
}

describe('angleDeg', () => {
  it('straight line = 180°, right angle = 90°, folded = 0°', () => {
    expect(angleDeg(v(0, 1, 0), v(0, 0, 0), v(0, -1, 0))).toBeCloseTo(180, 6)
    expect(angleDeg(v(1, 0, 0), v(0, 0, 0), v(0, 1, 0))).toBeCloseTo(90, 6)
    expect(angleDeg(v(1, 0, 0), v(0, 0, 0), v(2, 0, 0))).toBeCloseTo(0, 4)
  })
  it('returns null for coincident points', () => {
    expect(angleDeg(v(0, 0, 0), v(0, 0, 0), v(1, 0, 0))).toBeNull()
  })
})

function pose(): Vec3[] {
  const w: Vec3[] = Array.from({ length: 33 }, () => v(0, 0, 0))
  // Left and right legs as 90° knee bends (hip → knee → ankle), 45° trunk lean.
  w[LM.L_SHOULDER] = v(-0.2, -0.5, 0.1); w[LM.R_SHOULDER] = v(0.2, -0.5, 0.1)
  w[LM.L_HIP] = v(-0.1, 0, 0); w[LM.R_HIP] = v(0.1, 0, 0)
  w[LM.L_KNEE] = v(-0.1, 0, 0.4); w[LM.R_KNEE] = v(0.1, 0, 0.4)
  w[LM.L_ANKLE] = v(-0.1, 0.4, 0.4); w[LM.R_ANKLE] = v(0.1, 0.4, 0.4)
  w[LM.L_FOOT] = v(-0.1, 0.4, 0.6); w[LM.R_FOOT] = v(0.1, 0.4, 0.6)
  return w
}

describe('jointAngles', () => {
  it('computes a 90° knee', () => {
    const a = jointAngles(pose())
    expect(a?.kneeL).toBeCloseTo(90, 5)
    expect(a?.kneeR).toBeCloseTo(90, 5)
    expect(a?.knee).toBeCloseTo(90, 5)
  })

  it('is orientation-independent: any 3D rotation (e.g. floating upside down) gives the same angles', () => {
    const base = jointAngles(pose())!
    for (const [axis, rad] of [
      [v(1, 0, 0), Math.PI], // upside down
      [v(0, 0, 1), 1.3],
      [v(1, 2, 3), 2.7],
    ] as const) {
      const r = jointAngles(pose().map((p) => rotate(p, axis, rad)))!
      expect(r.knee).toBeCloseTo(base.knee, 5)
      expect(r.hipL).toBeCloseTo(base.hipL, 5)
      expect(r.ankleR).toBeCloseTo(base.ankleR, 5)
    }
  })

  it('returns null when landmarks are missing', () => {
    expect(jointAngles([])).toBeNull()
  })
})

describe('meanVisibility', () => {
  it('averages the key landmark visibilities', () => {
    const w = pose()
    for (const i of [11, 12, 23, 24]) w[i] = v(0, 0, 0, 0.2)
    expect(meanVisibility(w)).toBeCloseTo((4 * 0.2 + 4 * 1) / 8, 9)
  })
})
