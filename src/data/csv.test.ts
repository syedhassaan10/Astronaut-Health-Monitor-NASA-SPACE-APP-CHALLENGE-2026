import { describe, expect, it } from 'vitest'
import { BOM, encodeCsv, guardText, parseCsv, unguardText } from './csv'
import { COLUMNS, MAX_ROWS, parseLogbookCsv, toLogbookCsv, type LogbookData } from './logbookCsv'
import { gzipText, readTextMaybeGzip } from './gzip'

describe('csv encode / parse', () => {
  const tricky = [
    ['plain', 'with,comma', 'with "quotes"', 'multi\nline', ' leading', 'trailing ', '', 'ünïcödé ✓', 'a\r\nb'],
    ['x', '', '', 'y', '"', ',', '""', "it's", '=SUM(A1)'],
  ]

  it('round-trips awkward cells exactly', () => {
    expect(parseCsv(encodeCsv(tricky))).toEqual(tricky)
  })

  it('uses CRLF line endings (what Excel expects) and ends with one', () => {
    const t = encodeCsv([['a', 'b'], ['c', 'd']])
    expect(t).toBe('a,b\r\nc,d\r\n')
  })

  it('strips a UTF-8 BOM', () => {
    expect(parseCsv(`${BOM}a,b\r\n1,2\r\n`)).toEqual([['a', 'b'], ['1', '2']])
  })

  it('accepts CRLF, LF and CR line endings and skips blank lines', () => {
    expect(parseCsv('a,b\r\n1,2\n3,4\r5,6\n\n\r\n')).toEqual([['a', 'b'], ['1', '2'], ['3', '4'], ['5', '6']])
  })

  it('keeps an empty trailing cell and a final line without newline', () => {
    expect(parseCsv('a,b,\n1,2,3')).toEqual([['a', 'b', ''], ['1', '2', '3']])
  })

  it('throws on an unterminated quote instead of swallowing the file', () => {
    expect(() => parseCsv('a,"b\n1,2')).toThrow(/never closed/)
  })

  it('formula-injection guard is reversible and only touches dangerous prefixes', () => {
    for (const v of ['=1+1', '+cmd', '-2', '@x', '\tx']) {
      expect(guardText(v).startsWith("'")).toBe(true)
      expect(unguardText(guardText(v))).toBe(v)
    }
    expect(guardText('s-123')).toBe('s-123')
    expect(unguardText("it's")).toBe("it's")
  })
})

const data: LogbookData = {
  sessions: [{
    id: 's-1', crewId: 'c1', exercise: 'squat', day: 30, gravityG: 0, targetLoadKg: 110.5, prescribedReps: 24,
    status: 'completed', startedAt: Date.UTC(2026, 9, 7, 10, 0, 0), endedAt: Date.UTC(2026, 9, 7, 10, 20, 0), source: 'webcam',
  }],
  reps: [
    { id: 's-1#1', sessionId: 's-1', crewId: 'c1', exercise: 'squat', timestamp: Date.UTC(2026, 9, 7, 10, 1, 0), gravityG: 0,
      targetLoadKg: 110.5, repNo: 1, minKneeAngle: 94.1234, eccentricS: 3.2, concentricS: 1.1, asymmetry: 2.5, confidence: 0.93,
      formScore: 90, flags: ['fast-concentric', 'asymmetry'], level: 'amber' },
    { id: 's-1#2', sessionId: 's-1', crewId: 'c1', exercise: 'squat', timestamp: Date.UTC(2026, 9, 7, 10, 1, 6), gravityG: 0,
      targetLoadKg: 110.5, repNo: 2, minKneeAngle: 96, eccentricS: 3, concentricS: 1, asymmetry: 3, confidence: 0.9,
      formScore: 100, flags: [], level: 'green' },
  ],
  checkins: [
    { id: 'c1:d30', crewId: 'c1', day: 30, sleep: 6, fatigue: 4, pain: 5, painLocation: 'knee', stress: 3 },
    { id: 'c1:d29', crewId: 'c1', day: 29, sleep: 7, fatigue: 3, pain: 0, painLocation: null, stress: 2 },
  ],
}

