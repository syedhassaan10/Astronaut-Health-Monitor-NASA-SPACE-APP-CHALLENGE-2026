// Rolling performance statistics for the HUD and the benchmark.
export interface PerfSnapshot {
  cameraFps: number
  inferencePerSec: number
  avgInferenceMs: number
  frames: number
  inferences: number
  /** Share of frames on which inference was skipped, 0..100. */
  skippedPct: number
  /** Estimated inference time saved vs running every frame (ms). */
  savedMs: number
}

const WINDOW_MS = 2000

export class PerfStats {
  private frameTimes: number[] = []
  private infTimes: number[] = []
  private frames = 0
  private inferences = 0
  private infMsTotal = 0
  /** Inferences whose duration is included in the average (the first one is warm-up). */
  private timed = 0

  reset(): void {
    this.frameTimes = []
    this.infTimes = []
    this.frames = this.inferences = 0
    this.infMsTotal = 0
    this.timed = 0
  }

  private trim(arr: number[], now: number): void {
    while (arr.length && now - (arr[0] ?? now) > WINDOW_MS) arr.shift()
  }

  onFrame(now: number): void {
    this.frames += 1
    this.frameTimes.push(now)
    this.trim(this.frameTimes, now)
  }

  onInference(now: number, ms: number): void {
    this.inferences += 1
    // The first call after a reset pays one-off model/GPU warm-up; keep it out of the
    // average so the HUD and benchmark reflect steady-state cost.
    if (this.inferences > 1) {
      this.infMsTotal += ms
      this.timed += 1
    }
    this.infTimes.push(now)
    this.trim(this.infTimes, now)
  }

  snapshot(now: number): PerfSnapshot {
    this.trim(this.frameTimes, now)
    this.trim(this.infTimes, now)
    const rate = (a: number[]) => (a.length > 1 ? ((a.length - 1) * 1000) / ((a[a.length - 1] ?? 0) - (a[0] ?? 0) || 1) : 0)
    const avg = this.timed ? this.infMsTotal / this.timed : 0
    return {
      cameraFps: rate(this.frameTimes),
      inferencePerSec: rate(this.infTimes),
      avgInferenceMs: avg,
      frames: this.frames,
      inferences: this.inferences,
      skippedPct: this.frames ? (100 * (this.frames - this.inferences)) / this.frames : 0,
      savedMs: (this.frames - this.inferences) * avg,
    }
  }
}
