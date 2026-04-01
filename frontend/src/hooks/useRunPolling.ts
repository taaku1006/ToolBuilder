import { useCallback, useEffect, useRef } from 'react'
import { type RunStatus, getRunStatus } from '../api/eval'

export function useRunPolling(onPoll: (status: RunStatus) => void) {
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const onPollRef = useRef(onPoll)

  // Keep onPollRef in sync without re-creating startPolling
  onPollRef.current = onPoll

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current)
      pollRef.current = null
    }
  }, [])

  const startPolling = useCallback(
    (runId: string) => {
      stopPolling()
      pollRef.current = setInterval(async () => {
        try {
          const status = await getRunStatus(runId)
          onPollRef.current(status)
          if (status.status !== 'running') {
            stopPolling()
          }
        } catch {
          stopPolling()
        }
      }, 2000)
    },
    [stopPolling],
  )

  useEffect(() => {
    return () => stopPolling()
  }, [stopPolling])

  return { startPolling, stopPolling }
}