describe('logbook CSV', () => {
  it('starts with a BOM, has the header and CRLF line endings', () => {
    const t = toLogbookCsv(data)
    expect(t.startsWith(BOM)).toBe(true)
    expect(t.slice(1).startsWith(COLUMNS.join(','))).toBe(true)
    expect(t).toContain('\r\n')
    expect(t.replace(/\r\n/g, '').includes('\n')).toBe(false) // no bare LF anywhere
  })

  it('every row has the same number of cells as the header', () => {
    const rows = parseCsv(toLogbookCsv(data))
    expect(rows).toHaveLength(1 + 1 + 2 + 2)
    for (const r of rows) expect(r).toHaveLength(COLUMNS.length)
  })

  it('round-trips sessions, reps and check-ins', () => {
    const p = parseLogbookCsv(toLogbookCsv(data))
    expect(p.errors).toEqual([])
    expect(p.sessions).toEqual(data.sessions)
    expect(p.reps).toEqual(data.reps)
    expect(p.checkins).toEqual(data.checkins)
  })

  it('rounds long decimals to 4 places', () => {
    const d: LogbookData = { ...data, reps: [{ ...data.reps[0]!, minKneeAngle: 94.123456789 }] }
    expect(parseLogbookCsv(toLogbookCsv(d)).reps[0]?.minKneeAngle).toBe(94.1235)
  })

  it('imports a session as completed even if it was exported as active (no phantom Resume prompt)', () => {
    const d: LogbookData = { sessions: [{ ...data.sessions[0]!, status: 'active', endedAt: null }], reps: [], checkins: [] }
    const p = parseLogbookCsv(toLogbookCsv(d))
    expect(p.sessions[0]?.status).toBe('completed')
    expect(p.sessions[0]?.endedAt).toBeNull()
  })

  it('neutralises spreadsheet formulas in text cells and restores them on import', () => {
    const d: LogbookData = { ...data, checkins: [], reps: [], sessions: [{ ...data.sessions[0]!, id: '=HYPERLINK("x")', crewId: '@c1' }] }
    const t = toLogbookCsv(d)
    expect(t).toContain("'=HYPERLINK")
    expect(t).not.toMatch(/(^|,)=HYPERLINK/m)
    const p = parseLogbookCsv(t)
    expect(p.sessions[0]?.id).toBe('=HYPERLINK("x")')
    expect(p.sessions[0]?.crewId).toBe('@c1')
  })

  it('understands a file saved by Excel (reordered/extra columns, LF endings, no BOM)', () => {
    const csv = 'extra,record,id,crewId,day,sleep,fatigue,pain,painLocation,stress\n' +
      'ignored,checkin,whatever,c2,12,7,3,0,,2\n'
    const p = parseLogbookCsv(csv)
    expect(p.errors).toEqual([])
    expect(p.checkins).toEqual([{ id: 'c2:d12', crewId: 'c2', day: 12, sleep: 7, fatigue: 3, pain: 0, painLocation: null, stress: 2 }])
  })

  it('reports invalid rows with line numbers but still imports the valid ones', () => {
    const head = COLUMNS.join(',')
    const good = 'checkin,c1:d1,,1,,c1,,,,,,,,,,,,,,,,,,7,3,0,,2'
    const badRange = 'checkin,c1:d2,,2,,c1,,,,,,,,,,,,,,,,,,11,3,0,,2' // sleep 11
    const badNum = 'checkin,c1:d3,,3,,c1,,,,,,,,,,,,,,,,,,abc,3,0,,2'
    const badRecord = 'banana,x'
    const p = parseLogbookCsv([head, good, badRange, badNum, badRecord].join('\r\n'))
    expect(p.checkins).toHaveLength(1)
    expect(p.errors.map((e) => e.line)).toEqual([3, 4, 5])
    expect(p.errors[0]?.message).toMatch(/sleep.*between 0 and 10/)
    expect(p.errors[1]?.message).toMatch(/not a number/)
    expect(p.errors[2]?.message).toMatch(/unknown record type/)
  })

  it('rejects out-of-range reps, unknown exercises, bad dates and unknown levels', () => {
    const head = COLUMNS.join(',')
    const base = { ...data.reps[0]! }
    const variants = [
      toLogbookCsv({ ...data, sessions: [], checkins: [], reps: [{ ...base, confidence: 1.5 }] }),
      toLogbookCsv({ ...data, sessions: [], checkins: [], reps: [{ ...base, minKneeAngle: 400 }] }),
      toLogbookCsv({ ...data, sessions: [], checkins: [], reps: [{ ...base, repNo: 0 }] }),
      toLogbookCsv({ ...data, sessions: [], checkins: [], reps: [{ ...base, exercise: 'burpee' as never }] }),
      // a hand-edited file with a garbage date (cannot be produced by our own exporter)
      toLogbookCsv({ ...data, sessions: [], checkins: [], reps: [base] }).replace('2026-10-07T10:01:00.000Z', 'not-a-date'),
    ]
    for (const v of variants) {
      const p = parseLogbookCsv(v)
      expect(p.reps).toHaveLength(0)
      expect(p.errors.length).toBeGreaterThan(0)
    }
    expect(head).toContain('record')
  })

  it('rejects a file that is not an OrbitFit logbook', () => {
    const p = parseLogbookCsv('name,age\r\nann,5\r\n')
    expect(p.errors[0]?.message).toMatch(/Not an OrbitFit logbook/)
    expect(p.sessions.length + p.reps.length + p.checkins.length).toBe(0)
  })

  it('reports malformed CSV instead of throwing', () => {
    const p = parseLogbookCsv('record,id\r\nrep,"oops')
    expect(p.errors).toHaveLength(1)
    expect(p.errors[0]?.message).toMatch(/never closed/)
  })

  it('refuses files over the row limit', () => {
    const rows = ['record,id', ...Array.from({ length: MAX_ROWS + 1 }, () => 'x,y')].join('\n')
    expect(parseLogbookCsv(rows).errors[0]?.message).toMatch(/Too many rows/)
  })
})

describe('gzip', () => {
  it('round-trips CSV text, including the BOM and non-ASCII characters', async () => {
    const text = toLogbookCsv(data) + 'ünï ✓\r\n'
    const gz = await gzipText(text)
    expect(gz.size).toBeLessThan(text.length)
    expect(await readTextMaybeGzip(gz)).toBe(text)
  })

  it('detects gzip by its magic bytes, not by file name, and also reads plain CSV', async () => {
    const plain = new Blob(['record,id\r\n'])
    expect(await readTextMaybeGzip(plain)).toBe('record,id\r\n')
    const gz = await gzipText('hello')
    expect(new Uint8Array(await gz.slice(0, 2).arrayBuffer())).toEqual(new Uint8Array([0x1f, 0x8b]))
  })

  it('aborts a decompression bomb instead of exhausting memory', async () => {
    const bomb = await gzipText('a'.repeat(5_000_000))
    await expect(readTextMaybeGzip(bomb, 1_000_000)).rejects.toThrow(/too large/)
  })
})
