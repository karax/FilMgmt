import { useEffect, useState } from 'react'

import { elapsedMinutes } from '../lib/printJobs'

export function useElapsedMinutes(startedAt: string | null): number | null {
  const [now, setNow] = useState(Date.now())

  useEffect(() => {
    if (!startedAt) return
    const interval = window.setInterval(() => setNow(Date.now()), 60_000)
    return () => window.clearInterval(interval)
  }, [startedAt])

  return elapsedMinutes(startedAt, now)
}
