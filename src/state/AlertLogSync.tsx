import { useEffect } from 'react'
import { db } from '../db/db'
import { TODAY, addAlertEntries } from '../db/repo'
import { newLogEntries } from '../engine/alertLog'
import { useAssessments } from './useAssessments'
import { useLive } from './useLive'

/**
 * Keeps the persisted alert log up to date: whenever the current assessments contain an alert
 * (or an escalation) that is not logged yet, it is written to the logbook. Renders nothing.
 */
export default function AlertLogSync() {
  const assessments = useAssessments(TODAY)
  const keys = useLive(async () => new Set((await db.alerts.toCollection().primaryKeys()) as string[]))

  useEffect(() => {
    if (!keys) return
    const alerts = Object.values(assessments).flatMap((a) => a.alerts)
    const fresh = newLogEntries(alerts, keys, TODAY)
    if (fresh.length > 0) void addAlertEntries(fresh).catch((e) => console.error('Alert log write failed', e))
  }, [assessments, keys])

  return null
}
