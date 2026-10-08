import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { CREW } from '../data/crew'
import { LOCATIONS } from '../data/locations'
import { buildPlan } from '../engine/gravityEngine'
import { useApp } from '../state/AppState'

const QUICK_PLACES = ['leo', 'moon', 'mars', 'earth'] as const

function useOnline(): boolean {
  const [online, setOnline] = useState(() => (typeof navigator === 'undefined' ? true : navigator.onLine))
  useEffect(() => {
    const on = () => setOnline(true)
    const off = () => setOnline(false)
    window.addEventListener('online', on)
    window.addEventListener('offline', off)
    return () => {
      window.removeEventListener('online', on)
      window.removeEventListener('offline', off)
    }
  }, [])
  return online
}

const btn = 'px-3 py-1.5 rounded-md text-sm border border-space-600 text-ink-100 hover:bg-space-700'

function Step({ n, title, children }: { n: number; title: string; children: React.ReactNode }) {
  return (
    <li className="flex gap-3">
      <span aria-hidden="true" className="shrink-0 w-6 h-6 rounded-full border border-accent text-accent text-xs font-mono grid place-items-center mt-0.5">{n}</span>
      <div className="min-w-0 flex-1">
        <p className="font-semibold text-ink-100">{title}</p>
        <div className="text-sm text-ink-300 mt-1 space-y-2">{children}</div>
      </div>
    </li>
  )
}

/** First-load guide for judges (dismissible; reopen from the header). */
export default function QuickStart({ onClose }: { onClose: () => void }) {
  const app = useApp()
  const online = useOnline()
  const member = CREW.find((c) => c.id === app.crewId) ?? CREW[0]!
  const plan = buildPlan(member.massKg, app.g, 'squat')
  const place = LOCATIONS.find((l) => l.id === app.locationId)

  return (
    <section className="panel border-accent mb-4" aria-label="Judge Quick Start">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-semibold text-accent">Judge Quick Start <span className="text-ink-500 font-normal text-sm">· 4 steps, about 2 minutes, no webcam or login needed</span></h2>
          <p className="text-sm text-ink-300 mt-1">
            OrbitFit estimates whether an astronaut is deconditioning from how they exercise, and suggests what to do. Decision support, not a diagnosis.
          </p>
        </div>
        <button type="button" onClick={onClose} aria-label="Dismiss quick start" className="text-ink-300 hover:text-ink-100 text-lg leading-none px-1">✕</button>
      </div>

      <ol className="mt-4 space-y-5 list-none p-0">
        <Step n={1} title="Try Demo Mode (no webcam needed)">
          <p>Plays a bundled squat video through the same on-device pose pipeline as the webcam. Reps, depth and tempo appear as they happen.</p>
          <Link to="/crew?demo=1" className={`${btn} inline-block border-accent text-accent`}>Start Demo Mode</Link>
        </Step>

        <Step n={2} title="Change gravity and watch the plan adapt">
          <div className="flex flex-wrap gap-2" role="group" aria-label="Quick gravity presets">
            {QUICK_PLACES.map((id) => {
              const l = LOCATIONS.find((x) => x.id === id)!
              return (
                <button key={id} type="button" aria-pressed={app.locationId === id} onClick={() => app.setLocationId(id)}
                  className={`${btn} ${app.locationId === id ? 'border-accent text-accent bg-space-900' : ''}`}>{l.label}</button>
              )
            })}
          </div>
          <p className="font-mono text-xs bg-space-900 border border-space-700 rounded-md px-3 py-2" aria-live="polite">
            {place?.label ?? 'Custom'} → squat target <span className="text-accent">{plan.targetLoadKg.toFixed(1)} kg</span> · tempo{' '}
            <span className="text-accent">{plan.tempo.eccentricS.toFixed(1)} / {plan.tempo.concentricS.toFixed(1)} / {plan.tempo.holdS.toFixed(1)} s</span>{' '}
            · {plan.volume.sessionsPerWeek}× per week
            <span className="text-ink-500"> (simulated, for {member.name})</span>
          </p>
        </Step>

        <Step n={3} title="Send a downlink to the Earth tab">
          <p>
            Open the Earth receiver in a second tab, then queue a packet here. In BLACKOUT it waits in the queue; when you open the comms window it arrives after the
            simulated delay (1 simulated minute = 1 second), and Earth sends an acknowledgement back.
          </p>
          <div className="flex flex-wrap gap-2">
            <a className={btn} href={`${import.meta.env.BASE_URL}downlink?role=earth`} target="_blank" rel="noreferrer">1 · Open Earth tab ↗</a>
            <Link className={btn} to="/downlink">2 · Build and queue a packet</Link>
            <button type="button" className={btn} aria-pressed={app.comms === 'WINDOW OPEN'}
              onClick={() => app.setComms(app.comms === 'WINDOW OPEN' ? 'BLACKOUT' : 'WINDOW OPEN')}>
              3 · Comms: {app.comms === 'WINDOW OPEN' ? 'WINDOW OPEN (click for blackout)' : 'BLACKOUT (click to open window)'}
            </button>
          </div>
        </Step>

        <Step n={4} title="Turn off the internet. It keeps working.">
          <p>
            After the first load every file, including the pose model, is cached on this device. Switch off Wi-Fi, or open DevTools (F12) → Network → <em>Offline</em>,
            then reload.
          </p>
          <p className="flex flex-wrap gap-2 font-mono text-xs">
            <span className={`border rounded px-2 py-1 ${app.offlineReady ? 'border-nominal text-nominal' : 'border-watch text-watch'}`} role="status">
              {app.offlineReady ? '● OFFLINE READY: everything is cached' : '○ Caching files… wait for OFFLINE READY in the header'}
            </span>
            <span className={`border rounded px-2 py-1 ${online ? 'border-space-600 text-ink-300' : 'border-act text-act'}`} role="status">
              {online ? 'Browser says: online' : 'Browser says: OFFLINE. You are running without a network.'}
            </span>
          </p>
        </Step>
      </ol>

      <p className="text-xs text-ink-500 mt-5 border-t border-space-700 pt-3">
        Reopen this panel any time from the “Quick Start” button in the header. To start over, use <Link className="text-accent underline" to="/cmo#logbook">Reset demo data</Link>{' '}
        on the CMO page. More detail in <Link className="text-accent underline" to="/about">About</Link>.
      </p>
    </section>
  )
}
