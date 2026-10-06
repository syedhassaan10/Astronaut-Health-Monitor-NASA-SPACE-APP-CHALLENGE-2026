import { describe, expect, it } from 'vitest'
import { PerfStats } from './perfStats'

describe('PerfStats', () => {
  it('computes fps, inference rate, skipped % and saved time', () => {
    const p = new PerfStats()
    // 30 fps for 1 s (31 frames), inference on every 6th frame.
    for (let i = 0; i <= 30; i++) {
      const t = i * (1000 / 30)
      p.onFrame(t)
      if (i % 6 === 0) p.onInference(t, 10)
    }
    const s = p.snapshot(1000)
    expect(s.cameraFps).toBeCloseTo(30, 0)
    expect(s.frames).toBe(31)
    expect(s.inferences).toBe(6)
    expect(s.skippedPct).toBeCloseTo((100 * 25) / 31, 5)
    expect(s.avgInferenceMs).toBeCloseTo(10, 5)
    expect(s.savedMs).toBeCloseTo(25 * 10, 5)
  })

  it('excludes the first (warm-up) inference from the average', () => {
    const p = new PerfStats()
    p.onFrame(0)
    p.onInference(0, 500) // warm-up
    p.onInference(100, 10)
    p.onInference(200, 20)
    expect(p.snapshot(200).avgInferenceMs).toBeCloseTo(15, 9)
    expect(p.snapshot(200).inferences).toBe(3)
  })

  it('reset clears everything', () => {
    const p = new PerfStats()
    p.onFrame(0)
    p.onInference(0, 5)
    p.reset()
    const s = p.snapshot(0)
    expect(s.frames).toBe(0)
    expect(s.inferences).toBe(0)
    expect(s.avgInferenceMs).toBe(0)
  })
})
