import Page from '../components/Page'
import { useApp } from '../state/AppState'
import { CREW } from '../data/crew'

export default function Crew() {
  const a = useApp()
  const member = CREW.find((c) => c.id === a.crewId) ?? CREW[0]!
  return (
    <Page title="Astronaut view" subtitle="Workout + daily self-check.">
      <div className="panel">
        <p className="label-mono">Active crew member</p>
        <p className="text-lg mt-1">{member.name} <span className="text-ink-500">· {member.role}</span></p>
        <p className="text-sm text-ink-300 mt-2">Gravity: {a.g.toFixed(3)} g. Workout engine arrives in Phase 2; camera measurement in Phase 3.</p>
      </div>
    </Page>
  )
}
