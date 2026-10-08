import { useEffect, useRef, useState } from 'react'
import { db } from '../db/db'
import { setNote } from '../db/repo'
import { useLive } from '../state/useLive'

/** Free-text CMO note for one crew member. Saved to the logbook automatically as you type. */
export default function CmoNote({ crewId, name }: { crewId: string; name: string }) {
  const stored = useLive(async () => (await db.cmoNotes.get(crewId)) ?? null, [crewId])
  const [text, setText] = useState('')
  const [savedAt, setSavedAt] = useState<number | null>(null)
  const [error, setError] = useState(false)
  const loaded = useRef(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Load the stored text once; later live updates must not overwrite what is being typed.
  useEffect(() => {
    if (stored === undefined || loaded.current) return
    loaded.current = true
    setText(stored?.text ?? '')
    setSavedAt(stored?.updatedAt ?? null)
  }, [stored])

  // Flush a pending save if the page is left mid-typing.
  useEffect(() => () => { if (timer.current) clearTimeout(timer.current) }, [])

  function change(v: string) {
    setText(v)
    if (timer.current) clearTimeout(timer.current)
    timer.current = setTimeout(() => {
      setNote(crewId, v).then(() => { setSavedAt(Date.now()); setError(false) }, () => setError(true))
    }, 500)
  }

  return (
    <section className="panel" aria-label={`CMO notes for ${name}`}>
      <label htmlFor={`note-${crewId}`} className="text-sm font-semibold">{name}</label>
      <textarea id={`note-${crewId}`} value={text} onChange={(e) => change(e.target.value)} rows={4} maxLength={5000}
        placeholder="Notes for the next review, follow-ups, what was agreed with the crew member…"
        className="mt-2 w-full bg-space-900 border border-space-600 rounded-md p-2 text-sm" />
      <p className="text-xs mt-1" role="status">
        {error ? <span className="text-act">Could not save this note.</span>
          : savedAt ? <span className="text-ink-500">Saved {new Date(savedAt).toLocaleTimeString()}</span>
          : <span className="text-ink-500">Saved automatically.</span>}
      </p>
    </section>
  )
}
