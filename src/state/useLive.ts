import { liveQuery } from 'dexie'
import { useEffect, useState } from 'react'

/**
 * Subscribes to a Dexie live query: re-renders whenever any table it read from changes
 * (including writes made from another tab). Returns undefined until the first result.
 */
export function useLive<T>(querier: () => Promise<T> | T, deps: readonly unknown[] = []): T | undefined {
  const [value, setValue] = useState<T | undefined>(undefined)
  useEffect(() => {
    const sub = liveQuery(querier).subscribe({
      next: setValue,
      error: (e) => console.error('Logbook query failed', e),
    })
    return () => sub.unsubscribe()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)
  return value
}
