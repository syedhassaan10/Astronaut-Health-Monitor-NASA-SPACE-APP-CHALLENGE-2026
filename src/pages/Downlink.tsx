import { useSearchParams } from 'react-router-dom'
import Page from '../components/Page'
import { useApp } from '../state/AppState'

export default function Downlink() {
  const [params] = useSearchParams()
  const earth = params.get('role') === 'earth'
  const a = useApp()
  return (
    <Page
      title={earth ? 'Earth receiver' : 'Earth downlink'}
      subtitle={earth ? 'Receives flight surgeon packets (simulated).' : 'Packet builder for the flight surgeon (simulated).'}
    >
      <div className="panel text-sm text-ink-300">
        Comms: <span className="font-mono">{a.comms}</span>. The packet builder and BroadcastChannel transfer arrive in Phase 7.
      </div>
    </Page>
  )
}
