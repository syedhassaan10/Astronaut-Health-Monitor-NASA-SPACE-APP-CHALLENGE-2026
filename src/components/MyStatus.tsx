import AlertCard from './AlertCard'
import StatusBadge from './StatusBadge'
import { DEMO_DAYS } from '../data/demoSeed'
import { useAssessments } from '../state/useAssessments'

/** The astronaut's own trend status (seeded demo data until the logbook lands in Phase 6). */
export default function MyStatus({ crewId }: { crewId: string }) {
  const a = useAssessments(DEMO_DAYS)[crewId]
  if (!a) return null
  return (
    <section className="panel" aria-label="My trend status">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-semibold">My trend status</h2>
        <StatusBadge status={a.status} large />
        <span className="label-mono ml-auto">estimate · decision support · mission day {DEMO_DAYS} (seeded demo data)</span>
      </div>
      {a.alerts.length === 0 ? (
        <p className="text-sm text-ink-300 mt-2">
          No active alerts. Your depth, speed, symmetry, consistency and exercise volume are within your personal baseline.
        </p>
      ) : (
        <div className="mt-3 space-y-3">{a.alerts.map((al) => <AlertCard key={al.id} alert={al} compact />)}</div>
      )}
    </section>
  )
}
