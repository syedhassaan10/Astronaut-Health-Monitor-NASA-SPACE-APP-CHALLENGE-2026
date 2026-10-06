import { Link } from 'react-router-dom'

// Phase 1 placeholder content; the full Judge Quick Start flow is finished in Phase 8.
export default function QuickStart({ onClose }: { onClose: () => void }) {
  return (
    <section className="panel border-accent mb-4" aria-label="Judge Quick Start">
      <div className="flex items-start justify-between gap-4">
        <h2 className="font-semibold text-accent">Judge Quick Start</h2>
        <button type="button" onClick={onClose} aria-label="Dismiss quick start" className="text-ink-300 hover:text-ink-100">✕</button>
      </div>
      <ol className="list-decimal pl-5 mt-2 space-y-1 text-sm text-ink-300">
        <li>Try Demo Mode on the <Link className="text-accent underline" to="/crew">Crew</Link> page (no webcam needed).</li>
        <li>Change gravity in the header and watch the plan adapt.</li>
        <li>Open <Link className="text-accent underline" to="/downlink?role=earth">the Earth tab</Link> and send a downlink.</li>
        <li>Turn off internet — it keeps working.</li>
      </ol>
    </section>
  )
}
