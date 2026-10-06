import { describe, expect, it } from 'vitest'
import { LOCATIONS } from './locations'

describe('location presets', () => {
  it('has gravity within 0..1 g for every preset', () => {
    for (const l of LOCATIONS) {
      expect(l.g).toBeGreaterThanOrEqual(0)
      expect(l.g).toBeLessThanOrEqual(1)
    }
  })
})
