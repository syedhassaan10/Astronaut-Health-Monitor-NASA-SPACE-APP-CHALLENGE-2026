import { CREW } from '../data/crew'
import { db } from '../db/db'
import { setAcknowledged } from '../db/repo'
import { EXERCISES } from '../engine/gravityEngine'
import { useLive } from '../state/useLive'
import StatusBadge from './StatusBadge'

/** Chronological record of every alert raised (newest first). Acknowledgement is stored in the logbook. */
export default function AlertLog() {
  const rows = useLive(() => db.alerts.orderBy('day').reverse().toArray())
  if (!rows) return <p className="text-sm text-ink-500">Loading alert log…</p>
  if (rows.length === 0) return <div className="panel text-sm text-ink-300">No alerts have been raised yet.</div>
  return (
    <div className="panel overflow-x-auto" aria-label="Alert log">
      <table className="w-full text-sm text-left">
        <thead className="label-mono">
          <tr>
            <th className="pr-3 py-1">Day</th><th className="pr-3">Crew</th><th className="pr-3">Level</th>
            <th className="pr-3">Alert</th><th className="pr-3">Detail</th><th>Ack</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.key} className={`border-t border-space-700 align-top ${r.acknowledged ? 'opacity-60' : ''}`}>
              <td className="pr-3 py-1.5 font-mono">{r.day}</td>
              <td className="pr-3 whitespace-nowrap">{CREW.find((c) => c.id === r.crewId)?.name ?? r.crewId}</td>
              <td className="pr-3"><StatusBadge status={r.level} /></td>
              <td className="pr-3">
                {r.title}
                <span className="block text-xs text-ink-500">{r.exercise ? EXERCISES[r.exercise].label : 'Daily check-in'}</span>
              </td>
              <td className="pr-3 text-ink-300 min-w-64">{r.summary}</td>
              <td>
                <input type="checkbox" checked={r.acknowledged} aria-label={`Acknowledge: ${r.title}, day ${r.day}`}
                  onChange={(e) => void setAcknowledged(r.key, e.target.checked)} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
