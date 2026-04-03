import { useCallback, useEffect, useRef } from 'react'
import type { RunStatus } from '../api/eval'

/**
 * Stream eval run status via Server-Sent Events.
 *
 * Replaces the previous 2-second polling implementation with a persistent
 * SSE connection. The server only pushes data when the status actually
 * changes, eliminating redundant requests.
 */
export function useRunPolling(onPoll: (status: RunStatus) => void) {
  const abortRef = useRef<AbortController | null>(null)
  const onPollRef = useRef(onPoll)
  onPollRef.current = onPoll

  const stopPolling = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort()
      abortRef.current = null
    }
  }, [])

  const startPolling = useCallback(
    (runId: string) => {
      stopPolling()

      const controller = new AbortController()
      abortRef.current = controller

      void (async () => {
        try {
          const response = await fetch(`/api/eval/run/${runId}/stream`, {
            signal: controller.signal,
          })

          if (!response.ok || response.body == null) {
            stopPolling()
            return
          }

          const reader = response.body.getReader()
          const decoder = new TextDecoder()
          let buffer = ''

          while (true) {
            const { done, value } = await reader.read()
            if (done) break

            buffer += decoder.decode(value, { stream: true })

            let boundary: number
            while ((boundary = buffer.indexOf('\n\n')) !== -1) {
              const message = buffer.slice(0, boundary)
              buffer = buffer.slice(boundary + 2)

              for (const line of message.split('\n')) {
                if (!line.startsWith('data:')) continue
                const json = line.slice(5).trim()
                try {
                  const status = JSON.parse(json) as RunStatus
                  onPollRef.current(status)
                } catch {
                  // skip malformed JSON
                }
              }
            }
          }
        } catch (err: unknown) {
          if (err instanceof Error && err.name === 'AbortError') return
        } finally {
          abortRef.current = null
        }
      })()
    },
    [stopPolling],
  )

  useEffect(() => {
    return () => stopPolling()
  }, [stopPolling])

  return { startPolling, stopPolling }
}
