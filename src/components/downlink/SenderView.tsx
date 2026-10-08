import { useEffect, useMemo, useState } from 'react'
import { CREW } from '../../data/crew'
import { downloadBlob } from '../../data/gzip'
import { db } from '../../db/db'
import { TODAY } from '../../db/repo'
import { CHANNEL_NAME } from '../../downlink/protocol'
import { cancelQueued, enqueuePacket, listQueue } from '../../downlink/queueRepo'
import { buildPacket, formatKb, packetSizeBytes, type DownlinkPacket } from '../../engine/downlink'
import { phaseOf, type Phase } from '../../engine/downlinkQueue'
import { LATENCY_MAX, LATENCY_MIN, useApp } from '../../state/AppState'
import { useSessionRecords } from '../../state/useAssessments'
import { useCheckins } from '../../state/useCheckins'
import { useLive } from '../../state/useLive'
import { useNow } from '../../state/useNow'
import StatusBadge from '../StatusBadge'

const btn = 'px-3 py-1.5 rounded-md text-sm border border-space-600 text-ink-100 hover:bg-space-700 disabled:opacity-40'
const WINDOWS = [7, 14, 30] as const

/** Earth tab presence: listens for its heartbeat on the shared channel. */
function useEarthPresence(): boolean {
  const [seen, setSeen] = useState(0)
  const now = useNow(1000)
  useEffect(() => {
    if (typeof BroadcastChannel === 'undefined') return
    const ch = new BroadcastChannel(CHANNEL_NAME)
    ch.onmessage = (e: MessageEvent) => {
      if ((e.data as { type?: string } | null)?.type === 'earth-online') setSeen(Date.now())
    }
    return () => ch.close()
  }, [])
  return now - seen < 10_000
}

const PHASE: Record<Phase, { label: string; cls: string }> = {
  'waiting-for-window': { label: 'QUEUED · waiting for a comms window (blackout)', cls: 'border-watch text-watch' },
  starting: { label: 'STARTING TRANSMISSION', cls: 'border-accent text-accent' },
  'in-transit': { label: 'IN TRANSIT', cls: 'border-accent text-accent' },
  'awaiting-ack': { label: 'DELIVERED · awaiting ACK', cls: 'border-accent text-accent' },
  acked: { label: 'ACKNOWLEDGED BY EARTH', cls: 'border-nominal text-nominal' },
  'gave-up': { label: 'GAVE UP after repeated attempts', cls: 'border-act text-act' },
}

