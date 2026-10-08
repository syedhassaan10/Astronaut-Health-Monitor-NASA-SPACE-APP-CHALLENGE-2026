/// <reference types="node" />
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'

// Hard rule from the spec: the UI says "estimate", "trend", "decision support", never "diagnosis".
// The word may appear only to DENY it ("not a diagnosis", "no diagnosis", "never ... diagnosis").

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name)
    if (statSync(p).isDirectory()) return files(p)
    return /\.(ts|tsx)$/.test(name) && !/\.test\.tsx?$/.test(name) ? [p] : []
  })
}

const DENIAL = /\b(not|no|never|nor|nothing|without|avoid|avoids)\b[^.\n]{0,60}diagnos|diagnos[^.\n]{0,40}\b(not|never)\b/i
/** A line that states a limit ("does NOT estimate...", "no bone density") rather than making a claim. */
const NEGATED = /\b(not|no|never|nor|nothing|without|avoid|avoids|cannot)\b/i

describe('wording rules', () => {
  const lines = files('src').flatMap((f) =>
    readFileSync(f, 'utf8').split('\n').map((text, i) => ({ f: f.replace(/\\/g, '/'), n: i + 1, text })),
  )

  it('only uses "diagnos…" to deny it', () => {
    const offenders = lines.filter((l) => /diagnos/i.test(l.text) && !DENIAL.test(l.text))
    expect(offenders.map((o) => `${o.f}:${o.n}: ${o.text.trim()}`)).toEqual([])
  })

  it('shows the persistent prototype disclaimer in the footer', () => {
    const footer = readFileSync('src/components/Footer.tsx', 'utf8')
    expect(footer).toContain('Prototype decision-support tool. Not a medical device. Thresholds are demonstration values, not clinically validated.')
  })

  it('does not claim to measure bone density or muscle mass', () => {
    const claims = lines.filter((l) => /\b(measure|measures|measured|show|shows|display|displays|estimate|estimates|report|reports)\b[^.\n]{0,30}(bone density|muscle mass)/i.test(l.text) && !NEGATED.test(l.text))
    expect(claims.map((o) => `${o.f}:${o.n}`)).toEqual([])
  })
})
