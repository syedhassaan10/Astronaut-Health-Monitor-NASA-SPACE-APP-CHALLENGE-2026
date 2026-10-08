import { useCallback, useEffect, useRef, useState, type RefObject } from 'react'
import { AdaptiveSampler, DEFAULT_SAMPLER, type SamplingMode } from '../engine/adaptiveSampler'
import { assessRep, targetsFor, type Level } from '../engine/formFeedback'
import { buildPlan, tempoForG, volumeForG, type ExerciseId } from '../engine/gravityEngine'
import { PerfStats, type PerfSnapshot } from '../engine/perfStats'
import { jointAngles, meanVisibility, type Vec3 } from '../engine/poseMath'
import { REP_CONFIGS, RepDetector, type RepMetrics } from '../engine/repDetector'
import { addRep, finishSession, repId, sessionReps, startSession } from '../db/repo'
import type { RepRow, SessionRow } from '../db/schema'
import { makeBenchResult, saveBenchmark, type BenchResult, type BenchRow } from '../data/benchmark'
import { drawOverlay } from './drawOverlay'
import { loadPoseLandmarker } from './poseLandmarker'

export type Source = { kind: 'webcam' } | { kind: 'video'; url: string; label: string; revoke?: boolean }
export type Status = 'idle' | 'loading' | 'running' | 'error'

/** A rep as shown in the rep log (live, or restored from the logbook when resuming). */
export interface RepRecord {
  repNo: number
  minKneeAngle: number
  eccentricS: number
  concentricS: number
  asymmetryDeg: number
  confidence: number
  assessment: { overall: Level; score: number; flags: string[] }
}

export interface MeasureContext {
  crewId: string
  massKg: number
}

const toRecord = (r: RepRow): RepRecord => ({
  repNo: r.repNo, minKneeAngle: r.minKneeAngle, eccentricS: r.eccentricS, concentricS: r.concentricS,
  asymmetryDeg: r.asymmetry, confidence: r.confidence, assessment: { overall: r.level, score: r.formScore, flags: r.flags },
})

export interface Live {
  present: boolean
  knee: number | null
  confidence: number
  level: Level | 'neutral'
}

export interface BenchState {
  phase: 'full' | 'adaptive'
  elapsedS: number
}

type Landmark = { x: number; y: number; z: number; visibility?: number }

const BENCH_SECONDS = 30
/** A frame below this confidence is not fed to the rep detector at all. */
const MIN_FRAME_CONF = 0.3
/** Live banner threshold: below this the user is told to reposition the camera. */
const UNRELIABLE_CONF = 0.5
const EMPTY_LIVE: Live = { present: false, knee: null, confidence: 0, level: 'neutral' }

const errMsg = (e: unknown) => (e instanceof Error ? e.message : String(e))

type Cancel = () => void
function scheduleFrame(video: HTMLVideoElement, cb: (now: number) => void): Cancel {
  if ('requestVideoFrameCallback' in video) {
    const id = video.requestVideoFrameCallback((now) => cb(now))
    return () => video.cancelVideoFrameCallback(id)
  }
  const id = requestAnimationFrame(cb)
  return () => cancelAnimationFrame(id)
}

