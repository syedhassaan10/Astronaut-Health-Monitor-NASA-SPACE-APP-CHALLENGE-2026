import { db as defaultDb, type OrbitDB } from '../db/db'
import type { QueueRow } from '../db/schema'
import { packetSizeBytes, type DownlinkPacket } from '../engine/downlink'

/** Adds a packet to the persisted downlink queue, waiting for a comms window. Idempotent by packet id. */
export async function enqueuePacket(packet: DownlinkPacket, database: OrbitDB = defaultDb, now: number = Date.now()): Promise<QueueRow> {
  const row: QueueRow = {
    id: packet.id, createdAt: now, status: 'queued', payload: JSON.stringify(packet), sizeBytes: packetSizeBytes(packet),
    missionDay: packet.missionDay, sentAt: null, deliverAt: null, transmittedAt: null, ackedAt: null, attempts: 0,
  }
  return database.transaction('rw', database.downlinkQueue, async () => {
    const existing = await database.downlinkQueue.get(row.id)
    if (existing) return existing
    await database.downlinkQueue.add(row)
    return row
  })
}

/** Cancels a packet that has not been acknowledged yet. */
export async function cancelQueued(id: string, database: OrbitDB = defaultDb): Promise<void> {
  await database.transaction('rw', database.downlinkQueue, async () => {
    const row = await database.downlinkQueue.get(id)
    if (row && row.status !== 'acked') await database.downlinkQueue.delete(id)
  })
}

export function listQueue(database: OrbitDB = defaultDb): Promise<QueueRow[]> {
  return database.downlinkQueue.orderBy('createdAt').reverse().toArray()
}
