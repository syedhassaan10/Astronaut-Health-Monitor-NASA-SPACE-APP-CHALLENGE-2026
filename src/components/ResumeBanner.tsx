import { CREW } from '../data/crew'
import { db } from '../db/db'
import { listActiveSessions } from '../db/repo'
import type { SessionRow } from '../db/schema'
import { EXERCISES } from '../engine/gravityEngine'
import { useLive } from '../state/useLive'

interface Unfinished {
  session: SessionRow
  reps: number
}

const btn = 'px-3 py-1.5 rounded-md text-sm border border-space-600 hover:bg-space-700'

/**
 * Offered after a reload when a session was never closed (tab closed, crash, power loss).
 * Every rep up to that moment is already in the logbook; resuming restores them and carries on.
 */
export default function ResumeBanner({
  busy, resumed, onResume, onFinish,
}: {
  /** True while the camera is running or loading: nothing to offer then. */
  busy: boolean
  resumed: SessionRow | null
  onResume: (s: SessionRow) => void
  onFinish: (s: SessionRow) => void
}) {
  const unfinished = useLive<Unfinished[]>(async () => {
    const sessions = await listActiveSessions(db)
    return Promise.all(sessions.map(async (session) => ({ session, reps: await db.reps.where('sessionId').equals(session.id).count() })))
  })

  if (busy) return null

  if (resumed) {
    const n = unfinished?.find((u) => u.session.id === resumed.id)?.reps ?? 0
    return (
      <div role="status" className="mt-3 rounded-md border border-accent bg-space-900 p-3 text-sm">
        <p className="font-semibold text-accent">Resuming your {EXERCISES[resumed.exercise].label.toLowerCase()} session</p>
        <p className="text-ink-300 mt-1">
          {n} rep{n === 1 ? '' : 's'} restored from the logbook. Start the webcam, Demo Mode or a video file below to carry on from rep {n + 1}.
        </p>
        <button type="button" className={`${btn} mt-2`} onClick={() => onFinish(resumed)}>Finish without resuming</button>
      </div>
    )
  }

  if (!unfinished || unfinished.length === 0) return null
  return (
    <div role="alert" className="mt-3 rounded-md border border-watch bg-space-900 p-3 text-sm space-y-3">
      <p className="font-semibold text-watch">Unfinished session found</p>
      {unfinished.map(({ session, reps }) => (
        <div key={session.id} className="flex flex-wrap items-center gap-3">
          <p className="text-ink-300 flex-1 min-w-56">
            {EXERCISES[session.exercise].label} · {CREW.find((c) => c.id === session.crewId)?.name ?? session.crewId} ·{' '}
            <strong className="text-ink-100">{reps} rep{reps === 1 ? '' : 's'} saved</strong> · started {new Date(session.startedAt).toLocaleString()}
          </p>
          <button type="button" className={`${btn} border-accent text-accent`} onClick={() => onResume(session)}>Resume session</button>
          <button type="button" className={btn} onClick={() => onFinish(session)}>Finish it</button>
        </div>
      ))}
    </div>
  )
}
