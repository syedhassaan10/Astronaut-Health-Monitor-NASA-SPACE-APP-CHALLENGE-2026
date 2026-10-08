import 'fake-indexeddb/auto'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import { CREW } from '../data/crew'
import { DEMO_CHECKINS, DEMO_DAYS, DEMO_SESSIONS } from '../data/demoSeed'
import { OrbitDB } from '../db/db'
import { EarthDB, storeCsvOnly, storePacket } from '../db/earthDb'
import { buildPacket, type DownlinkPacket } from '../engine/downlink'
import { CHANNEL_NAME, parseMessage } from './protocol'
import { cancelQueued, enqueuePacket } from './queueRepo'
import { EarthReceiver } from './receiver'
import { DownlinkSender, type SenderConfig } from './sender'

// These tests run the REAL sender and a REAL Earth receiver over real BroadcastChannels.
// Latency is tiny (60 ms) so the whole protocol can be exercised in well under a second each.

const LAT = 60
const MARGIN = 600
let n = 0
let name = ''
let db: OrbitDB
let earth: EarthDB
let cfg: SenderConfig
const channels: BroadcastChannel[] = []
const stoppers: (() => void)[] = []

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms))
const chan = () => {
  const c = new BroadcastChannel(CHANNEL_NAME)
  channels.push(c)
  return c
}
const packet = (id = 'pkt-1', day = DEMO_DAYS): DownlinkPacket =>
  buildPacket({ sessions: DEMO_SESSIONS, checkins: DEMO_CHECKINS, crew: CREW.map((c) => ({ id: c.id, name: c.name, role: c.role })), day, windowDays: 7, id, now: Date.now() })

function makeSender(database = db) {
  const s = new DownlinkSender({ channel: chan(), db: database, getConfig: () => cfg })
  stoppers.push(() => s.stop())
  return s
}
function makeEarth(database = earth, heartbeatMs = 4000) {
  const received: { id: string; duplicate: boolean }[] = []
  const r = new EarthReceiver({ channel: chan(), db: database, heartbeatMs, onPacket: (id, duplicate) => received.push({ id, duplicate }) })
  r.start()
  stoppers.push(() => r.stop())
  return { r, received }
}
/** Ticks the sender(s) repeatedly for `ms`, like the real 500 ms interval but faster. */
async function pump(senders: DownlinkSender[], ms: number, every = 10) {
  const end = Date.now() + ms
  while (Date.now() < end) {
    await Promise.all(senders.map((s) => s.tick()))
    await sleep(every)
  }
}
const queueRow = (id = 'pkt-1') => db.downlinkQueue.get(id)

/** Ticks until `cond` is true (or the deadline passes) and returns how long it took. */
async function until(senders: DownlinkSender[], cond: () => boolean | Promise<boolean>, timeoutMs = 4000): Promise<number> {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    if (await cond()) return Date.now() - start
    await Promise.all(senders.map((s) => s.tick()))
    await sleep(10)
  }
  throw new Error(`condition not met within ${timeoutMs} ms`)
}
const isAcked = async (id = 'pkt-1') => (await db.downlinkQueue.get(id))?.status === 'acked'

beforeEach(() => {
  name = `dl-test-${n++}`
  db = new OrbitDB(name)
  earth = new EarthDB(`${name}-earth`)
  cfg = { windowOpen: false, latencyMs: LAT, retryMarginMs: MARGIN }
})
afterEach(() => {
  stoppers.splice(0).forEach((s) => s())
  channels.splice(0).forEach((c) => c.close())
})

describe('BLACKOUT', () => {
  it('keeps a queued packet queued and sends nothing, however long it waits', async () => {
    await enqueuePacket(packet(), db)
    const { received } = makeEarth()
    const sender = makeSender()
    await pump([sender], 400)
    expect(received).toEqual([])
    expect(await earth.packets.count()).toBe(0)
    expect(await queueRow()).toMatchObject({ status: 'queued', attempts: 0, transmittedAt: null })
  })

  it('the queued packet is still there after a "reload" (new DB connection, new sender)', async () => {
    await enqueuePacket(packet(), db)
    db.close()
    const reopened = new OrbitDB(name)
    const sender = makeSender(reopened)
    await pump([sender], 100)
    expect(await reopened.downlinkQueue.get('pkt-1')).toMatchObject({ status: 'queued' })
    expect(JSON.parse((await reopened.downlinkQueue.get('pkt-1'))!.payload).id).toBe('pkt-1')
  })
})

