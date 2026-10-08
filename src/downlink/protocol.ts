import { parsePacket, type DownlinkPacket } from '../engine/downlink'

/** BroadcastChannel name shared by the astronaut tab(s) and the Earth tab. */
export const CHANNEL_NAME = 'orbitfit-downlink'

/** Astronaut -> Earth. `latencyMs` tells Earth how long the return leg (the ACK) should take. */
export interface PacketMsg {
  type: 'packet'
  packet: DownlinkPacket
  latencyMs: number
}
/** Earth -> astronaut: "packet <id> received". */
export interface AckMsg {
  type: 'ack'
  id: string
}
/** Earth -> astronaut heartbeat, so the astronaut tab can show whether an Earth tab is listening. */
export interface EarthOnlineMsg {
  type: 'earth-online'
}
export type Message = PacketMsg | AckMsg | EarthOnlineMsg

/** What both sides need from a BroadcastChannel (lets tests use real channels or stubs). */
export interface ChannelLike {
  postMessage(message: unknown): void
  addEventListener(type: 'message', listener: (e: MessageEvent) => void): void
  removeEventListener(type: 'message', listener: (e: MessageEvent) => void): void
  close(): void
}

export const MAX_LATENCY_MS = 60 * 60 * 1000
const ID_RE = /^[A-Za-z0-9_.:-]{1,80}$/

/**
 * Validates an incoming channel message. Anything that does not match exactly is dropped:
 * the channel is open to every same-origin context, so its contents are never trusted.
 */
export function parseMessage(data: unknown): Message | null {
  if (typeof data !== 'object' || data === null) return null
  const m = data as Record<string, unknown>
  if (m.type === 'earth-online') return { type: 'earth-online' }
  if (m.type === 'ack') return typeof m.id === 'string' && ID_RE.test(m.id) ? { type: 'ack', id: m.id } : null
  if (m.type === 'packet') {
    const lat = m.latencyMs
    if (typeof lat !== 'number' || !Number.isFinite(lat) || lat < 0 || lat > MAX_LATENCY_MS) return null
    const parsed = parsePacket(m.packet)
    return parsed.ok ? { type: 'packet', packet: parsed.packet, latencyMs: lat } : null
  }
  return null
}
