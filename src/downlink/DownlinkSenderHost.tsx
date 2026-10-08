import { useEffect, useRef } from 'react'
import { useApp } from '../state/AppState'
import { CHANNEL_NAME } from './protocol'
import { DownlinkSender } from './sender'

/**
 * Runs the astronaut-side downlink in the background on every page (not just /downlink), so a
 * queued packet is sent as soon as the comms window opens wherever the user is in the app.
 * Not mounted in the Earth tab. Renders nothing.
 */
export default function DownlinkSenderHost() {
  const app = useApp()
  const cfg = useRef({ windowOpen: false, latencyMs: 10_000 })
  cfg.current = { windowOpen: app.comms === 'WINDOW OPEN', latencyMs: app.latencyMin * 1000 } // 1 simulated minute = 1 second

  useEffect(() => {
    if (typeof BroadcastChannel === 'undefined') return
    const channel = new BroadcastChannel(CHANNEL_NAME)
    const sender = new DownlinkSender({ channel, getConfig: () => cfg.current })
    sender.start(500)
    return () => {
      sender.stop()
      channel.close()
    }
  }, [])

  return null
}
