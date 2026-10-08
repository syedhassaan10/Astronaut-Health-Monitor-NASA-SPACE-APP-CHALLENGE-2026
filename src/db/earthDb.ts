import Dexie, { type EntityTable } from 'dexie'
import type { DownlinkPacket, PacketSummary } from '../engine/downlink'
import { packetSizeBytes } from '../engine/downlink'

/** A packet as stored on the Earth side. */
export interface EarthPacketRow {
  id: string
  /** When Earth received it (epoch ms). */
  receivedAt: number
  /** When the astronaut built it. */
  createdAt: number
  missionDay: number
  sizeBytes: number
  via: 'link' | 'import'
  /** Null for a CSV-only import (no summary JSON). */
  summary: PacketSummary | null
  csv: string
}

/**
 * Earth's own store. It is a separate IndexedDB database from the astronaut logbook
 * (`orbitfit`), so the Earth tab only ever sees what was actually downlinked or imported.
 */
export class EarthDB extends Dexie {
  packets!: EntityTable<EarthPacketRow, 'id'>

  constructor(name = 'orbitfit-earth') {
    super(name)
    this.version(1).stores({ packets: 'id, receivedAt, missionDay' })
  }
}

export const earthDb = new EarthDB()

/**
 * Stores a packet unless one with the same id is already there (idempotent: retries and
 * duplicate deliveries never create a second copy). The check and the write share one
 * transaction, so two simultaneous deliveries cannot both insert.
 */
export async function storePacket(
  packet: DownlinkPacket, via: EarthPacketRow['via'], database: EarthDB = earthDb, now: number = Date.now(),
): Promise<{ duplicate: boolean }> {
  return database.transaction('rw', database.packets, async () => {
    if (await database.packets.get(packet.id)) return { duplicate: true }
    await database.packets.add({
      id: packet.id, receivedAt: now, createdAt: packet.createdAt, missionDay: packet.missionDay,
      sizeBytes: packetSizeBytes(packet), via, summary: packet.summary, csv: packet.csv,
    })
    return { duplicate: false }
  })
}

/** Stores a CSV-only import as a packet without a summary. */
export async function storeCsvOnly(
  id: string, missionDay: number, csv: string, database: EarthDB = earthDb, now: number = Date.now(),
): Promise<{ duplicate: boolean }> {
  return database.transaction('rw', database.packets, async () => {
    if (await database.packets.get(id)) return { duplicate: true }
    await database.packets.add({
      id, receivedAt: now, createdAt: now, missionDay, sizeBytes: new TextEncoder().encode(csv).length,
      via: 'import', summary: null, csv,
    })
    return { duplicate: false }
  })
}
