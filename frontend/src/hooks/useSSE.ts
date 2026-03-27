import { useState, useRef, useCallback } from 'react'
import type { AgentLogEntry, GenerateResponse } from '../types'

export interface UseSSEOptions {
  onEvent: (entry: AgentLogEntry) => void
  onComplete: (response: GenerateResponse) => void
  onError: (error: string) => void
}

export interface UseSSEReturn {
  start: (task: string, fileId?: string) => void
  abort: () => void
  isStreaming: boolean
}

export function useSSE(options: UseSSEOptions): UseSSEReturn {
  const [isStreaming, setIsStreaming] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)

  const abort = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsStreaming(false)
  }, [])

  const start = useCallback(
    (task: string, fileId?: string) => {
      const controller = new AbortController()
      abortControllerRef.current = controller
      setIsStreaming(true)

      const body: Record<string, string> = { task }
      if (fileId != null) {
        body['file_id'] = fileId
      }

      void (async () => {
        try {
          const response = await fetch('/api/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
            signal: controller.signal,
          })

          if (!response.ok) {
            options.onError(`HTTP error: ${response.status}`)
            setIsStreaming(false)
            return
          }

          if (response.body == null) {
            options.onError('Response body is null')
            setIsStreaming(false)
            return
          }

          const reader = response.body.getReader()
          const decoder = new TextDecoder()
          let buffer = ''

          while (true) {
            const { done, value } = await reader.read()
            if (done) break

            buffer += decoder.decode(value, { stream: true })

            // Process all complete SSE messages in buffer
            // SSE messages end with \n\n
            let boundary: number
            while ((boundary = buffer.indexOf('\n\n')) !== -1) {
              const message = buffer.slice(0, boundary)
              buffer = buffer.slice(boundary + 2)

              for (const line of message.split('\n')) {
                if (!line.startsWith('data:')) continue

                const json = line.slice(5).trim()
                let entry: AgentLogEntry
                try {
                  entry = JSON.parse(json) as AgentLogEntry
                } catch {
                  // Skip malformed JSON
                  continue
                }

                if (entry.phase === 'complete') {
                  let parsed: GenerateResponse
                  try {
                    parsed = JSON.parse(entry.content) as GenerateResponse
                  } catch {
                    options.onError('Failed to parse complete response')
                    continue
                  }
                  options.onComplete(parsed)
                } else {
                  options.onEvent(entry)
                }
              }
            }
          }
        } catch (err: unknown) {
          if (err instanceof Error && err.name === 'AbortError') {
            return
          }
          const message = err instanceof Error ? err.message : 'Unknown error'
          options.onError(message)
        } finally {
          setIsStreaming(false)
        }
      })()
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [options.onEvent, options.onComplete, options.onError]
  )

  return { start, abort, isStreaming }
}
