// NASA references used by OrbitFit. URLs were checked against NASA pages / NTRS records.
// (Non-NASA credits and the challenge-dataset placeholders are further down.)
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
    id: 'hrp-hazards',
    title: '5 Hazards of Human Spaceflight',
    organization: 'NASA Human Research Program',
    url: 'https://www.nasa.gov/hrp/hazards',
    usedFor:
      'Frames the problem: gravity (and the lack of it), isolation and confinement, and distance from Earth are the three hazards OrbitFit addresses. Radiation and closed or hostile environments are not addressed.',
  },
]

export const SOURCE_BY_ID: Record<string, Source> = Object.fromEntries(SOURCES.map((s) => [s.id, s]))

/** Non-NASA material the prototype is built on, with the licence terms that apply. */
export interface Credit {
  id: string
  title: string
  author: string
  url: string
  licence: string
  usedFor: string
}

export const CREDITS: Credit[] = [
  {
    id: 'mediapipe',
    title: 'MediaPipe Pose Landmarker (pose_landmarker_lite model and @mediapipe/tasks-vision)',
    author: 'Google (MediaPipe / Google AI Edge)',
    url: 'https://developers.google.com/edge/mediapipe/solutions/vision/pose_landmarker',
    licence: 'Models: Creative Commons Attribution 4.0. Code: Apache 2.0 (as stated on the guide page).',
    usedFor:
      'On-device body pose estimation. The model file and WebAssembly runtime are served from this app’s own origin and run in the browser; no video or image ever leaves the device.',
  },
  {
    id: 'demo-video',
    title: 'Demo Mode clip: “A Woman Doing Squats” (stock video, downscaled to 480x854)',
    author: 'Julia Larson, via Pexels',
    url: 'https://www.pexels.com/video/a-woman-doing-squats-6454275/',
    licence: 'Pexels License (free to use).',
    usedFor: 'Sample exercise video bundled in public/demo so Demo Mode works without a webcam. It is not a NASA source.',
  },
]

/**
 * Datasets named in the official 2026 NASA Space Apps challenge statement.
 * PLACEHOLDERS: fill in from the statement. OrbitFit currently uses NO external dataset at
 * runtime; all demo data is synthetic and generated in src/data/demoSeed.ts.
 */
export interface ChallengeDataset {
  id: string
  name: string
  url: string
  usedFor: string
}

export const CHALLENGE_STATEMENT_SITE = 'https://www.spaceappschallenge.org/'

export const CHALLENGE_DATASETS: ChallengeDataset[] = [
  { id: 'dataset-1', name: '[PLACEHOLDER] Dataset 1 name', url: '', usedFor: '[PLACEHOLDER] How OrbitFit uses it, or “not used yet”.' },
  { id: 'dataset-2', name: '[PLACEHOLDER] Dataset 2 name', url: '', usedFor: '[PLACEHOLDER] How OrbitFit uses it, or “not used yet”.' },
  { id: 'dataset-3', name: '[PLACEHOLDER] Dataset 3 name', url: '', usedFor: '[PLACEHOLDER] How OrbitFit uses it, or “not used yet”.' },
]
