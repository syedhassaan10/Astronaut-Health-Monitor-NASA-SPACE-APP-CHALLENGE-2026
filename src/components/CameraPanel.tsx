import { useEffect, useMemo, useRef, useState } from 'react'
import { REP_CONFIGS } from '../engine/repDetector'
import { EXERCISES, type ExerciseId } from '../engine/gravityEngine'
import { useMeasurement } from '../pose/useMeasurement'
import { LEVEL_COLOR } from '../pose/drawOverlay'
import PerfHud from './PerfHud'
import ResumeBanner from './ResumeBanner'
import RepTable from './RepTable'

const DEMO_URL = `${import.meta.env.BASE_URL}demo/squat.mp4`

const btn = 'px-3 py-1.5 rounded-md text-sm border border-space-600 text-ink-100 hover:bg-space-700 disabled:opacity-40 disabled:hover:bg-transparent'

export default function CameraPanel({
  exercise, g, crewId, massKg, onSwitch,
}: {
  exercise: ExerciseId
  g: number
  crewId: string
  massKg: number
  /** Called before resuming so the page can select the session's crew member and exercise. */
  onSwitch: (crewId: string, exercise: ExerciseId) => void
}) {
  const videoRef = useRef<HTMLVideoElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const ctx = useMemo(() => ({ crewId, massKg }), [crewId, massKg])
  const m = useMeasurement(videoRef, canvasRef, exercise, g, ctx)
  const [demoAvailable, setDemoAvailable] = useState<boolean | null>(null)
  const supported = REP_CONFIGS[exercise] !== undefined
  const active = m.status === 'running'

  // The SPA fallback answers 200 + HTML for missing files, so check the content type.
  useEffect(() => {
    let cancelled = false
    fetch(DEMO_URL, { method: 'HEAD' })
      .then((r) => !cancelled && setDemoAvailable(r.ok && (r.headers.get('content-type') ?? '').startsWith('video')))
      .catch(() => !cancelled && setDemoAvailable(false))
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="panel" aria-label="Camera measurement">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">Camera measurement</h2>
        <span className="label-mono">on-device pose estimate · every rep is saved to the offline logbook as it completes</span>
      </div>

      <ResumeBanner
        busy={m.status === 'running' || m.status === 'loading'}
        resumed={m.resumed}
        onResume={(s) => {
          onSwitch(s.crewId, s.exercise)
          void m.resume(s)
        }}
        onFinish={(s) => void m.closeUnfinished(s)}
      />
      {m.logError && (
        <p role="alert" className="mt-2 text-sm text-act">
          Logbook write failed: {m.logError}. Recent reps may not be saved. Check that browser storage is not full or blocked.
        </p>
      )}

      {!supported && (
        <p role="note" className="mt-2 text-sm text-watch">
          Camera rep detection supports squat and deadlift (knee-angle based) in this prototype. Select one of those to measure.
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2 mt-3">
        {!active ? (
          <>
            <button type="button" className={btn} disabled={!supported || m.status === 'loading'} onClick={() => void m.start({ kind: 'webcam' })}>
              {m.status === 'loading' ? 'Loading model…' : 'Start webcam'}
            </button>
            <button type="button" className={btn} disabled={!supported || m.status === 'loading' || demoAvailable === false}
              onClick={() => void m.start({ kind: 'video', url: DEMO_URL, label: 'Demo video' })}
              title={demoAvailable === false ? 'Demo clip not installed yet (see note below)' : undefined}>
              Demo Mode
            </button>
            <button type="button" className={btn} disabled={!supported || m.status === 'loading'} onClick={() => fileRef.current?.click()}>
              Use video file…
            </button>
            <input ref={fileRef} type="file" accept="video/*" className="hidden" aria-label="Choose an exercise video file"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) void m.start({ kind: 'video', url: URL.createObjectURL(f), label: f.name, revoke: true })
                e.target.value = ''
              }} />
          </>
        ) : (
          <button type="button" className={btn} onClick={m.stop}>Stop</button>
        )}

        <div role="radiogroup" aria-label="Sampling mode" className="flex ml-auto rounded-md border border-space-600 overflow-hidden">
          {(['adaptive', 'full'] as const).map((mode) => (
            <button key={mode} type="button" role="radio" aria-checked={m.mode === mode} onClick={() => m.setMode(mode)}
              disabled={m.bench !== null}
              className={`px-3 py-1.5 text-sm ${m.mode === mode ? 'bg-space-700 text-accent' : 'text-ink-300 hover:bg-space-800'}`}>
              {mode === 'adaptive' ? 'Adaptive' : 'Full (every frame)'}
            </button>
          ))}
        </div>
      </div>

      {demoAvailable === false && !active && (
        <p className="mt-2 text-xs text-ink-500">
          Demo Mode needs a clip at <code className="font-mono text-ink-300">public/demo/squat.mp4</code> (not bundled yet). Until then, use
          “Use video file…” with any side-view squat video.
        </p>
      )}
      {m.error && <p role="alert" className="mt-2 text-sm text-act">{m.error}</p>}

      <div className="relative mt-3 bg-black rounded-lg overflow-hidden aspect-video max-h-[28rem]">
        <video ref={videoRef} playsInline muted className={`absolute inset-0 w-full h-full object-contain ${m.sourceLabel === 'Webcam' ? '-scale-x-100' : ''}`} />
        <canvas ref={canvasRef} className="absolute inset-0 w-full h-full object-contain pointer-events-none" aria-hidden="true" />
        {!active && m.status !== 'loading' && (
          <p className="absolute inset-0 grid place-items-center text-ink-500 text-sm p-4 text-center">
            Start the webcam, Demo Mode or a video file to measure knee angle, depth, tempo and symmetry.
          </p>
        )}
        {active && (
          <div className="absolute top-2 left-2 right-2 flex flex-wrap gap-2 pointer-events-none">
            <span className="font-mono text-xs bg-space-950/80 rounded px-2 py-1">{m.sourceLabel}</span>
            <span className="font-mono text-xs bg-space-950/80 rounded px-2 py-1">
              Knee {m.live.knee !== null ? `${m.live.knee.toFixed(0)}°` : '—'}
            </span>
            <span className="font-mono text-xs bg-space-950/80 rounded px-2 py-1">Confidence {(m.live.confidence * 100).toFixed(0)}%</span>
            <span className="font-mono text-xs rounded px-2 py-1 bg-space-950/80" style={{ color: LEVEL_COLOR[m.live.level] }}>● Form</span>
          </div>
        )}
        {active && !m.live.present && (
          <p role="status" className="absolute bottom-2 left-2 right-2 text-center text-sm bg-space-950/85 text-watch rounded px-2 py-1">
            No person detected — step into frame so hips, knees and ankles are visible.
          </p>
        )}
        {m.bannerVisible && (
          <p role="alert" className="absolute bottom-2 left-2 right-2 text-center text-sm font-semibold bg-act/90 text-space-950 rounded px-2 py-1">
            Measurement unreliable — reposition camera
          </p>
        )}
      </div>

      <div className="mt-3 grid gap-4 lg:grid-cols-2">
        <PerfHud stats={m.stats} mode={m.mode} bench={m.bench} benchResult={m.benchResult} canBench={active} onBench={m.startBenchmark} />
        <RepTable reps={m.reps} partials={m.partials} rejected={m.rejected} exerciseLabel={EXERCISES[exercise].label} />
      </div>
    </section>
  )
}
