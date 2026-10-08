import { describe, expect, it } from 'vitest'
import {
  ARED_MAX_KG, EXERCISES, buildPlan, clampG, effectiveBodyweightN, targetAredLoadKg, tempoForG, volumeForG,
} from './gravityEngine'

describe('gravityEngine', () => {
  it('clamps gravity to 0..1 and handles NaN', () => {
    expect(clampG(-1)).toBe(0)
    expect(clampG(2)).toBe(1)
    expect(clampG(NaN)).toBe(1)
  })

  it('effective bodyweight = m·g·9.81', () => {
    expect(effectiveBodyweightN(70, 1)).toBeCloseTo(686.7, 5)
    expect(effectiveBodyweightN(70, 0)).toBe(0)
    expect(effectiveBodyweightN(70, 0.38)).toBeCloseTo(70 * 0.38 * 9.81, 5)
  })

  it('target load at 1 g equals the base training load', () => {
    expect(targetAredLoadKg(80, 1, EXERCISES.squat).kg).toBe(40)
  })

  it('target load at 0 g adds the full missing bodyweight × factor', () => {
    expect(targetAredLoadKg(70, 0, EXERCISES.squat).kg).toBe(110)
    expect(targetAredLoadKg(70, 0, EXERCISES.deadlift).kg).toBeCloseTo(70 * 0.6 + 50, 9)
  })

  it('target load decreases monotonically as g increases', () => {
    const a = targetAredLoadKg(75, 0.1, EXERCISES.heelRaise).kg
    const b = targetAredLoadKg(75, 0.6, EXERCISES.heelRaise).kg
    expect(a).toBeGreaterThan(b)
  })

  it('caps at the ARED maximum', () => {
    const r = targetAredLoadKg(500, 0, EXERCISES.squat)
    expect(r.kg).toBe(ARED_MAX_KG)
    expect(r.capped).toBe(true)
    expect(targetAredLoadKg(70, 0, EXERCISES.squat).capped).toBe(false)
  })

  it('tempo matches the 1 g and 0 g anchors and interpolates linearly', () => {
    expect(tempoForG(1)).toEqual({ eccentricS: 2, concentricS: 1, holdS: 0 })
    expect(tempoForG(0)).toEqual({ eccentricS: 4, concentricS: 2, holdS: 1 })
    const mid = tempoForG(0.5)
    expect(mid.eccentricS).toBeCloseTo(3, 9)
    expect(mid.concentricS).toBeCloseTo(1.5, 9)
    expect(mid.holdS).toBeCloseTo(0.5, 9)
  })

  it('weekly volume rises as gravity falls', () => {
    expect(volumeForG(1)).toEqual({ sessionsPerWeek: 3, sets: 3, reps: 8, minutesPerDay: 30 })
    expect(volumeForG(0)).toEqual({ sessionsPerWeek: 6, sets: 4, reps: 10, minutesPerDay: 120 })
    expect(volumeForG(0.166).minutesPerDay).toBeGreaterThan(volumeForG(0.38).minutesPerDay)
  })

  it('buildPlan combines all pieces', () => {
    const p = buildPlan(70, 0, 'squat')
    expect(p.targetLoadKg).toBe(110)
    expect(p.effectiveBodyweightN).toBe(0)
    expect(p.tempo.holdS).toBe(1)
  })
})
