import { useEffect, useMemo, useRef, useState } from 'react'
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { readTextMaybeGzip } from '../../data/gzip'
import { earthDb, storeCsvOnly, storePacket, type EarthPacketRow } from '../../db/earthDb'
import { CHANNEL_NAME } from '../../downlink/protocol'
import { EarthReceiver } from '../../downlink/receiver'
import { adherencePct, formatKb, hashText, mergeTrends, parsePacketCsv, parsePacketJson, type TrendRow } from '../../engine/downlink'
import { useLive } from '../../state/useLive'
import StatusBadge from '../StatusBadge'

const btn = 'px-3 py-1.5 rounded-md text-sm border border-space-600 text-ink-100 hover:bg-space-700 disabled:opacity-40'
const CREW_COLORS = ['#38bdf8', '#34d399', '#fbbf24', '#a78bfa', '#f87171']
const MAX_IMPORT_BYTES = 5_000_000

type Metric = { key: string; label: string; unit: string; pick: (r: TrendRow) => number | null }
const METRICS: Metric[] = [
  { key: 'depth', label: 'Squat depth (bottom knee angle)', unit: '°', pick: (r) => r.depthDeg },
  { key: 'concentric', label: 'Lifting phase duration', unit: ' s', pick: (r) => r.concentricS },
  { key: 'asymmetry', label: 'Left/right asymmetry', unit: '°', pick: (r) => r.asymmetryDeg },
  { key: 'variability', label: 'Rep-to-rep variability', unit: '°', pick: (r) => r.variabilityDeg },
  { key: 'adherence', label: 'Exercise volume completed', unit: '%', pick: adherencePct },
]

