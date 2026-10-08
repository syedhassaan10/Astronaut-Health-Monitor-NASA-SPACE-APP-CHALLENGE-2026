import { useEffect, useState } from 'react'
import { requestPersistentStorage } from '../db/db'
import { ensureSeeded } from '../db/repo'

export type DbState = { status: 'loading' } | { status: 'ready' } | { status: 'error'; message: string }

/** Opens the logbook, seeds the demo data on first run, and asks the browser to keep it. */
export function useDbReady(): DbState {
  const [state, setState] = useState<DbState>({ status: 'loading' })
  useEffect(() => {
    let cancelled = false
    ensureSeeded()
      .then(() => {
        if (!cancelled) setState({ status: 'ready' })
        void requestPersistentStorage()
      })
      .catch((e: unknown) => {
        if (!cancelled) setState({ status: 'error', message: e instanceof Error ? e.message : String(e) })
      })
    return () => {
      cancelled = true
    }
  }, [])
  return state
}
