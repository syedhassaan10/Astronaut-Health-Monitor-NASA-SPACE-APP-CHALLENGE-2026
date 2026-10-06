import { useState } from 'react'
import Page from '../components/Page'
import CountermeasureCard from '../components/CountermeasureCard'
import CameraPanel from '../components/CameraPanel'
import CheckInForm from '../components/CheckInForm'
import MyStatus from '../components/MyStatus'
import { useApp } from '../state/AppState'
import { CREW } from '../data/crew'
import { EXERCISES, EXERCISE_IDS, type ExerciseId } from '../engine/gravityEngine'

export default function Crew() {
  const a = useApp()
  const [exercise, setExercise] = useState<ExerciseId>('squat')
  const member = CREW.find((c) => c.id === a.crewId) ?? CREW[0]!
  return (
    <Page title="Astronaut view" subtitle="Workout + daily self-check.">
      <div className="panel">
        <p className="label-mono">Active crew member</p>
        <p className="text-lg mt-1">{member.name} <span className="text-ink-500">· {member.role}</span></p>
        <div role="radiogroup" aria-label="Exercise" className="flex flex-wrap gap-2 mt-3">
          {EXERCISE_IDS.map((id) => (
            <button key={id} type="button" role="radio" aria-checked={exercise === id} onClick={() => setExercise(id)}
              className={`px-3 py-1.5 rounded-md text-sm border ${exercise === id ? 'border-accent text-accent bg-space-900' : 'border-space-600 text-ink-300 hover:bg-space-700'}`}>
              {EXERCISES[id].label}
            </button>
          ))}
        </div>
      </div>
      <CheckInForm crewId={member.id} crewName={member.name} />
      <MyStatus crewId={member.id} />
      <CountermeasureCard massKg={member.massKg} g={a.g} exercise={exercise} />
      <CameraPanel exercise={exercise} g={a.g} />
    </Page>
  )
}
