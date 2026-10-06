import { FilesetResolver, PoseLandmarker } from '@mediapipe/tasks-vision'

// Everything is loaded from OUR OWN origin (public/mediapipe/wasm, public/models):
// no CDN, no third-party request at runtime.
let cached: Promise<PoseLandmarker> | null = null

async function create(): Promise<PoseLandmarker> {
  const base = import.meta.env.BASE_URL
  const fileset = await FilesetResolver.forVisionTasks(`${base}mediapipe/wasm`)
  const options = (delegate: 'GPU' | 'CPU') => ({
    baseOptions: { modelAssetPath: `${base}models/pose_landmarker_lite.task`, delegate },
    runningMode: 'VIDEO' as const,
    numPoses: 1,
    minPoseDetectionConfidence: 0.5,
    minPosePresenceConfidence: 0.5,
    minTrackingConfidence: 0.5,
  })
  try {
    return await PoseLandmarker.createFromOptions(fileset, options('GPU'))
  } catch {
    return await PoseLandmarker.createFromOptions(fileset, options('CPU'))
  }
}

export function loadPoseLandmarker(): Promise<PoseLandmarker> {
  cached ??= create().catch((e) => {
    cached = null // allow retry after a failure
    throw e
  })
  return cached
}