describe('WINDOW OPEN delivery', () => {
  it('delivers to Earth only AFTER the simulated delay, then Earth ACKs and the packet is acknowledged', async () => {
    await enqueuePacket(packet(), db)
    const { received } = makeEarth()
    const sender = makeSender()
    cfg.windowOpen = true
    const opened = Date.now()

    await pump([sender], LAT * 0.6) // before the delay has elapsed: nothing can have arrived
    expect(received).toEqual([])
    expect((await queueRow())?.status).toBe('sent')

    await until([sender], () => received.length > 0) // arrives once the delay has elapsed
    expect(received.map((r) => r.id)).toEqual(['pkt-1'])
    expect(Date.now() - opened).toBeGreaterThanOrEqual(LAT) // it really took the full simulated delay
    expect(await earth.packets.count()).toBe(1)

    await until([sender], isAcked) // the ACK's return leg
    const row = await queueRow()
    expect(row?.status).toBe('acked')
    expect(row?.ackedAt).not.toBeNull()
    expect(row?.attempts).toBe(1) // delivered first time, no retries
  })

  it('what Earth stores is exactly what was sent', async () => {
    const p = packet()
    await enqueuePacket(p, db)
    makeEarth()
    const sender = makeSender()
    cfg.windowOpen = true
    await until([sender], isAcked)
    const stored = await earth.packets.get('pkt-1')
    expect(stored?.summary).toEqual(p.summary)
    expect(stored?.csv).toBe(p.csv)
    expect(stored?.missionDay).toBe(p.missionDay)
    expect(stored?.via).toBe('link')
  })

  it('a window opened later still delivers a packet that waited through a blackout', async () => {
    await enqueuePacket(packet(), db)
    makeEarth()
    const sender = makeSender()
    await pump([sender], 150) // blackout
    expect(await earth.packets.count()).toBe(0)
    cfg.windowOpen = true
    await until([sender], isAcked)
    expect(await earth.packets.count()).toBe(1)
  })

  it('delivers several packets, each exactly once', async () => {
    for (const id of ['a', 'b', 'c']) await enqueuePacket(packet(id), db)
    const { received } = makeEarth()
    const sender = makeSender()
    cfg.windowOpen = true
    await until([sender], async () => (await Promise.all(['a', 'b', 'c'].map((i) => isAcked(i)))).every(Boolean))
    expect(received.map((r) => r.id).sort()).toEqual(['a', 'b', 'c'])
    expect(await earth.packets.count()).toBe(3)
  })
})

describe('no duplicates', () => {
  it('Earth stores a packet once even if it is delivered several times, and ACKs every time', async () => {
    const { r, received } = makeEarth()
    const p = packet()
    await r.receive(p, 5)
    await r.receive(p, 5)
    await r.receive(p, 5)
    expect(await earth.packets.count()).toBe(1)
    expect(received.map((x) => x.duplicate)).toEqual([false, true, true])
  })

  it('simultaneous deliveries cannot both insert (check + write are one transaction)', async () => {
    const p = packet()
    const results = await Promise.all(Array.from({ length: 8 }, () => storePacket(p, 'link', earth)))
    expect(results.filter((x) => !x.duplicate)).toHaveLength(1)
    expect(await earth.packets.count()).toBe(1)
  })

  it('two astronaut tabs sharing one queue deliver a packet to Earth only once', async () => {
    await enqueuePacket(packet(), db)
    makeEarth()
    const a = makeSender()
    const b = makeSender(new OrbitDB(name)) // a second tab = a second connection to the same database
    cfg.windowOpen = true
    await until([a, b], isAcked)
    await pump([a, b], 250) // keep both tabs running: no late duplicate may appear
    expect(await earth.packets.count()).toBe(1)
    expect((await queueRow())?.status).toBe('acked')
  })

  it('a re-enqueued packet with the same id is not queued twice', async () => {
    const p = packet()
    await enqueuePacket(p, db)
    await enqueuePacket(p, db)
    expect(await db.downlinkQueue.count()).toBe(1)
  })

  it('importing a packet that already arrived over the link does not duplicate it', async () => {
    const p = packet()
    expect((await storePacket(p, 'link', earth)).duplicate).toBe(false)
    expect((await storePacket(p, 'import', earth)).duplicate).toBe(true)
    expect(await earth.packets.count()).toBe(1)
    expect((await earth.packets.get('pkt-1'))?.via).toBe('link') // the original is kept
  })

  it('a CSV-only import is idempotent by its content id', async () => {
    expect((await storeCsvOnly('csv-1', 30, 'a,b\r\n1,2\r\n', earth)).duplicate).toBe(false)
    expect((await storeCsvOnly('csv-1', 30, 'a,b\r\n1,2\r\n', earth)).duplicate).toBe(true)
    expect(await earth.packets.count()).toBe(1)
    expect((await earth.packets.get('csv-1'))?.summary).toBeNull()
  })
})

