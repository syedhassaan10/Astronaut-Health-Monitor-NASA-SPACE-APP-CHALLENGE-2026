import { NavLink } from 'react-router-dom'
import { useApp } from '../state/AppState'
import { CREW } from '../data/crew'
import { LOCATIONS } from '../data/locations'

const NAV = [
  ['/crew', 'Crew'],
  ['/cmo', 'CMO'],
  ['/downlink', 'Downlink'],
  ['/about', 'About'],
  ['/sources', 'Sources'],
] as const

const selectCls =
  'bg-space-900 border border-space-600 rounded-md px-2 py-1.5 text-sm text-ink-100 min-w-0'

export default function Header({ onQuickStart }: { onQuickStart: () => void }) {
  const a = useApp()
  const commsOpen = a.comms === 'WINDOW OPEN'
  return (
    <header className="bg-space-900 border-b border-space-700">
      <div className="mx-auto max-w-7xl px-4 py-3 flex flex-wrap items-center gap-x-5 gap-y-3">
        <div className="flex items-center gap-2">
          <img src={`${import.meta.env.BASE_URL}icon.svg`} alt="" className="w-7 h-7" />
          <span className="font-mono font-bold tracking-widest text-accent">ORBITFIT</span>
        </div>

        <nav aria-label="Main" className="flex flex-wrap gap-1">
          {NAV.map(([to, label]) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `px-3 py-1.5 rounded-md text-sm ${isActive ? 'bg-space-700 text-ink-100' : 'text-ink-300 hover:bg-space-800'}`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="flex flex-wrap items-center gap-3 ml-auto">
          <label className="flex items-center gap-1.5 text-xs text-ink-300">
            Crew
            <select className={selectCls} value={a.crewId} onChange={(e) => a.setCrewId(e.target.value)} aria-label="Crew member">
              {CREW.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </label>

          <label className="flex items-center gap-1.5 text-xs text-ink-300">
            Location
            <select className={selectCls} value={a.locationId} onChange={(e) => a.setLocationId(e.target.value)} aria-label="Location and gravity">
              {LOCATIONS.map((l) => (
                <option key={l.id} value={l.id}>{l.label}</option>
              ))}
            </select>
          </label>

          {a.locationId === 'custom' && (
            <label className="flex items-center gap-1.5 text-xs text-ink-300">
              {a.customG.toFixed(2)} g
              <input type="range" min={0} max={1} step={0.01} value={a.customG}
                onChange={(e) => a.setCustomG(Number(e.target.value))} aria-label="Custom gravity in g" />
            </label>
          )}

          <button
            type="button"
            onClick={() => a.setComms(commsOpen ? 'BLACKOUT' : 'WINDOW OPEN')}
            aria-pressed={commsOpen}
            aria-label={`Comms status: ${a.comms}. Click to toggle (simulated).`}
            className={`font-mono text-xs px-2.5 py-1.5 rounded-md border ${
              commsOpen ? 'border-nominal text-nominal' : 'border-act text-act'
            }`}
          >
            ● {a.comms}
          </button>

          <span
            role="status"
            className={`font-mono text-xs px-2.5 py-1.5 rounded-md border ${
              a.offlineReady ? 'border-nominal text-nominal' : 'border-space-600 text-ink-500'
            }`}
          >
            {a.offlineReady ? 'OFFLINE READY' : 'CACHING…'}
          </span>

          <button type="button" onClick={onQuickStart}
            className="text-xs px-2.5 py-1.5 rounded-md border border-space-600 text-ink-300 hover:bg-space-800">
            Quick Start
          </button>
        </div>
      </div>
    </header>
  )
}
