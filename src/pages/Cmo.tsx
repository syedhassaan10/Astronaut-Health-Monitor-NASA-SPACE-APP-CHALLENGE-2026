import { useState } from 'react'
import AlertCard from '../components/AlertCard'
import AlertLog from '../components/AlertLog'
import CmoNote from '../components/CmoNote'
import LogbookPanel from '../components/LogbookPanel'
import Page from '../components/Page'
import CheckinSummary from '../components/CheckinSummary'
import CheckinTrend from '../components/CheckinTrend'
import StatusBadge from '../components/StatusBadge'
import { CREW } from '../data/crew'
import { DEMO_DAYS } from '../data/demoSeed'
import type { Alert } from '../engine/healthTypes'
import { useAssessments } from '../state/useAssessments'
import { useCheckins } from '../state/useCheckins'

const SEVERITY = { ACT: 0, WATCH: 1 } as const

export default function Cmo() {
  const [day, setDay] = useState(DEMO_DAYS)
  const assessments = useAssessments(day)
  const checkins = useCheckins().filter((c) => c.day <= day)
  const latestOf = (crewId: string) =>
    checkins.filter((c) => c.crewId === crewId).reduce<(typeof checkins)[number] | undefined>((m, c) => (!m || c.day > m.day ? c : m), undefined)
  const alerts: Alert[] = CREW.flatMap((c) => assessments[c.id]?.alerts ?? []).sort(
    (a, b) => SEVERITY[a.level] - SEVERITY[b.level],
  )

  return (
    <Page title="Crew Medical Officer view" subtitle="Status of all crew, trend estimates and alerts. Decision support only.">
      <div className="panel">
        <label className="flex flex-wrap items-center gap-3 text-sm">
          <span className="label-mono">Mission day (seeded demo data)</span>
          <input type="range" min={1} max={DEMO_DAYS} value={day} onChange={(e) => setDay(Number(e.target.value))}
            aria-label="Mission day" className="flex-1 min-w-48" />
          <span className="font-mono text-accent w-16">Day {day}</span>
        </label>
        <p className="text-xs text-ink-500 mt-1">Drag the slider to replay how each crew member&apos;s trend estimate evolves.</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {CREW.map((c) => {
          const a = assessments[c.id]
          const notes = a?.exercises.flatMap((e) => e.notes) ?? []
          return (
            <section key={c.id} className="panel" aria-label={`${c.name} status`}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-semibold">{c.name}</p>
                  <p className="text-xs text-ink-500">{c.role}</p>
                </div>
                <StatusBadge status={a?.status ?? 'NOMINAL'} large />
              </div>
              <p className="mt-3 text-sm text-ink-300">
                {a && a.alerts.length > 0 ? `${a.alerts.length} active alert${a.alerts.length > 1 ? 's' : ''}:` : 'No active alerts.'}
              </p>
              <ul className="mt-1 text-sm space-y-0.5">
                {a?.alerts.map((al) => (
                  <li key={al.id}><span className={al.level === 'ACT' ? 'text-act' : 'text-watch'}>{al.level}</span> · {al.title}</li>
                ))}
              </ul>
              {notes.length > 0 && <p className="mt-2 text-xs text-ink-500">{notes[0]}</p>}
              <div className="mt-3 pt-3 border-t border-space-700"><CheckinSummary checkin={latestOf(c.id)} /></div>
            </section>
          )
        })}
      </div>

      <h2 className="font-semibold pt-2">Daily check-in trends</h2>
      <p className="text-sm text-ink-300 -mt-3">Self-reported sleep, fatigue, pain and stress (0-10) shown next to the exercise trends above.</p>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {CREW.map((c) => (
          <section key={c.id} className="panel" aria-label={`${c.name} check-in trend`}>
            <p className="text-sm font-semibold mb-2">{c.name}</p>
            <CheckinTrend checkins={checkins.filter((x) => x.crewId === c.id)} label={c.name} />
          </section>
        ))}
      </div>

      <h2 className="font-semibold pt-2">Alerts ({alerts.length})</h2>
      {alerts.length === 0 && <div className="panel text-sm text-ink-300">No alerts on day {day}. All crew trend estimates are within their baselines.</div>}
      {alerts.map((al) => (
        <div key={al.id}>
          <p className="label-mono mb-1">{CREW.find((c) => c.id === al.crewId)?.name}</p>
          <AlertCard alert={al} />
        </div>
      ))}

      <h2 className="font-semibold pt-2">Alert log</h2>
      <p className="text-sm text-ink-300 -mt-3">Every alert, with the mission day it was first raised. Escalations are logged separately. Acknowledgements are saved.</p>
      <AlertLog />

      <h2 className="font-semibold pt-2">CMO notes</h2>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {CREW.map((c) => <CmoNote key={c.id} crewId={c.id} name={c.name} />)}
      </div>

      <LogbookPanel />
    </Page>
  )
}
