import { useEffect, useId, useState, type ReactNode } from 'react'
import type { BodyLocation, CheckIn } from '../engine/healthTypes'
import { LOCATION_LABEL } from '../engine/checkinRules'
import { TODAY, saveCheckin } from '../db/repo'
import { useCheckins } from '../state/useCheckins'

function Slider({ label, low, high, value, onChange, hint }: {
  label: string; low: string; high: string; value: number; onChange: (v: number) => void; hint?: ReactNode
}) {
  const id = useId()
  return (
    <div>
      <div className="flex items-baseline justify-between gap-2">
        <label htmlFor={id} className="text-sm font-medium">{label}</label>
        <output htmlFor={id} className="font-mono text-accent text-lg w-8 text-right">{value}</output>
      </div>
      <input id={id} type="range" min={0} max={10} step={1} value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        aria-valuetext={`${value} out of 10. 0 is ${low}, 10 is ${high}.`}
        className="w-full accent-sky-400" />
      <div className="flex justify-between text-[11px] text-ink-500 -mt-1"><span>0 · {low}</span><span>{high} · 10</span></div>
      {hint}
    </div>
  )
}

const LOCATIONS = Object.keys(LOCATION_LABEL) as BodyLocation[]

/** The daily 30-second self-check. One entry per crew member per mission day (saving again replaces it). */
export default function CheckInForm({ crewId, crewName }: { crewId: string; crewName: string }) {
  const all = useCheckins()
  const existing = all.find((c) => c.crewId === crewId && c.day === TODAY)

  const [sleep, setSleep] = useState(7)
  const [fatigue, setFatigue] = useState(3)
  const [pain, setPain] = useState(0)
  const [location, setLocation] = useState<BodyLocation | ''>('')
  const [stress, setStress] = useState(3)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Prefill with today's entry when the crew member changes (or one already exists).
  useEffect(() => {
    setSleep(existing?.sleep ?? 7)
    setFatigue(existing?.fatigue ?? 3)
    setPain(existing?.pain ?? 0)
    setLocation(existing?.painLocation ?? '')
    setStress(existing?.stress ?? 3)
    setSaved(false)
    setError(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [crewId])

  async function submit(e: React.FormEvent) {
    e.preventDefault()
    if (pain > 0 && location === '') {
      setError('Please choose where it hurts.')
      return
    }
    setError(null)
    const entry: Omit<CheckIn, 'id'> = {
      crewId, day: TODAY, sleep, fatigue, pain, stress,
      painLocation: pain > 0 ? (location || 'other') : null,
    }
    try {
      await saveCheckin(entry)
      setSaved(true)
    } catch {
      setError('Could not save to the logbook. Please try again.')
    }
  }

  return (
    <form className="panel" onSubmit={submit} aria-label="Daily check-in">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">Daily check-in <span className="text-ink-500 font-normal text-sm">· about 30 seconds</span></h2>
        <span className="label-mono">{crewName} · mission day {TODAY}</span>
      </div>
      <p className="text-sm text-ink-300 mt-1">
        How are you today? Your answers sit next to your exercise trends so the Crew Medical Officer sees the whole picture.
        This is self-reported decision support, not a diagnosis.
      </p>

      <div className="grid gap-5 mt-4 sm:grid-cols-2">
        <Slider label="Sleep quality" low="very poor" high="excellent" value={sleep} onChange={setSleep} />
        <Slider label="Fatigue" low="fresh" high="exhausted" value={fatigue} onChange={setFatigue} />
        <Slider label="Muscle / joint pain" low="none" high="worst imaginable" value={pain} onChange={setPain}
          hint={pain > 0 && (
            <div className="mt-2">
              <label className="text-sm" htmlFor="pain-loc">Where does it hurt?</label>
              <select id="pain-loc" value={location} onChange={(e) => setLocation(e.target.value as BodyLocation | '')}
                aria-invalid={error ? true : undefined}
                className="ml-2 bg-space-900 border border-space-600 rounded-md px-2 py-1 text-sm">
                <option value="">Choose…</option>
                {LOCATIONS.map((l) => <option key={l} value={l}>{LOCATION_LABEL[l]}</option>)}
              </select>
            </div>
          )} />
        <Slider label="Mood / stress" low="calm" high="very stressed" value={stress} onChange={setStress} />
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button type="submit" className="px-4 py-2 rounded-md bg-accent text-space-950 font-semibold hover:brightness-110">
          {existing ? 'Update today’s check-in' : 'Save check-in'}
        </button>
        {error && <p role="alert" className="text-sm text-act">{error}</p>}
        {saved && <p role="status" className="text-sm text-nominal">Saved for mission day {TODAY}. Your status below has been updated.</p>}
      </div>
    </form>
  )
}
