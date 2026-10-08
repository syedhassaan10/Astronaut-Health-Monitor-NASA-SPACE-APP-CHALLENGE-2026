import { useEffect, useRef, useState } from 'react'
import { downloadBlob, gzipText, readTextMaybeGzip } from '../data/gzip'
import { db } from '../db/db'
import { exportLogbookCsv, importLogbookCsv, type ImportReport } from '../db/logbookIO'
import { resetDemoData } from '../db/repo'
import { useLive } from '../state/useLive'

const btn = 'px-3 py-1.5 rounded-md text-sm border border-space-600 text-ink-100 hover:bg-space-700 disabled:opacity-40'

const stamp = () => new Date().toISOString().slice(0, 10).replace(/-/g, '')

/** Offline logbook controls: what is stored, export (CSV / gzipped CSV), import, reset. */
export default function LogbookPanel() {
  const counts = useLive(async () => ({
    sessions: await db.sessions.count(), reps: await db.reps.count(), checkins: await db.checkins.count(), alerts: await db.alerts.count(),
  }))
  const fileRef = useRef<HTMLInputElement>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<{ kind: 'ok' | 'error'; text: string } | null>(null)
  const [report, setReport] = useState<ImportReport | null>(null)
  const [confirmReset, setConfirmReset] = useState(false)
  const [storage, setStorage] = useState<string>('')

  useEffect(() => {
    void (async () => {
      try {
        const est = await navigator.storage?.estimate?.()
        const persisted = await navigator.storage?.persisted?.()
        if (est?.usage !== undefined) setStorage(`${(est.usage / 1_048_576).toFixed(1)} MB used · browser storage ${persisted ? 'protected' : 'not protected from eviction'}`)
      } catch {
        /* estimate unsupported: show nothing */
      }
    })()
  }, [counts])

  async function run(label: string, job: () => Promise<string | void>) {
    setBusy(true)
    setMessage(null)
    try {
      const done = await job()
      if (done) setMessage({ kind: 'ok', text: done })
    } catch (e) {
      setMessage({ kind: 'error', text: `${label} failed: ${e instanceof Error ? e.message : String(e)}` })
    } finally {
      setBusy(false)
    }
  }

  const exportCsv = () => run('Export', async () => {
    const csv = await exportLogbookCsv()
    downloadBlob(new Blob([csv], { type: 'text/csv;charset=utf-8' }), `orbitfit-logbook-${stamp()}.csv`)
    return `Exported ${(csv.length / 1024).toFixed(0)} KB CSV. It opens directly in Excel.`
  })

  const exportGz = () => run('Export', async () => {
    const gz = await gzipText(await exportLogbookCsv())
    downloadBlob(gz, `orbitfit-logbook-${stamp()}.csv.gz`)
    return `Exported ${(gz.size / 1024).toFixed(0)} KB gzipped CSV. Unzip it (7-Zip, WinRAR, macOS Archive Utility) before opening in Excel.`
  })

  const importFile = (file: File) => run('Import', async () => {
    setReport(null)
    const r = await importLogbookCsv(await readTextMaybeGzip(file))
    setReport(r)
    const added = r.added.sessions + r.added.reps + r.added.checkins
    return added > 0
      ? `Imported ${r.added.reps} reps, ${r.added.sessions} sessions and ${r.added.checkins} check-ins.`
      : r.errors.length === 0 ? 'Nothing new to import: everything in this file is already in the logbook.' : undefined
  })

  const reset = () => run('Reset', async () => {
    await resetDemoData()
    setConfirmReset(false)
    setReport(null)
    return 'Demo data restored. All sessions, check-ins, notes and alert history were replaced.'
  })

  return (
    <section id="logbook" className="panel scroll-mt-4" aria-label="Offline logbook">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">Offline logbook</h2>
        <span className="label-mono">stored in this browser · works without a network</span>
      </div>
      <p className="text-sm text-ink-300 mt-1" aria-live="polite">
        {counts
          ? `${counts.reps.toLocaleString()} reps · ${counts.sessions} sessions · ${counts.checkins} check-ins · ${counts.alerts} logged alerts`
          : 'Reading logbook…'}
        {storage && <span className="text-ink-500"> · {storage}</span>}
      </p>

      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" className={btn} disabled={busy} onClick={() => void exportCsv()}>Export CSV</button>
        <button type="button" className={btn} disabled={busy} onClick={() => void exportGz()}>Export gzipped CSV</button>
        <button type="button" className={btn} disabled={busy} onClick={() => fileRef.current?.click()}>Import CSV…</button>
        <input ref={fileRef} type="file" accept=".csv,.gz,text/csv,application/gzip" className="hidden" aria-label="Choose a logbook CSV file to import"
          onChange={(e) => {
            const f = e.target.files?.[0]
            if (f) void importFile(f)
            e.target.value = ''
          }} />
        {!confirmReset ? (
          <button type="button" className={`${btn} ml-auto`} disabled={busy} onClick={() => setConfirmReset(true)}>Reset demo data…</button>
        ) : (
          <span className="ml-auto flex flex-wrap items-center gap-2 text-sm">
            <span className="text-act">This erases everything you recorded.</span>
            <button type="button" className={`${btn} border-act text-act`} disabled={busy} onClick={() => void reset()}>Yes, reset</button>
            <button type="button" className={btn} onClick={() => setConfirmReset(false)}>Cancel</button>
          </span>
        )}
      </div>

      {message && (
        <p role={message.kind === 'error' ? 'alert' : 'status'} className={`mt-3 text-sm ${message.kind === 'error' ? 'text-act' : 'text-nominal'}`}>
          {message.text}
        </p>
      )}
      {report && (
        <div className="mt-3 text-sm text-ink-300" role="status">
          <p>
            Read {report.totalRows.toLocaleString()} rows: <strong className="text-ink-100">{report.added.reps} reps, {report.added.sessions} sessions,
            {' '}{report.added.checkins} check-ins added</strong>; {report.alreadyPresent.toLocaleString()} already present (left unchanged);{' '}
            {report.errors.length} problem{report.errors.length === 1 ? '' : 's'}.
          </p>
          {report.errors.length > 0 && (
            <ul className="mt-1 list-disc pl-5 text-act">
              {report.errors.slice(0, 8).map((e, i) => (
                <li key={i}>{e.line > 0 ? `Line ${e.line}: ` : ''}{e.message}</li>
              ))}
              {report.errors.length > 8 && <li>…and {report.errors.length - 8} more.</li>}
            </ul>
          )}
        </div>
      )}
    </section>
  )
}