describe('unreliable link', () => {
  it('Earth tab closed: the transmission is lost, the sender retries, and delivery happens once Earth is back', async () => {
    await enqueuePacket(packet(), db)
    const sender = makeSender()
    cfg.windowOpen = true
    await pump([sender], LAT + 100) // transmitted into the void: nobody is listening
    expect((await queueRow())?.transmittedAt).not.toBeNull()
    expect(await earth.packets.count()).toBe(0)

    const { received } = makeEarth() // Earth tab opens
    await until([sender], isAcked) // the retry fires, then delivery + ACK
    expect(received.filter((r) => !r.duplicate)).toHaveLength(1)
    expect(await earth.packets.count()).toBe(1)
    const row = await queueRow()
    expect(row?.status).toBe('acked')
    expect(row?.attempts).toBeGreaterThanOrEqual(2) // it did have to retry
  })

  it('a blackout that starts while the packet is still in transit sends it back to the queue', async () => {
    await enqueuePacket(packet(), db)
    const { received } = makeEarth()
    const sender = makeSender()
    cfg.windowOpen = true
    await pump([sender], LAT * 0.4)
    expect((await queueRow())?.status).toBe('sent')
    cfg.windowOpen = false // link lost before arrival
    await pump([sender], LAT * 2)
    expect(received).toEqual([])
    expect(await queueRow()).toMatchObject({ status: 'queued', transmittedAt: null })
  })

  it('...and the next window delivers it, once', async () => {
    await enqueuePacket(packet(), db)
    makeEarth()
    const sender = makeSender()
    cfg.windowOpen = true
    await pump([sender], LAT * 0.4)
    cfg.windowOpen = false
    await pump([sender], LAT)
    cfg.windowOpen = true
    await until([sender], isAcked)
    expect(await earth.packets.count()).toBe(1)
  })

  it('an ACK that arrives during a blackout is lost; a later window re-sends and Earth does not duplicate', async () => {
    cfg.latencyMs = 200 // a long return leg gives the test room to close the window while the ACK is in flight
    await enqueuePacket(packet(), db)
    const { received } = makeEarth()
    const sender = makeSender()
    cfg.windowOpen = true
    await until([sender], () => received.length > 0) // delivered; its ACK is now travelling back
    expect(received.map((r) => r.id)).toEqual(['pkt-1'])
    cfg.windowOpen = false // blackout while the ACK is on its way back
    await pump([sender], 320) // the ACK arrives into the blackout and is lost
    expect((await queueRow())?.status).toBe('sent') // ACK never recorded
    cfg.windowOpen = true
    await until([sender], isAcked) // retry -> Earth recognises the duplicate -> ACK
    expect(await earth.packets.count()).toBe(1)
    expect(received.some((r) => r.duplicate)).toBe(true) // it was re-delivered and recognised
  })

  it('a packet cancelled before sending is never delivered', async () => {
    await enqueuePacket(packet(), db)
    makeEarth()
    const sender = makeSender()
    await cancelQueued('pkt-1', db)
    cfg.windowOpen = true
    await pump([sender], LAT * 2 + 150)
    expect(await earth.packets.count()).toBe(0)
  })

  it('an acknowledged packet cannot be cancelled', async () => {
    await enqueuePacket(packet(), db)
    await db.downlinkQueue.update('pkt-1', { status: 'acked', ackedAt: 1 })
    await cancelQueued('pkt-1', db)
    expect(await db.downlinkQueue.count()).toBe(1)
  })
})

describe('Earth presence heartbeat', () => {
  it('the sender notices an Earth tab, and notices it is gone', async () => {
    const sender = makeSender()
    expect(sender.earthOnline).toBe(false)
    makeEarth(earth, 30)
    await sleep(120)
    expect(sender.earthOnline).toBe(true)
  })
})

describe('untrusted messages', () => {
  it('parseMessage rejects anything malformed', () => {
    const p = packet()
    expect(parseMessage(null)).toBeNull()
    expect(parseMessage('x')).toBeNull()
    expect(parseMessage({ type: 'nope' })).toBeNull()
    expect(parseMessage({ type: 'ack' })).toBeNull()
    expect(parseMessage({ type: 'ack', id: 'bad id/with spaces' })).toBeNull()
    expect(parseMessage({ type: 'packet', packet: p })).toBeNull() // no latency
    expect(parseMessage({ type: 'packet', packet: p, latencyMs: -1 })).toBeNull()
    expect(parseMessage({ type: 'packet', packet: p, latencyMs: 1e12 })).toBeNull()
    expect(parseMessage({ type: 'packet', packet: { ...p, id: '' }, latencyMs: 10 })).toBeNull()
    expect(parseMessage({ type: 'packet', packet: p, latencyMs: 10 })?.type).toBe('packet')
    expect(parseMessage({ type: 'ack', id: 'pkt-1' })).toEqual({ type: 'ack', id: 'pkt-1' })
  })

  it('Earth ignores a malformed packet broadcast by something else on the channel', async () => {
    const { received } = makeEarth()
    const rogue = chan()
    rogue.postMessage({ type: 'packet', packet: { id: 'evil', csv: 5 }, latencyMs: 1 })
    rogue.postMessage({ type: 'packet', packet: { ...packet('ok'), version: 99 }, latencyMs: 1 })
    await sleep(120)
    expect(received).toEqual([])
    expect(await earth.packets.count()).toBe(0)
  })

  it('a forged ACK for an unknown packet changes nothing', async () => {
    await enqueuePacket(packet(), db)
    const sender = makeSender()
    cfg.windowOpen = true
    chan().postMessage({ type: 'ack', id: 'does-not-exist' })
    await sleep(80)
    await sender.tick()
    expect(await db.downlinkQueue.count()).toBe(1)
    expect((await queueRow())?.status).not.toBe('acked')
  })
})