export function useMeasurement(
  videoRef: RefObject<HTMLVideoElement | null>,
  canvasRef: RefObject<HTMLCanvasElement | null>,
  exercise: ExerciseId,
  g: number,
  ctx: MeasureContext,
) {
  const [status, setStatus] = useState<Status>('idle')
  const [error, setError] = useState<string | null>(null)
  const [sourceLabel, setSourceLabel] = useState('')
  const [mode, setModeState] = useState<SamplingMode>('adaptive')
  const [reps, setReps] = useState<RepRecord[]>([])
  const [partials, setPartials] = useState(0)
  const [rejected, setRejected] = useState(0)
  const [live, setLive] = useState<Live>(EMPTY_LIVE)
  const [stats, setStats] = useState<PerfSnapshot | null>(null)
  const [bench, setBench] = useState<BenchState | null>(null)
  const [benchResult, setBenchResult] = useState<BenchResult | null>(null)
  const [bannerUntil, setBannerUntil] = useState(0)
  const [logError, setLogError] = useState<string | null>(null)
  const [resumed, setResumed] = useState<SessionRow | null>(null)

  // Mutable state used inside the frame loop (no re-render per frame).
  const sampler = useRef(new AdaptiveSampler('adaptive', DEFAULT_SAMPLER))
  const perf = useRef(new PerfStats())
  const detector = useRef<RepDetector | null>(null)
  const latest = useRef({ exercise, g })
  const cancel = useRef<Cancel | null>(null)
  const running = useRef(false)
  const stream = useRef<MediaStream | null>(null)
  const revokeUrl = useRef<string | null>(null)
  const lastTs = useRef(0)
  const lastLandmarks = useRef<Landmark[] | null>(null)
  const lastKnee = useRef<number | null>(null)
  const lastLevel = useRef<Level | 'neutral'>('neutral')
  const lastUiMs = useRef(0)
  const lastLive = useRef<Live>(EMPTY_LIVE)
  const mirror = useRef(false)
  const benchRef = useRef<{ phase: 'full' | 'adaptive'; startedAt: number; rows: BenchRow[]; repsAtStart: number; source: string } | null>(null)
  const repCount = useRef(0)
  const sourceRef = useRef<Source | null>(null)
  const ctxRef = useRef(ctx)
  /** The session currently being recorded (null when the camera is off). */
  const sessionRef = useRef<SessionRow | null>(null)
  /** An unfinished session the user chose to resume; the next start() continues it. */
  const pendingResume = useRef<SessionRow | null>(null)
  const nextRepNo = useRef(1)

  useEffect(() => {
    ctxRef.current = ctx
  }, [ctx])

  useEffect(() => {
    latest.current = { exercise, g }
    const cfg = REP_CONFIGS[exercise]
    if (cfg) detector.current?.setConfig(cfg)
  }, [exercise, g])

  const stop = useCallback(() => {
    running.current = false
    cancel.current?.()
    cancel.current = null
    stream.current?.getTracks().forEach((t) => t.stop())
    stream.current = null
    const v = videoRef.current
    if (v) {
      v.pause()
      v.srcObject = null
      v.removeAttribute('src')
      v.load()
    }
    if (revokeUrl.current) URL.revokeObjectURL(revokeUrl.current)
    revokeUrl.current = null
    const c = canvasRef.current
    c?.getContext('2d')?.clearRect(0, 0, c.width, c.height)
    benchRef.current = null
    setBench(null)
    setStatus('idle')
    const done = sessionRef.current
    sessionRef.current = null
    if (done) void finishSession(done.id).catch((e) => setLogError(errMsg(e)))
  }, [videoRef, canvasRef])

  useEffect(() => stop, [stop])

  const finishBenchPhase = useCallback(
    (now: number) => {
      const b = benchRef.current
      if (!b) return
      const snap = perf.current.snapshot(now)
      b.rows.push({
        mode: b.phase,
        seconds: BENCH_SECONDS,
        frames: snap.frames,
        inferences: snap.inferences,
        avgInferenceMs: snap.avgInferenceMs,
        reps: repCount.current - b.repsAtStart,
      })
      if (b.phase === 'full') {
        // Second leg: adaptive on the same source (clip restarted for a fair comparison).
        b.phase = 'adaptive'
        b.startedAt = now
        b.repsAtStart = repCount.current
        sampler.current.setMode('adaptive')
        setModeState('adaptive')
        perf.current.reset()
        detector.current?.reset()
        const v = videoRef.current
        if (v && sourceRef.current?.kind === 'video') v.currentTime = 0
      } else {
        const [full, adaptive] = b.rows as [BenchRow, BenchRow]
        const result = makeBenchResult(b.source, full, adaptive)
        saveBenchmark(result)
        setBenchResult(result)
        benchRef.current = null
        setBench(null)
      }
    },
    [videoRef],
  )

  const handleResult = useCallback((landmarks: Landmark[] | undefined, world: Vec3[] | undefined, now: number) => {
    if (!landmarks || !world) {
      lastLandmarks.current = null
      lastKnee.current = null
      sampler.current.onResult(null, now)
      lastLive.current = EMPTY_LIVE
      return
    }
    lastLandmarks.current = landmarks
    const angles = jointAngles(world)
    const confidence = meanVisibility(landmarks)
    const knee = angles ? angles.knee : null
    lastKnee.current = knee
    sampler.current.onResult(knee, now)
    lastLive.current = { present: true, knee, confidence, level: lastLevel.current }
    if (!angles || confidence < MIN_FRAME_CONF) return

    const det = detector.current
    if (!det) return
    const res = det.push({ tMs: now, knee: angles.knee, asymmetryDeg: Math.abs(angles.kneeL - angles.kneeR), confidence })
    if (!res) return
    // Reps made during the 30 s benchmark are measurement tests, not workout data: never logged.
    const logging = benchRef.current === null

    /** Writes the rep to IndexedDB right now (not at session end) so a crash cannot lose it. */
    const persist = (m: RepMetrics, formScore: number, flags: string[], level: RepRow['level']): number | null => {
      const session = sessionRef.current
      if (!session || !logging) return null
      const { exercise: ex, g: gg } = latest.current
      const repNo = nextRepNo.current++
      const row: RepRow = {
        id: repId(session.id, repNo), sessionId: session.id, crewId: session.crewId, exercise: ex, timestamp: Date.now(),
        gravityG: gg, targetLoadKg: buildPlan(ctxRef.current.massKg, gg, ex).targetLoadKg, repNo,
        minKneeAngle: m.minKneeAngle, eccentricS: m.eccentricS, concentricS: m.concentricS,
        asymmetry: m.asymmetryDeg, confidence: m.confidence, formScore, flags, level,
      }
      addRep(row).then(() => setLogError(null), (e) => setLogError(errMsg(e)))
      return repNo
    }

    if (res.kind === 'partial') {
      setPartials((n) => n + 1)
    } else if (res.kind === 'unreliable') {
      setRejected((n) => n + 1)
      setBannerUntil(performance.now() + 5000)
      persist(res.rep, 0, ['low-confidence'], 'red') // kept for the audit trail; the rules ignore low-confidence reps
    } else {
      const { exercise: ex, g: gg } = latest.current
      const cfg = REP_CONFIGS[ex]
      if (!cfg) return
      const assessment = assessRep(res.rep, targetsFor(cfg, tempoForG(gg)))
      lastLevel.current = assessment.overall
      repCount.current += 1
      const repNo = persist(res.rep, assessment.score, assessment.flags, assessment.overall)
      if (repNo !== null) {
        setReps((r) => [...r, {
          repNo, minKneeAngle: res.rep.minKneeAngle, eccentricS: res.rep.eccentricS, concentricS: res.rep.concentricS,
          asymmetryDeg: res.rep.asymmetryDeg, confidence: res.rep.confidence,
          assessment: { overall: assessment.overall, score: assessment.score, flags: assessment.flags },
        }])
      }
    }
  }, [])

  const loop = useCallback(
    async (now: number) => {
      const video = videoRef.current
      const canvas = canvasRef.current
      if (!running.current || !video) return
      perf.current.onFrame(now)

      if (sampler.current.shouldRun(now)) {
        try {
          const lm = await loadPoseLandmarker()
          const ts = Math.max(lastTs.current + 1, Math.round(now))
          lastTs.current = ts
          const t0 = performance.now()
          const out = lm.detectForVideo(video, ts)
          const t1 = performance.now()
          perf.current.onInference(t1, t1 - t0)
          handleResult(out.landmarks[0], out.worldLandmarks[0], now)
        } catch (e) {
          running.current = false
          setError(e instanceof Error ? e.message : String(e))
          setStatus('error')
          return
        }
      }

      // Live depth colouring while a rep is in progress; last rep's overall level otherwise.
      const cfg = REP_CONFIGS[latest.current.exercise]
      const k = lastKnee.current
      if (cfg && k !== null && detector.current?.currentPhase === 'moving') {
        lastLive.current = { ...lastLive.current, level: k <= cfg.depthTargetDeg + 5 ? 'green' : k <= cfg.depthTargetDeg + 20 ? 'amber' : 'neutral' }
      } else if (lastLive.current.level !== lastLevel.current) {
        lastLive.current = { ...lastLive.current, level: lastLevel.current }
      }

      if (canvas && video.videoWidth) {
        if (canvas.width !== video.videoWidth) {
          canvas.width = video.videoWidth
          canvas.height = video.videoHeight
        }
        drawOverlay(canvas, { landmarks: lastLandmarks.current, mirror: mirror.current, kneeAngle: lastKnee.current, level: lastLive.current.level })
      }

      // Throttled UI updates.
      if (now - lastUiMs.current > 250) {
        lastUiMs.current = now
        setLive(lastLive.current)
        setStats(perf.current.snapshot(now))
        const b = benchRef.current
        if (b) {
          const elapsed = (now - b.startedAt) / 1000
          setBench({ phase: b.phase, elapsedS: Math.min(elapsed, BENCH_SECONDS) })
          if (elapsed >= BENCH_SECONDS) finishBenchPhase(now)
        }
      }

      if (running.current) cancel.current = scheduleFrame(video, (n) => void loop(n))
    },
    [videoRef, canvasRef, handleResult, finishBenchPhase],
  )

  const start = useCallback(
    async (source: Source) => {
      const video = videoRef.current
      if (!video) return
      stop()
      setError(null)
      setStatus('loading')
      const pending = pendingResume.current
      if (!pending) {
        setReps([])
        nextRepNo.current = 1
      }
      setPartials(0)
      setRejected(0)
      setBannerUntil(0)
      repCount.current = 0
      lastLevel.current = 'neutral'
      sourceRef.current = source
      try {
        await loadPoseLandmarker()
        if (source.kind === 'webcam') {
          if (!navigator.mediaDevices?.getUserMedia) throw new Error('Camera access needs HTTPS or http://localhost (secure context).')
          const s = await navigator.mediaDevices.getUserMedia({
            video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
            audio: false,
          })
          stream.current = s
          video.srcObject = s
          mirror.current = true
          setSourceLabel('Webcam')
        } else {
          video.src = source.url
          video.loop = true
          video.muted = true
          if (source.revoke) revokeUrl.current = source.url
          mirror.current = false
          setSourceLabel(source.label)
        }
        video.playsInline = true
        await video.play()
        // Open the logbook session only now that the camera/video is really running.
        if (pending) {
          sessionRef.current = pending // continue the unfinished session; it is still 'active' in the DB
          pendingResume.current = null
          setResumed(null)
        } else {
          const { exercise: ex, g: gg } = latest.current
          const v = volumeForG(gg)
          sessionRef.current = await startSession({
            crewId: ctxRef.current.crewId, exercise: ex, gravityG: gg,
            targetLoadKg: buildPlan(ctxRef.current.massKg, gg, ex).targetLoadKg,
            prescribedReps: v.sets * v.reps, source: source.kind === 'webcam' ? 'webcam' : 'video',
          })
        }
        const cfg = REP_CONFIGS[latest.current.exercise]
        detector.current = cfg ? new RepDetector(cfg) : null
        sampler.current.reset()
        perf.current.reset()
        lastTs.current = 0
        running.current = true
        setStatus('running')
        cancel.current = scheduleFrame(video, (n) => void loop(n))
      } catch (e) {
        stop()
        const msg = e instanceof Error ? e.message : String(e)
        setError(/denied|NotAllowed/i.test(msg) ? 'Camera permission was denied. Allow camera access, or use Demo Mode.' : msg)
        setStatus('error')
      }
    },
    [videoRef, stop, loop],
  )

  /** Restores an unfinished session's reps; the next start() (webcam, demo or file) continues it. */
  const resume = useCallback(async (session: SessionRow) => {
    const rows = await sessionReps(session.id)
    pendingResume.current = session
    nextRepNo.current = rows.reduce((m, r) => Math.max(m, r.repNo), 0) + 1
    setReps(rows.filter((r) => !r.flags.includes('low-confidence')).map(toRecord))
    setResumed(session)
  }, [])

  /** Closes an unfinished session without resuming it. */
  const closeUnfinished = useCallback(async (session: SessionRow) => {
    if (pendingResume.current?.id === session.id) {
      pendingResume.current = null
      setResumed(null)
      setReps([])
    }
    await finishSession(session.id)
  }, [])

  // If the crew member, exercise or gravity changes while recording, close that session and
  // open a fresh one (the camera keeps running) so each session has one set of conditions.
  const lastCtx = useRef({ crewId: ctx.crewId, exercise, g })
  useEffect(() => {
    const prev = lastCtx.current
    lastCtx.current = { crewId: ctx.crewId, exercise, g }
    const session = sessionRef.current
    if (!running.current || !session) return
    if (prev.crewId === ctx.crewId && prev.exercise === exercise && Math.abs(prev.g - g) < 0.001) return
    const v = volumeForG(g)
    sessionRef.current = null
    nextRepNo.current = 1
    setReps([])
    void (async () => {
      try {
        await finishSession(session.id)
        sessionRef.current = await startSession({
          crewId: ctx.crewId, exercise, gravityG: g, targetLoadKg: buildPlan(ctx.massKg, g, exercise).targetLoadKg,
          prescribedReps: v.sets * v.reps, source: session.source === 'webcam' ? 'webcam' : 'video',
        })
      } catch (e) {
        setLogError(errMsg(e))
      }
    })()
  }, [ctx.crewId, ctx.massKg, exercise, g])

  const setMode = useCallback((m: SamplingMode) => {
    sampler.current.setMode(m)
    perf.current.reset()
    setModeState(m)
  }, [])

  const startBenchmark = useCallback(() => {
    if (!running.current) return
    sampler.current.setMode('full')
    setModeState('full')
    perf.current.reset()
    detector.current?.reset()
    const v = videoRef.current
    if (v && sourceRef.current?.kind === 'video') v.currentTime = 0
    const src = sourceRef.current
    benchRef.current = {
      phase: 'full',
      startedAt: performance.now(),
      rows: [],
      repsAtStart: repCount.current,
      source: src?.kind === 'video' ? src.label : 'Webcam',
    }
    setBenchResult(null)
    setBench({ phase: 'full', elapsedS: 0 })
  }, [videoRef])

  const bannerVisible = status === 'running' && ((live.present && live.confidence < UNRELIABLE_CONF) || performance.now() < bannerUntil)

  return { logError, resumed, resume, closeUnfinished, status, error, sourceLabel, mode, setMode, reps, partials, rejected, live, stats, bench, benchResult, bannerVisible, start, stop, startBenchmark }
}
