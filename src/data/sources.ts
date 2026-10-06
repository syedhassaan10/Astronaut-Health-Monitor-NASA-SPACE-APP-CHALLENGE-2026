// NASA references used by OrbitFit. URLs point to stable NASA portals / search
// entry points; confirm the exact record before citing in a publication.
export interface Source {
  id: string
  title: string
  organization: string
  url: string
  usedFor: string
}

export const SOURCES: Source[] = [
  {
    id: 'hrp-muscle-bone',
    title: 'Human Research Program: evidence on spaceflight muscle and bone loss',
    organization: 'NASA Human Research Program',
    url: 'https://humanresearchroadmap.nasa.gov/',
    usedFor:
      'Background for why unloading in microgravity reduces muscle and bone, and why countermeasure exercise is needed. Motivates the gravity-scaled target load and the deconditioning trend rules.',
  },
  {
    id: 'iss-exercise',
    title: 'ISS exercise countermeasures: ARED, T2 treadmill, CEVIS (~2 h/day)',
    organization: 'NASA (International Space Station Program / HRP)',
    url: 'https://ntrs.nasa.gov/search?q=ARED%20advanced%20resistive%20exercise%20device',
    usedFor:
      'Basis for the ARED maximum load (~272 kg / 600 lb), the ~2 h/day exercise budget at 0 g, and the squat / deadlift / heel raise staples. All numbers are simplified in this prototype.',
  },
  {
    id: 'nasa-hrp-portal',
    title: 'NASA Human Research Program',
    organization: 'NASA',
    url: 'https://www.nasa.gov/hrp/',
    usedFor: 'Program overview for the human health and performance risks that OrbitFit relates to.',
  },
]

export const SOURCE_BY_ID: Record<string, Source> = Object.fromEntries(SOURCES.map((s) => [s.id, s]))
