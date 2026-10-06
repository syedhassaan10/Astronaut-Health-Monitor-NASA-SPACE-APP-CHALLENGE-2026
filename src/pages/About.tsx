import { useEffect, useState } from 'react'
import { useLocation } from 'react-router-dom'
import Page from '../components/Page'
import { loadBenchmark, type BenchRow } from '../data/benchmark'
import { DEFAULT_SAMPLER } from '../engine/adaptiveSampler'

function BenchLine({ label, r }: { label: string; r: BenchRow }) {
  return (
    <tr className="border-t border-space-700">
      <td className="py-1.5 pr-4">{label}</td>
      <td className="pr-4">{r.frames}</td>
      <td className="pr-4">{r.inferences}</td>
      <td className="pr-4">{r.avgInferenceMs.toFixed(1)} ms</td>
      <td>{r.reps}</td>
    </tr>
  )
}

export default function About() {
  const { hash } = useLocation()
  const [bench] = useState(loadBenchmark)
  useEffect(() => {
    if (hash) document.getElementById(hash.slice(1))?.scrollIntoView({ block: 'start' })
  }, [hash])
  return (
    <Page title="About OrbitFit" subtitle="Problem, solution, hazards, limitations.">
      <div className="panel text-sm text-ink-300">
        OrbitFit helps astronauts notice changes in their own musculoskeletal health using only a camera, offline. Full content arrives in Phase 8.
      </div>

      <section id="benchmark" className="panel">
        <h2 className="font-semibold">Adaptive sampling benchmark</h2>
        <p className="text-sm text-ink-300 mt-1">
          Adaptive mode runs pose inference every {DEFAULT_SAMPLER.baseStride}th frame and on every frame for {DEFAULT_SAMPLER.burstMs} ms
          around each turning point of the knee angle. Run the 30-second benchmark on the Crew page to fill this table.
        </p>
        {bench ? (
          <div className="mt-3 overflow-x-auto">
            <table className="text-sm font-mono text-left">
              <thead className="text-ink-500">
                <tr><th className="pr-4">Mode</th><th className="pr-4">Frames</th><th className="pr-4">Inference calls</th><th className="pr-4">Avg inference</th><th>Reps</th></tr>
              </thead>
              <tbody>
                <BenchLine label="Full (every frame)" r={bench.full} />
                <BenchLine label="Adaptive" r={bench.adaptive} />
              </tbody>
            </table>
            <p className="mt-2 text-sm">
              <span className="text-nominal font-mono">{bench.reductionPct.toFixed(0)} % fewer inference calls</span> per frame with Adaptive.
              Source: {bench.source} · {new Date(bench.when).toLocaleString()}
            </p>
          </div>
        ) : (
          <p className="mt-3 text-sm text-ink-500">No benchmark has been run on this device yet.</p>
        )}
      </section>
    </Page>
  )
}
