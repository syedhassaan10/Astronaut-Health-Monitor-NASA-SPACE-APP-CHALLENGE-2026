// Simplified location presets (gravity as a fraction of Earth g).
// Phase 2 builds the countermeasure engine on top of these.
export interface Location {
  id: string
  label: string
  g: number
}

export const LOCATIONS: Location[] = [
  { id: 'earth', label: 'Earth (1.0 g)', g: 1.0 },
  { id: 'leo', label: 'LEO / ISS (0 g)', g: 0 },
  { id: 'transit', label: 'Deep Space Transit (0 g)', g: 0 },
  { id: 'moon', label: 'Moon (0.166 g)', g: 0.166 },
  { id: 'mars', label: 'Mars (0.38 g)', g: 0.38 },
  { id: 'custom', label: 'Custom', g: 0.5 },
]
