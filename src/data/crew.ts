// Placeholder crew roster (demo data is seeded in Phase 8).
export interface CrewMember {
  id: string
  name: string
  role: string
  massKg: number
}

export const CREW: CrewMember[] = [
  { id: 'c1', name: 'Cmdr. A. Rivera', role: 'Commander', massKg: 78 },
  { id: 'c2', name: 'Dr. M. Okafor', role: 'Crew Medical Officer', massKg: 70 },
  { id: 'c3', name: 'Eng. K. Tanaka', role: 'Flight Engineer', massKg: 66 },
]
