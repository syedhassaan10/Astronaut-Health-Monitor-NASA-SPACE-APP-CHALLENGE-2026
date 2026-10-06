import { Link } from 'react-router-dom'
import { EXERCISES } from '../engine/gravityEngine'
import type { Alert } from '../engine/healthTypes'
import StatusBadge from './StatusBadge'
import TrendChart from './TrendChart'

const border = { WATCH: 'border-watch/60', ACT: 'border-act/70' } as const

/** The three-part alert: what changed / why it matters in spaceflight / suggested action. */
export default function AlertCard({ alert, compact = false }: { alert: Alert; compact?: boolean }) {
  return (
    <article className={`panel ${border[alert.level]}`} aria-label={`${alert.level} alert: ${alert.title}`}>
      <header className="flex flex-wrap items-center gap-2">
        <StatusBadge status={alert.level} />
        <h3 className="font-semibold">{alert.title}</h3>
        <span className="label-mono ml-auto">{EXERCISES[alert.exercise].label} · day {alert.day}</span>
      </header>

      <div className={`mt-3 grid gap-4 ${compact ? '' : 'lg:grid-cols-[1.1fr_1fr]'}`}>
        <section aria-label="What changed">
          <h4 className="label-mono">1 · What changed</h4>
          <p className="text-sm mt-1">{alert.what.summary}</p>
          <TrendChart alert={alert} />
        </section>

        <div className="space-y-3">
          <section aria-label="Why it matters in spaceflight">
            <h4 className="label-mono">2 · Why it matters in spaceflight</h4>
            <p className="text-sm text-ink-300 mt-1">{alert.why.text}</p>
            <Link className="text-xs text-accent underline" to={`/sources#${alert.why.sourceId}`}>Source</Link>
          </section>
          <section aria-label="Suggested action">
            <h4 className="label-mono">3 · Suggested action</h4>
            <ul className="list-disc pl-5 mt-1 space-y-1 text-sm">
              {alert.actions.map((a) => <li key={a}>{a}</li>)}
            </ul>
          </section>
        </div>
      </div>
    </article>
  )
}