export default function SenderView() {
  const app = useApp()
  const windowOpen = app.comms === 'WINDOW OPEN'
  const sessions = useSessionRecords()
  const checkins = useCheckins()
  const queue = useLive(() => listQueue(db))
  const now = useNow(250)
  const earthOnline = useEarthPresence()
  const [windowDays, setWindowDays] = useState<number>(14)
  const [msg, setMsg] = useState<string | null>(null)

  const crew = useMemo(() => CREW.map((c) => ({ id: c.id, name: c.name, role: c.role })), [])
  const build = (id: string): DownlinkPacket =>
    buildPacket({ sessions, checkins, crew, day: TODAY, windowDays, id, now: Date.now() })
  const preview = useMemo(
    () => buildPacket({ sessions, checkins, crew, day: TODAY, windowDays, id: 'preview', now: 0 }),
    [sessions, checkins, crew, windowDays],
  )
  const size = packetSizeBytes(preview)
  const ready = sessions.length > 0
  const latencyS = app.latencyMin // 1 simulated minute = 1 real second

  async function queuePacket() {
    const p = build(`pkt-${crypto.randomUUID().slice(0, 8)}`)
    await enqueuePacket(p)
    setMsg(windowOpen
      ? `Packet ${p.id} queued and will go out now.`
      : `Packet ${p.id} queued. It stays here until the comms window opens.`)
  }
  const download = (kind: 'json' | 'csv') => {
    const p = build(`pkt-${crypto.randomUUID().slice(0, 8)}`)
    if (kind === 'json') downloadBlob(new Blob([JSON.stringify(p, null, 2)], { type: 'application/json' }), `orbitfit-packet-day${p.missionDay}-${p.id}.json`)
    else downloadBlob(new Blob(['﻿' + p.csv], { type: 'text/csv;charset=utf-8' }), `orbitfit-packet-day${p.missionDay}-${p.id}.csv`)
    setMsg(`Downloaded ${kind.toUpperCase()} (${formatKb(kind === 'json' ? packetSizeBytes(p) : new TextEncoder().encode(p.csv).length)}). It can be carried to Earth and loaded with “Import packet/CSV”.`)
  }

  return (
    <div className="space-y-4">
      <div role="note" className="rounded-md border border-space-600 bg-space-900 px-3 py-2 text-sm text-ink-300">
        <strong className="text-accent">SIMULATED link.</strong> There is no radio and no server. Packets travel between browser tabs on this device only,
        and the one-way delay is scaled for demo: <strong>1 simulated minute = 1 second</strong>.
      </div>

      <section className="panel" aria-label="Comms link">
        <h2 className="font-semibold">Comms link</h2>
        <div className="mt-3 flex flex-wrap items-center gap-x-8 gap-y-3">
          <div>
            <p className="label-mono">Status</p>
            <button type="button" aria-pressed={windowOpen} onClick={() => app.setComms(windowOpen ? 'BLACKOUT' : 'WINDOW OPEN')}
              className={`mt-1 font-mono text-sm px-3 py-1.5 rounded-md border ${windowOpen ? 'border-nominal text-nominal' : 'border-act text-act'}`}>
              ● {app.comms} <span className="text-ink-500">(click to toggle)</span>
            </button>
          </div>
          <label className="flex-1 min-w-60 text-sm">
            <span className="label-mono block">One-way latency (simulated)</span>
            <span className="flex items-center gap-3 mt-1">
              <input type="range" min={LATENCY_MIN} max={LATENCY_MAX} step={1} value={app.latencyMin}
                onChange={(e) => app.setLatencyMin(Number(e.target.value))} aria-label="Simulated one-way latency in minutes" className="flex-1 accent-sky-400" />
              <span className="font-mono text-accent w-24">{app.latencyMin} min</span>
            </span>
            <span className="text-xs text-ink-500">Demo time: arrives {latencyS} s after sending; the ACK takes another {latencyS} s.</span>
          </label>
          <div>
            <p className="label-mono">Earth receiver</p>
            <p className={`mt-1 font-mono text-sm ${earthOnline ? 'text-nominal' : 'text-ink-500'}`} role="status">
              {earthOnline ? '● Earth tab is listening' : '○ No Earth tab detected'}
            </p>
            <a className="text-sm text-accent underline" href={`${import.meta.env.BASE_URL}downlink?role=earth`} target="_blank" rel="noreferrer">
              Open Earth receiver in a new tab ↗
            </a>
          </div>
        </div>
        {!windowOpen && <p className="text-sm text-watch mt-3">BLACKOUT: nothing is transmitted. Packets wait in the queue (they are saved, so even a reload keeps them).</p>}
      </section>

      <section className="panel" aria-label="Packet builder">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="font-semibold">Flight surgeon packet</h2>
          <span className="label-mono">summary JSON + session CSV · decision support only</span>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-4 text-sm">
          <label className="flex items-center gap-2">CSV detail
            <select value={windowDays} onChange={(e) => setWindowDays(Number(e.target.value))} className="bg-space-900 border border-space-600 rounded-md px-2 py-1">
              {WINDOWS.map((d) => <option key={d} value={d}>last {d} days</option>)}
            </select>
          </label>
          <p>Packet size: <strong className="font-mono text-accent" data-testid="packet-size">{formatKb(size)}</strong>
            <span className="text-ink-500"> ({new TextEncoder().encode(preview.csv).length.toLocaleString()} B of that is CSV)</span></p>
        </div>

        <ul className="mt-3 grid gap-2 sm:grid-cols-3" aria-label="Packet summary preview">
          {preview.summary.crew.map((c) => (
            <li key={c.crewId} className="bg-space-900 border border-space-700 rounded-lg p-2 text-sm">
              <div className="flex items-center justify-between gap-2"><span className="font-semibold">{c.name}</span><StatusBadge status={c.status} /></div>
              <p className="text-xs text-ink-500 mt-1">{c.alerts.length ? c.alerts.map((a) => a.title).join(' · ') : 'No active alerts'}</p>
            </li>
          ))}
        </ul>

        <div className="mt-4 flex flex-wrap gap-2">
          <button type="button" className={`${btn} border-accent text-accent`} disabled={!ready} onClick={() => void queuePacket()}>Queue packet for downlink</button>
          <button type="button" className={btn} disabled={!ready} onClick={() => download('json')}>Download JSON</button>
          <button type="button" className={btn} disabled={!ready} onClick={() => download('csv')}>Download CSV</button>
        </div>
        {msg && <p role="status" className="text-sm text-nominal mt-3">{msg}</p>}
      </section>

      <section className="panel" aria-label="Downlink queue">
        <h2 className="font-semibold">Downlink queue</h2>
        {!queue ? <p className="text-sm text-ink-500 mt-2">Reading queue…</p> : queue.length === 0 ? (
          <p className="text-sm text-ink-300 mt-2">Nothing queued. Build a packet above.</p>
        ) : (
          <ul className="mt-3 space-y-2">
            {queue.map((q) => {
              const phase = phaseOf(q, windowOpen)
              const st = PHASE[phase]
              const left = q.deliverAt !== null ? Math.max(0, Math.ceil((q.deliverAt - now) / 1000)) : null
              return (
                <li key={q.id} className="bg-space-900 border border-space-700 rounded-lg p-3 text-sm">
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="font-mono">{q.id}</span>
                    <span className={`font-mono text-xs border rounded px-2 py-0.5 ${st.cls}`}>{st.label}</span>
                    <span className="text-ink-500">day {q.missionDay} · {formatKb(q.sizeBytes)} · attempt{q.attempts === 1 ? '' : 's'}: {q.attempts}</span>
                    {q.status !== 'acked' && <button type="button" className={`${btn} ml-auto`} onClick={() => void cancelQueued(q.id)}>Cancel</button>}
                  </div>
                  {phase === 'in-transit' && left !== null && (
                    <div className="mt-2">
                      <div className="h-1.5 rounded bg-space-700 overflow-hidden" role="progressbar" aria-label="Transit progress"
                        aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(100 * (1 - (left * 1000) / Math.max(1, (q.deliverAt ?? 0) - (q.sentAt ?? 0))))}>
                        <div className="h-full bg-accent" style={{ width: `${Math.min(100, 100 * (1 - (left * 1000) / Math.max(1, (q.deliverAt ?? 0) - (q.sentAt ?? 0))))}%` }} />
                      </div>
                      <p className="text-xs text-ink-500 mt-1">Reaches Earth in {left} s (simulated {left} min of delay)</p>
                    </div>
                  )}
                  {phase === 'awaiting-ack' && <p className="text-xs text-ink-500 mt-1">Transmitted at {new Date(q.transmittedAt ?? 0).toLocaleTimeString()}. Waiting for Earth’s ACK (the return trip also takes the simulated delay).</p>}
                  {phase === 'acked' && <p className="text-xs text-nominal mt-1">Acknowledged at {new Date(q.ackedAt ?? 0).toLocaleTimeString()}.</p>}
                  {q.attempts > 1 && phase !== 'acked' && <p className="text-xs text-watch mt-1">No acknowledgement last time, so it was sent again. Earth ignores duplicates.</p>}
                </li>
              )
            })}
          </ul>
        )}
      </section>
    </div>
  )
}