export default function EarthView() {
  const packets = useLive(() => earthDb.packets.orderBy('receivedAt').reverse().toArray())
  const [listening, setListening] = useState(false)
  const [event, setEvent] = useState<string | null>(null)
  const [importMsg, setImportMsg] = useState<{ ok: boolean; text: string } | null>(null)
  const [metricKey, setMetricKey] = useState('depth')
  const [confirmClear, setConfirmClear] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  // Open the receiving end of the channel for as long as this tab is open.
  useEffect(() => {
    if (typeof BroadcastChannel === 'undefined') return
    const channel = new BroadcastChannel(CHANNEL_NAME)
    const receiver = new EarthReceiver({
      channel,
      onPacket: (id, duplicate) =>
        setEvent(duplicate ? `Packet ${id} arrived again and was ignored as a duplicate.` : `Packet ${id} received and stored.`),
    })
    receiver.start()
    setListening(true)
    return () => {
      receiver.stop()
      channel.close()
      setListening(false)
    }
  }, [])

  const list = packets ?? []
  const latest = list[0]
  const byMission = useMemo(() => [...list].sort((a, b) => a.missionDay - b.missionDay || a.createdAt - b.createdAt), [list])
  const trends = useMemo(() => mergeTrends(byMission.map((p) => p.csv)), [byMission])
  const latestSummary = useMemo(() => [...byMission].reverse().find((p) => p.summary)?.summary ?? null, [byMission])
  const nameOf = (id: string) => latestSummary?.crew.find((c) => c.crewId === id)?.name ?? id
  const crewIds = useMemo(() => [...new Set(trends.map((r) => r.crewId))], [trends])
  const metric = METRICS.find((m) => m.key === metricKey) ?? METRICS[0]!
  const chart = useMemo(() => {
    const days = [...new Set(trends.map((r) => r.day))].sort((a, b) => a - b)
    return days.map((day) => {
      const row: Record<string, number | null> = { day }
      for (const id of crewIds) {
        const r = trends.find((t) => t.day === day && t.crewId === id)
        row[id] = r ? metric.pick(r) : null
      }
      return row
    })
  }, [trends, crewIds, metric])

  async function importFile(file: File) {
    setImportMsg(null)
    try {
      if (file.size > MAX_IMPORT_BYTES) throw new Error('File is too large (limit 5 MB).')
      const text = await readTextMaybeGzip(file, MAX_IMPORT_BYTES)
      if (file.name.toLowerCase().endsWith('.json') || text.trimStart().startsWith('{')) {
        const parsed = parsePacketJson(text)
        if (!parsed.ok) throw new Error(parsed.error)
        const { duplicate } = await storePacket(parsed.packet, 'import')
        setImportMsg({ ok: true, text: duplicate ? `Packet ${parsed.packet.id} was already stored; nothing changed.` : `Imported packet ${parsed.packet.id} (mission day ${parsed.packet.missionDay}).` })
      } else {
        const parsed = parsePacketCsv(text)
        if (!parsed.ok) throw new Error(parsed.error)
        if (parsed.rows.length === 0) throw new Error('The CSV has no session rows.')
        const day = Math.max(...parsed.rows.map((r) => r.day))
        const { duplicate } = await storeCsvOnly(`csv-${hashText(text)}`, day, text)
        setImportMsg({ ok: true, text: duplicate ? 'This CSV was already imported; nothing changed.' : `Imported CSV with ${parsed.rows.length} session rows (no summary, so no alerts are shown for it).` })
      }
    } catch (e) {
      setImportMsg({ ok: false, text: `Import failed: ${e instanceof Error ? e.message : String(e)}` })
    }
  }

  return (
    <div className="space-y-4">
      <div role="note" className="rounded-md border border-space-600 bg-space-900 px-3 py-2 text-sm text-ink-300">
        <strong className="text-accent">SIMULATED Earth receiver.</strong> This tab plays the flight surgeon on the ground. It has its own separate
        database and only knows what was downlinked to it (or imported below). Keep it open to receive packets.
      </div>

      <section className="panel" aria-label="Receiver status">
        <div className="flex flex-wrap items-center gap-x-8 gap-y-2">
          <p role="status" className={`font-mono text-sm ${listening ? 'text-nominal' : 'text-act'}`}>
            {listening ? `● Listening on “${CHANNEL_NAME}”` : '○ BroadcastChannel is not available in this browser'}
          </p>
          <p className="text-sm">
            <span className="label-mono mr-2">Last downlink</span>
            {latest ? <strong>{new Date(latest.receivedAt).toLocaleString()} · mission day {latest.missionDay}</strong> : <span className="text-ink-500">nothing received yet</span>}
          </p>
          <p className="text-sm text-ink-300">{list.length} packet{list.length === 1 ? '' : 's'} stored</p>
        </div>
        {event && <p role="status" className="text-sm text-nominal mt-2">{event}</p>}
      </section>

      <section className="panel" aria-label="Received packets">
        <h2 className="font-semibold">Received packets</h2>
        {list.length === 0 ? (
          <p className="text-sm text-ink-300 mt-2">Nothing yet. On the astronaut tab: open the comms window, queue a packet and wait for the simulated delay.</p>
        ) : (
          <div className="overflow-x-auto mt-2">
            <table className="w-full text-sm text-left">
              <thead className="label-mono"><tr><th className="pr-3 py-1">Received</th><th className="pr-3">Mission day</th><th className="pr-3">Size</th><th className="pr-3">Via</th><th className="pr-3">Crew status</th><th>Id</th></tr></thead>
              <tbody>
                {list.map((p: EarthPacketRow) => (
                  <tr key={p.id} className="border-t border-space-700 align-top">
                    <td className="pr-3 py-1.5 whitespace-nowrap">{new Date(p.receivedAt).toLocaleTimeString()}</td>
                    <td className="pr-3 font-mono">{p.missionDay}</td>
                    <td className="pr-3 whitespace-nowrap">{formatKb(p.sizeBytes)}</td>
                    <td className="pr-3">{p.via === 'link' ? 'downlink' : 'import'}</td>
                    <td className="pr-3">
                      {p.summary ? <span className="flex flex-wrap gap-1">{p.summary.crew.map((c) => <span key={c.crewId} title={c.name}><StatusBadge status={c.status} /></span>)}</span> : <span className="text-ink-500">CSV only</span>}
                    </td>
                    <td className="font-mono text-xs text-ink-500">{p.id}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {latestSummary && (
        <section className="panel" aria-label="Latest crew status">
          <h2 className="font-semibold">Crew status in the latest summary <span className="text-ink-500 font-normal text-sm">· estimates, decision support only</span></h2>
          <div className="grid gap-3 mt-3 md:grid-cols-3">
            {latestSummary.crew.map((c) => (
              <article key={c.crewId} className="bg-space-900 border border-space-700 rounded-lg p-3 text-sm" aria-label={`${c.name} status`}>
                <div className="flex items-start justify-between gap-2"><div><p className="font-semibold">{c.name}</p><p className="text-xs text-ink-500">{c.role}</p></div><StatusBadge status={c.status} /></div>
                {c.alerts.length === 0 ? <p className="text-ink-300 mt-2">No active alerts.</p> : (
                  <ul className="mt-2 space-y-1.5">
                    {c.alerts.map((a) => (
                      <li key={`${a.rule}-${a.level}`}><span className={a.level === 'ACT' ? 'text-act' : 'text-watch'}>{a.level}</span> · {a.title}<span className="block text-xs text-ink-500">{a.summary}</span></li>
                    ))}
                  </ul>
                )}
                {c.latestCheckin && <p className="text-xs text-ink-500 mt-2">Check-in d{c.latestCheckin.day}: sleep {c.latestCheckin.sleep}, fatigue {c.latestCheckin.fatigue}, pain {c.latestCheckin.pain}{c.latestCheckin.painLocation ? ` (${c.latestCheckin.painLocation})` : ''}, stress {c.latestCheckin.stress}</p>}
              </article>
            ))}
          </div>
        </section>
      )}

      <section className="panel" aria-label="Crew trends">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-semibold">Crew trends from received data</h2>
          <label className="text-sm flex items-center gap-2">Metric
            <select value={metricKey} onChange={(e) => setMetricKey(e.target.value)} className="bg-space-900 border border-space-600 rounded-md px-2 py-1">
              {METRICS.map((m) => <option key={m.key} value={m.key}>{m.label}</option>)}
            </select>
          </label>
        </div>
        {chart.length === 0 ? <p className="text-sm text-ink-300 mt-2">No session data yet.</p> : (
          <div role="img" aria-label={`${metric.label} by mission day for each crew member, from received packets`} className="h-64 w-full mt-3">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chart} margin={{ top: 8, right: 12, bottom: 16, left: 0 }}>
                <CartesianGrid stroke="#26375a" strokeDasharray="3 3" />
                <XAxis dataKey="day" stroke="#7a8aa8" tick={{ fontSize: 11 }} label={{ value: 'mission day', position: 'insideBottom', offset: -10, fill: '#7a8aa8', fontSize: 10 }} />
                <YAxis stroke="#7a8aa8" tick={{ fontSize: 11 }} domain={['auto', 'auto']} width={44} />
                <Tooltip contentStyle={{ background: '#111b2e', border: '1px solid #26375a', fontSize: 12 }} labelFormatter={(d) => `Day ${d}`}
                  formatter={(v, name) => [`${Number(v).toFixed(1)}${metric.unit}`, nameOf(String(name))]} />
                <Legend formatter={(v) => nameOf(String(v))} wrapperStyle={{ fontSize: 11 }} />
                {crewIds.map((id, i) => (
                  <Line key={id} type="monotone" dataKey={id} stroke={CREW_COLORS[i % CREW_COLORS.length]} strokeWidth={2} dot={false}
                    connectNulls isAnimationActive={false} strokeDasharray={i === 1 ? '6 3' : i === 2 ? '2 3' : undefined} />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
      </section>

      <section className="panel" aria-label="Import packet or CSV">
        <h2 className="font-semibold">Import packet / CSV <span className="text-ink-500 font-normal text-sm">· fallback if the link is down</span></h2>
        <p className="text-sm text-ink-300 mt-1">Load a packet JSON or CSV that was carried over on a file (downloaded from the astronaut tab). Duplicates are ignored.</p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button type="button" className={btn} onClick={() => fileRef.current?.click()}>Import packet/CSV…</button>
          <input ref={fileRef} type="file" accept=".json,.csv,.gz,application/json,text/csv" className="hidden" aria-label="Choose a packet JSON or CSV file to import"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) void importFile(f); e.target.value = '' }} />
          {!confirmClear ? (
            <button type="button" className={`${btn} ml-auto`} disabled={list.length === 0} onClick={() => setConfirmClear(true)}>Clear received data…</button>
          ) : (
            <span className="ml-auto flex items-center gap-2 text-sm">
              <span className="text-act">Delete everything Earth has received?</span>
              <button type="button" className={`${btn} border-act text-act`} onClick={() => { void earthDb.packets.clear(); setConfirmClear(false); setEvent(null) }}>Yes, clear</button>
              <button type="button" className={btn} onClick={() => setConfirmClear(false)}>Cancel</button>
            </span>
          )}
        </div>
        {importMsg && <p role={importMsg.ok ? 'status' : 'alert'} className={`text-sm mt-3 ${importMsg.ok ? 'text-nominal' : 'text-act'}`}>{importMsg.text}</p>}
      </section>
    </div>
  )
}
