// NASA references used by OrbitFit. URLs were checked against NASA pages / NTRS records.
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
    title: 'Risk of Reduced Physical Performance Capabilities Due to Reduced Muscle Size, Strength, and Endurance (Muscle Risk)',
    organization: 'NASA Human Research Program (Human Health and Performance)',
    url: 'https://www.nasa.gov/directorates/esdmd/hhp/risk-of-impaired-performance-due-to-reduced-muscle-size-strength-and-endurance/',
    usedFor:
      'Why unloading in microgravity reduces muscle size, strength and endurance, and why countermeasure exercise is needed. Motivates the gravity-scaled target load and the deconditioning trend rules.',
  },
  {
    id: 'hrp-bone',
    title: 'Evidence Report: Risk of Bone Fracture due to Spaceflight-induced Changes to Bone (2017)',
    organization: 'NASA Human Research Program',
    url: 'https://ntrs.nasa.gov/citations/20170004597',
    usedFor:
      'Bone mineral density declines of roughly 1–1.5% per month at weight-bearing sites on 4–6 month missions. Context only: OrbitFit does NOT estimate bone density.',
  },
  {
    id: 'iss-exercise',
    title: 'Human Research Program Advanced Exercise Concepts (AEC) Overview (Perusek et al., 2015)',
    organization: 'NASA Human Research Program, via NASA Technical Reports Server',
    url: 'https://ntrs.nasa.gov/citations/20160012339',
    usedFor:
      'Describes the ISS exercise hardware used as the model: ARED, T2 treadmill and CEVIS. Basis for the ARED load maximum (~272 kg / 600 lb) and the resistive-exercise staples. The ~2 h/day figure is a simplified approximation, not taken from this report.',
  },
  {
    id: 'iss-exercise-2024',
    title: 'Effects of Replacing Treadmill Running with Alternative Exercise Countermeasures During Long-Duration Spaceflight (Varanoske et al., 2024)',
    organization: 'NASA, via NASA Technical Reports Server',
    url: 'https://ntrs.nasa.gov/citations/20240000929',
    usedFor: 'Recent evidence comparing ISS countermeasure devices (ARED, T2, CEVIS) for exploration-class exercise planning.',
  },
  {
    id: 'hrp-sleep',
    title: 'Risk of Performance Decrements and Adverse Health Outcomes Resulting from Sleep Loss, Circadian Desynchronization, and Work Overload',
    organization: 'NASA Human Research Program (Human Health and Performance)',
    url: 'https://www.nasa.gov/directorates/esdmd/hhp/risk-of-performance-decrements-and-adverse-health-outcomes-resulting-from-sleep-loss-circadian-desynchronization-and-work-overload/',
    usedFor: 'Why poor sleep and high fatigue matter on missions, and why the daily check-in flags them and treats them as context for slower or less consistent reps.',
  },
  {
    id: 'hrp-behavioral',
    title: 'Risk of Adverse Cognitive or Behavioral Changes and Psychiatric Disorders Leading to In-mission Health and Performance and Long-term Health Effects (Behavioral Health Risk)',
    organization: 'NASA Human Research Program (Human Health and Performance)',
    url: 'https://www.nasa.gov/directorates/esdmd/hhp/risk-of-adverse-cognitive-or-behavioral-conditions-and-psychiatric-disorders/',
    usedFor: 'Isolation and confinement as a hazard: why the check-in tracks stress and mood, and why sustained high stress is surfaced for the Crew Medical Officer.',
  },
  {
    id: 'demo-video',
    title: 'Demo Mode clip: "A Woman Doing Squats" (stock video, downscaled)',
    organization: 'Julia Larson, via Pexels (Pexels License: free to use)',
    url: 'https://www.pexels.com/video/a-woman-doing-squats-6454275/',
    usedFor:
      'Sample exercise video bundled in public/demo so Demo Mode runs without a webcam. Re-encoded to 480x854 for size; not a NASA source.',
  },
]

export const SOURCE_BY_ID: Record<string, Source> = Object.fromEntries(SOURCES.map((s) => [s.id, s]))
