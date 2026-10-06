import { LOCATION_LABEL } from '../engine/checkinRules'
import type { CheckIn } from '../engine/healthTypes'

/** One-line summary of the latest check-in, shown next to the exercise status. */
export default function CheckinSummary({ checkin }: { checkin: CheckIn | undefined }) {
  if (!checkin) return <p className="text-xs text-ink-500">No check-in yet.</p>
  const chip = 'bg-space-900 border border-space-700 rounded px-1.5 py-0.5 font-mono text-xs'
  return (
    <p className="flex flex-wrap items-center gap-1.5 text-xs" aria-label={`Latest check-in, day ${checkin.day}`}>
      <span className="label-mono mr-1">Check-in d{checkin.day}</span>
      <span className={chip}>Sleep {checkin.sleep}</span>
      <span className={chip}>Fatigue {checkin.fatigue}</span>
      <span className={chip}>
        Pain {checkin.pain}{checkin.painLocation ? ` (${LOCATION_LABEL[checkin.painLocation]})` : ''}
      </span>
      <span className={chip}>Stress {checkin.stress}</span>
    </p>
  )
}
