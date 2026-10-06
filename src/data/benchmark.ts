// Benchmark results (Full vs Adaptive) are stored locally and shown on /about.
export interface BenchRow {
  mode: 'full' | 'adaptive'
  seconds: number
  frames: number
  inferences: number
  avgInferenceMs: number
  reps: number
}

export interface BenchResult {
  when: string
  source: string
  full: BenchRow
  adaptive: BenchRow
  /** % fewer inference calls in adaptive vs full. */
  reductionPct: number
}

const KEY = 'orbitfit.benchmark'

export function loadBenchmark(): BenchResult | null {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? (JSON.parse(raw) as BenchResult) : null
  } catch {
    return null
  }
}

export function saveBenchmark(r: BenchResult): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(r))
  } catch {
    /* storage unavailable: the table is still shown for this session */
  }
}

export function makeBenchResult(source: string, full: BenchRow, adaptive: BenchRow): BenchResult {
  // Compare inference calls per camera frame, so a slower Full run (which may drop
  // frames when inference is slower than the camera) does not flatter the result.
  const perFrame = (r: BenchRow) => (r.frames ? r.inferences / r.frames : 0)
  const reductionPct = perFrame(full) ? 100 * (1 - perFrame(adaptive) / perFrame(full)) : 0
  return { when: new Date().toISOString(), source, full, adaptive, reductionPct }
}
