import { useId, useState } from 'react'
import { Link } from 'react-router-dom'

// "Why?" tooltip: explains a number, shows the (simplified) formula, links to /sources.
export default function WhyTip({ text, formula, sourceId }: { text: string; formula?: string; sourceId: string }) {
  const [open, setOpen] = useState(false)
  const id = useId()
  return (
    <span className="relative inline-block" onMouseEnter={() => setOpen(true)} onMouseLeave={() => setOpen(false)}>
      <button
        type="button"
        aria-expanded={open}
        aria-controls={id}
        aria-label="Why this number?"
        onClick={() => setOpen((o) => !o)}
        onKeyDown={(e) => e.key === 'Escape' && setOpen(false)}
        className="ml-1.5 text-[10px] font-mono px-1.5 py-0.5 rounded border border-space-600 text-ink-300 hover:text-accent hover:border-accent"
      >
        Why?
      </button>
      {open && (
        <span id={id} role="tooltip" className="absolute z-20 left-0 top-full mt-1 w-64 panel text-xs text-ink-300 shadow-xl">
          <span className="block">{text}</span>
          {formula && <code className="block mt-1.5 text-accent font-mono">{formula}</code>}
          <span className="block mt-1.5 italic">Simplified prototype model.</span>
          <Link className="block mt-1.5 text-accent underline" to={`/sources#${sourceId}`}>See sources</Link>
        </span>
      )}
    </span>
  )
}
