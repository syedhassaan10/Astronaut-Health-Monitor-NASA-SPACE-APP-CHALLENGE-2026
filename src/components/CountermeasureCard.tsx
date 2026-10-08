import type { ReactNode } from 'react'
import { EXERCISES, type ExerciseId, buildPlan } from '../engine/gravityEngine'
import WhyTip from './WhyTip'

function Stat({ label, value, unit, why }: { label: string; value: string; unit?: string; why: ReactNode }) {
  return (
    <div className="bg-space-900 border border-space-700 rounded-lg p-3">
      <p className="label-mono">{label}</p>
      <p className="mt-1 text-2xl font-mono">
        {value}
        {unit && <span className="text-sm text-ink-500 ml-1">{unit}</span>}
        {why}
      </p>
    </div>
  )
}

const f1 = (n: number) => n.toFixed(1)

export default function CountermeasureCard({ massKg, g, exercise }: { massKg: number; g: number; exercise: ExerciseId }) {
  const plan = buildPlan(massKg, g, exercise)
  const ex = EXERCISES[exercise]
  const v = plan.volume
  return (
    <section className="panel" aria-label="Simulated ARED target load">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">Simulated ARED target load</h2>
        <span className="label-mono">simplified prototype model · simulated device</span>
      </div>
      <p className="text-sm text-ink-300 mt-1">
        {ex.label} at {g.toFixed(3)} g for a {massKg} kg crew member. We simulate the device; we do not control hardware.
      </p>

      <div className="grid gap-3 mt-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Target load" value={f1(plan.targetLoadKg)} unit="kg"
          why={<WhyTip sourceId="iss-exercise"
            text={`Replaces the load gravity no longer provides, plus base training load (${ex.baseTrainingLoadKg} kg). Capped at ~272 kg (ARED approx. maximum).${plan.capped ? ' Cap reached.' : ''}`}
            formula="mass × (1 − g) × factor + base" />} />
        <Stat label="Effective bodyweight" value={plan.effectiveBodyweightN.toFixed(0)} unit="N"
          why={<WhyTip sourceId="hrp-muscle-bone"
            text="Weight the body actually loads the skeleton with at this gravity. Falls to zero in microgravity, which drives muscle and bone unloading."
            formula="mass × g × 9.81" />} />
        <Stat label="Tempo (ecc / con / hold)" value={`${f1(plan.tempo.eccentricS)} / ${f1(plan.tempo.concentricS)} / ${f1(plan.tempo.holdS)}`} unit="s"
          why={<WhyTip sourceId="iss-exercise"
            text="Slower reps at lower gravity keep time under tension up. Linear between 1 g (2/1/0 s) and 0 g (4/2/1 s)."
            formula="lerp(g: 0→1)" />} />
        <Stat label="Weekly volume" value={`${v.sessionsPerWeek}× ${v.sets}×${v.reps}`} unit={`· ${v.minutesPerDay} min/day`}
          why={<WhyTip sourceId="iss-exercise"
            text="Less gravity means a larger exercise dose. At 0 g this approaches the ~2 h/day budget used on the ISS."
            formula="lerp(g: 0→1)" />} />
      </div>
    </section>
  )
}
