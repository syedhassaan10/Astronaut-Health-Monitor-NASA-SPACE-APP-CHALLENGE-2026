import { Link } from 'react-router-dom'
import type { PerfSnapshot } from '../engine/perfStats'
import type { SamplingMode } from '../engine/adaptiveSampler'
import type { BenchResult } from '../data/benchmark'
import type { BenchState } from '../pose/useMeasurement'

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 py-1 border-b border-space-700 last:border-0">
      <dt className="text-ink-300">{label}</dt>
      <dd className="font-mono">{value}</dd>
    </div>
  )
}

export default function PerfHud({
  stats, mode, bench, benchResult, canBench, onBench,
}: {
  stats: PerfSnapshot | null
  mode: SamplingMode
  bench: BenchState | null
  benchResult: BenchResult | null
  canBench: boolean
  onBench: () => void
}) {
  const s = stats
  return (
    <div className="bg-space-900 border border-space-700 rounded-lg p-3 text-sm" aria-label="Performance HUD">
      <p className="label-mono mb-1">Performance · {mode === 'adaptive' ? 'adaptive' : 'full'} sampling</p>
      <dl>
        <Row label="Camera FPS" value={s ? s.cameraFps.toFixed(1) : '—'} />
        <Row label="Inference calls / s" value={s ? s.inferencePerSec.toFixed(1) : '—'} />
        <Row label="Avg inference" value={s ? `${s.avgInferenceMs.toFixed(1)} ms` : '—'} />
        <Row label="Frames skipped" value={s ? `${s.skippedPct.toFixed(0)} %` : '—'} />
        <Row label="Est. compute saved vs Full" value={s ? `${(s.savedMs / 1000).toFixed(1)} s (${s.skippedPct.toFixed(0)} %)` : '—'} />
      </dl>
      <div className="mt-3 flex flex-wrap items-center gap-3">
        <button type="button" onClick={onBench} disabled={!canBench || bench !== null}
          className="px-3 py-1.5 rounded-md text-sm border border-space-600 hover:bg-space-700 disabled:opacity-40">
          Run 30 s benchmark
        </button>
        {bench && (
          <span role="status" className="font-mono text-xs text-accent">
            {bench.phase === 'full' ? 'Leg 1/2: Full' : 'Leg 2/2: Adaptive'} · {bench.elapsedS.toFixed(0)}/30 s — keep exercising
          </span>
        )}
      </div>
      {benchResult && (
        <p className="mt-2 text-xs text-ink-300">
          Result: <span className="font-mono text-nominal">{benchResult.reductionPct.toFixed(0)} % fewer inference calls</span> with Adaptive
          (reps {benchResult.full.reps} Full vs {benchResult.adaptive.reps} Adaptive). Saved — table on{' '}
          <Link className="text-accent underline" to="/about#benchmark">/about</Link>.
        </p>
      )}
    </div>
  )
}
