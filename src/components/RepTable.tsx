import { LEVEL_COLOR } from '../pose/drawOverlay'
import type { RepRecord } from '../pose/useMeasurement'

const f = (n: number, d = 1) => n.toFixed(d)

export default function RepTable({ reps, partials, rejected, exerciseLabel }: { reps: RepRecord[]; partials: number; rejected: number; exerciseLabel: string }) {
  const shown = reps.slice(-8).reverse()
  return (
    <div className="bg-space-900 border border-space-700 rounded-lg p-3 text-sm" aria-label="Rep log">
      <p className="label-mono mb-1">{exerciseLabel} reps · {reps.length} counted</p>
      {shown.length === 0 ? (
        <p className="text-ink-500">No reps yet. Reps appear here as soon as each one completes.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left font-mono text-xs">
            <thead className="text-ink-500">
              <tr><th className="pr-2">#</th><th className="pr-2">Depth</th><th className="pr-2">Ecc</th><th className="pr-2">Con</th><th className="pr-2">L/R Δ</th><th className="pr-2">Conf</th><th>Form</th></tr>
            </thead>
            <tbody>
              {shown.map((r) => (
                <tr key={r.repNo} className="border-t border-space-700">
                  <td className="pr-2 py-1">{r.repNo}</td>
                  <td className="pr-2">{f(r.minKneeAngle, 0)}°</td>
                  <td className="pr-2">{f(r.eccentricS)}s</td>
                  <td className="pr-2">{f(r.concentricS)}s</td>
                  <td className="pr-2">{f(r.asymmetryDeg)}°</td>
                  <td className="pr-2">{f(r.confidence * 100, 0)}%</td>
                  <td style={{ color: LEVEL_COLOR[r.assessment.overall] }} title={r.assessment.flags.join(', ') || 'good form'}>
                    ● {r.assessment.score}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {(partials > 0 || rejected > 0) && (
        <p className="mt-2 text-xs text-ink-300">
          Not counted: {partials} partial (never reached depth gate) · {rejected} rejected (low confidence — measurement unreliable).
        </p>
      )}
    </div>
  )
}
