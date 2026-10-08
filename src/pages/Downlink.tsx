import { useSearchParams } from 'react-router-dom'
import EarthView from '../components/downlink/EarthView'
import SenderView from '../components/downlink/SenderView'
import Page from '../components/Page'

/** /downlink is the astronaut's packet builder; /downlink?role=earth is the (simulated) Earth receiver. */
export default function Downlink() {
  const [params] = useSearchParams()
  const earth = params.get('role') === 'earth'
  return (
    <Page
      title={earth ? 'Earth receiver' : 'Earth downlink'}
      subtitle={earth ? 'Receives flight surgeon packets from the astronaut tab (simulated).' : 'Build a flight surgeon packet and send it to Earth when a comms window opens (simulated).'}
    >
      {earth ? <EarthView /> : <SenderView />}
    </Page>
  )
}
