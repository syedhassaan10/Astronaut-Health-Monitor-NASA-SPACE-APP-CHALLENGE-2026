import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { LOCATIONS } from '../data/locations'
import { CREW } from '../data/crew'

export type CommsStatus = 'BLACKOUT' | 'WINDOW OPEN'

interface Persisted {
  crewId: string
  locationId: string
  customG: number
  comms: CommsStatus
  /** Simulated one-way Earth link delay in minutes (5-40). Demo scale: 1 minute = 1 second. */
  latencyMin: number
  quickStartDismissed: boolean
}

interface AppState extends Persisted {
  g: number
  setCrewId: (id: string) => void
  setLocationId: (id: string) => void
  setCustomG: (g: number) => void
  setComms: (c: CommsStatus) => void
  setLatencyMin: (m: number) => void
  setQuickStartDismissed: (v: boolean) => void
  offlineReady: boolean
}

export const LATENCY_MIN = 5
export const LATENCY_MAX = 40

const KEY = 'orbitfit.app'
const DEFAULTS: Persisted = {
  crewId: CREW[0]!.id,
  locationId: 'leo',
  customG: 0.5,
  comms: 'BLACKOUT',
  latencyMin: 10,
  quickStartDismissed: false,
}

// localStorage can throw (private mode, blocked storage); fall back to defaults.
function load(): Persisted {
  try {
    const raw = localStorage.getItem(KEY)
    return raw ? { ...DEFAULTS, ...(JSON.parse(raw) as Partial<Persisted>) } : DEFAULTS
  } catch {
    return DEFAULTS
  }
}

const Ctx = createContext<AppState | null>(null)

export function AppStateProvider({ children }: { children: ReactNode }) {
  const [s, setS] = useState<Persisted>(load)
  const [offlineReady, setOfflineReady] = useState(false)

  useEffect(() => {
    try {
      localStorage.setItem(KEY, JSON.stringify(s))
    } catch {
      /* non-fatal */
    }
  }, [s])

  // Service worker registration; fires onOfflineReady once all assets are precached.
  useEffect(() => {
    let cancelled = false
    import('virtual:pwa-register')
      .then(({ registerSW }) => {
        registerSW({ onOfflineReady: () => !cancelled && setOfflineReady(true) })
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  const patch = useCallback((p: Partial<Persisted>) => setS((prev) => ({ ...prev, ...p })), [])

  const value = useMemo<AppState>(() => {
    const loc = LOCATIONS.find((l) => l.id === s.locationId) ?? LOCATIONS[0]!
    return {
      ...s,
      g: loc.id === 'custom' ? s.customG : loc.g,
      offlineReady,
      setCrewId: (crewId) => patch({ crewId }),
      setLocationId: (locationId) => patch({ locationId }),
      setCustomG: (customG) => patch({ customG }),
      setComms: (comms) => patch({ comms }),
      setLatencyMin: (m) => patch({ latencyMin: Math.min(LATENCY_MAX, Math.max(LATENCY_MIN, Math.round(m))) }),
      setQuickStartDismissed: (quickStartDismissed) => patch({ quickStartDismissed }),
    }
  }, [s, offlineReady, patch])

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useApp(): AppState {
  const v = useContext(Ctx)
  if (!v) throw new Error('useApp must be used inside AppStateProvider')
  return v
}
