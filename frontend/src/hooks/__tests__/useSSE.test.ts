import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useSSE } from '../useSSE'
import type { AgentLogEntry, GenerateResponse } from '../../types'

// Helper to build a ReadableStream from SSE lines
function buildSSEStream(lines: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const line of lines) {
        controller.enqueue(encoder.encode(line))
      }
      controller.close()
    },
  })
}

function makeFetchResponse(stream: ReadableStream<Uint8Array>, contentType = 'text/event-stream'): Response {
  return {
    ok: true,
    status: 200,
    headers: {
      get: (key: string) => (key === 'content-type' ? contentType : null),
    },
    body: stream,
  } as unknown as Response
}

const mockAgentLog: AgentLogEntry = {
  phase: 'A',
  action: 'start',
  content: 'Excel構造を分析中...',
  timestamp: '2024-01-01T00:00:00Z',
}

const mockCompleteResponse: GenerateResponse = {
  id: 'gen-001',
  summary: 'Excelの集計処理',
  python_code: 'import pandas as pd',
  steps: ['ステップ1'],
  tips: 'ヒント',
}

describe('useSSE', () => {
  let mockFetch: ReturnType<typeof vi.fn>

  beforeEach(() => {
    mockFetch = vi.fn()
    global.fetch = mockFetch
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('starts with isStreaming false', () => {
    const { result } = renderHook(() => useSSE({
      onEvent: vi.fn(),
      onComplete: vi.fn(),
      onError: vi.fn(),
    }))

    expect(result.current.isStreaming).toBe(false)
  })

  it('exposes start and abort functions', () => {
    const { result } = renderHook(() => useSSE({
      onEvent: vi.fn(),
      onComplete: vi.fn(),
      onError: vi.fn(),
    }))

    expect(typeof result.current.start).toBe('function')
    expect(typeof result.current.abort).toBe('function')
  })

  it('sets isStreaming to true when start is called', async () => {
    // Never-resolving fetch to keep streaming state
    mockFetch.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => useSSE({
      onEvent: vi.fn(),
      onComplete: vi.fn(),
      onError: vi.fn(),
    }))

    act(() => {
      result.current.start('テスト', 'file-123')
    })

    expect(result.current.isStreaming).toBe(true)
  })

  it('calls fetch with POST and correct headers', async () => {
    mockFetch.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => useSSE({
      onEvent: vi.fn(),
      onComplete: vi.fn(),
      onError: vi.fn(),
    }))

    act(() => {
      result.current.start('テスト', 'file-abc')
    })

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/generate',
      expect.objectContaining({
        method: 'POST',
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        body: JSON.stringify({ task: 'テスト', file_id: 'file-abc' }),
      })
    )
  })

  it('calls fetch without file_id when not provided', async () => {
    mockFetch.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => useSSE({
      onEvent: vi.fn(),
      onComplete: vi.fn(),
      onError: vi.fn(),
    }))

    act(() => {
      result.current.start('タスクのみ')
    })

    expect(mockFetch).toHaveBeenCalledWith(
      '/api/generate',
      expect.objectContaining({
        body: JSON.stringify({ task: 'タスクのみ' }),
      })
    )
  })

  it('calls onEvent for each agent log SSE event', async () => {
    const sseLines = [
      `data: ${JSON.stringify(mockAgentLog)}\n\n`,
      `data: ${JSON.stringify({ ...mockAgentLog, phase: 'B', action: 'done', content: '完了' })}\n\n`,
    ]
    const stream = buildSSEStream(sseLines)
    mockFetch.mockResolvedValue(makeFetchResponse(stream))

    const onEvent = vi.fn()
    const { result } = renderHook(() => useSSE({
      onEvent,
      onComplete: vi.fn(),
      onError: vi.fn(),
    }))

    await act(async () => {
      result.current.start('テスト')
      // Allow microtasks to settle
      await new Promise(r => setTimeout(r, 50))
    })

    expect(onEvent).toHaveBeenCalledWith(mockAgentLog)
    expect(onEvent).toHaveBeenCalledWith(
      expect.objectContaining({ phase: 'B', action: 'done' })
    )
  })

  it('calls onComplete with parsed GenerateResponse when phase is "complete"', async () => {
    const completeEvent: AgentLogEntry = {
      phase: 'complete',
      action: 'done',
      content: JSON.stringify(mockCompleteResponse),
      timestamp: '2024-01-01T00:00:00Z',
    }
    const sseLines = [`data: ${JSON.stringify(completeEvent)}\n\n`]
    const stream = buildSSEStream(sseLines)
    mockFetch.mockResolvedValue(makeFetchResponse(stream))

    const onComplete = vi.fn()
    const { result } = renderHook(() => useSSE({
      onEvent: vi.fn(),
      onComplete,
      onError: vi.fn(),
    }))

    await act(async () => {
      result.current.start('テスト')
      await new Promise(r => setTimeout(r, 50))
    })

    expect(onComplete).toHaveBeenCalledWith(mockCompleteResponse)
  })

  it('does not call onEvent for complete event', async () => {
    const completeEvent: AgentLogEntry = {
      phase: 'complete',
      action: 'done',
      content: JSON.stringify(mockCompleteResponse),
      timestamp: '2024-01-01T00:00:00Z',
    }
    const sseLines = [`data: ${JSON.stringify(completeEvent)}\n\n`]
    const stream = buildSSEStream(sseLines)
    mockFetch.mockResolvedValue(makeFetchResponse(stream))

    const onEvent = vi.fn()
    const { result } = renderHook(() => useSSE({
      onEvent,
      onComplete: vi.fn(),
      onError: vi.fn(),
    }))

    await act(async () => {
      result.current.start('テスト')
      await new Promise(r => setTimeout(r, 50))
    })

    expect(onEvent).not.toHaveBeenCalled()
  })

  it('sets isStreaming to false after stream completes', async () => {
    const completeEvent: AgentLogEntry = {
      phase: 'complete',
      action: 'done',
      content: JSON.stringify(mockCompleteResponse),
      timestamp: '2024-01-01T00:00:00Z',
    }
    const sseLines = [`data: ${JSON.stringify(completeEvent)}\n\n`]
    const stream = buildSSEStream(sseLines)
    mockFetch.mockResolvedValue(makeFetchResponse(stream))

    const { result } = renderHook(() => useSSE({
      onEvent: vi.fn(),
      onComplete: vi.fn(),
      onError: vi.fn(),
    }))

    await act(async () => {
      result.current.start('テスト')
      await new Promise(r => setTimeout(r, 50))
    })

    expect(result.current.isStreaming).toBe(false)
  })

  it('calls onError when fetch fails', async () => {
    mockFetch.mockRejectedValue(new Error('Network error'))

    const onError = vi.fn()
    const { result } = renderHook(() => useSSE({
      onEvent: vi.fn(),
      onComplete: vi.fn(),
      onError,
    }))

    await act(async () => {
      result.current.start('テスト')
      await new Promise(r => setTimeout(r, 50))
    })

    expect(onError).toHaveBeenCalledWith('Network error')
    expect(result.current.isStreaming).toBe(false)
  })

  it('calls onError when response is not ok', async () => {
    mockFetch.mockResolvedValue({
      ok: false,
      status: 500,
      headers: { get: () => null },
    })

    const onError = vi.fn()
    const { result } = renderHook(() => useSSE({
      onEvent: vi.fn(),
      onComplete: vi.fn(),
      onError,
    }))

    await act(async () => {
      result.current.start('テスト')
      await new Promise(r => setTimeout(r, 50))
    })

    expect(onError).toHaveBeenCalledWith(expect.stringContaining('500'))
    expect(result.current.isStreaming).toBe(false)
  })

  it('calls onError when response body is null', async () => {
    mockFetch.mockResolvedValue({
      ok: true,
      status: 200,
      headers: { get: () => 'text/event-stream' },
      body: null,
    })

    const onError = vi.fn()
    const { result } = renderHook(() => useSSE({
      onEvent: vi.fn(),
      onComplete: vi.fn(),
      onError,
    }))

    await act(async () => {
      result.current.start('テスト')
      await new Promise(r => setTimeout(r, 50))
    })

    expect(onError).toHaveBeenCalled()
    expect(result.current.isStreaming).toBe(false)
  })

  it('abort sets isStreaming to false', async () => {
    mockFetch.mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => useSSE({
      onEvent: vi.fn(),
      onComplete: vi.fn(),
      onError: vi.fn(),
    }))

    act(() => {
      result.current.start('テスト')
    })

    expect(result.current.isStreaming).toBe(true)

    act(() => {
      result.current.abort()
    })

    expect(result.current.isStreaming).toBe(false)
  })

  it('abort cancels in-flight fetch via AbortController', async () => {
    let capturedSignal: AbortSignal | undefined
    mockFetch.mockImplementation((_url: string, opts: RequestInit) => {
      capturedSignal = opts.signal as AbortSignal
      return new Promise(() => {})
    })

    const { result } = renderHook(() => useSSE({
      onEvent: vi.fn(),
      onComplete: vi.fn(),
      onError: vi.fn(),
    }))

    act(() => {
      result.current.start('テスト')
    })

    act(() => {
      result.current.abort()
    })

    expect(capturedSignal?.aborted).toBe(true)
  })

  it('ignores lines that do not start with "data:"', async () => {
    const sseLines = [
      'event: ping\n',
      ': keep-alive\n',
      `data: ${JSON.stringify(mockAgentLog)}\n\n`,
    ]
    const stream = buildSSEStream(sseLines)
    mockFetch.mockResolvedValue(makeFetchResponse(stream))

    const onEvent = vi.fn()
    const { result } = renderHook(() => useSSE({
      onEvent,
      onComplete: vi.fn(),
      onError: vi.fn(),
    }))

    await act(async () => {
      result.current.start('テスト')
      await new Promise(r => setTimeout(r, 50))
    })

    expect(onEvent).toHaveBeenCalledTimes(1)
    expect(onEvent).toHaveBeenCalledWith(mockAgentLog)
  })

  it('skips malformed JSON without calling onError', async () => {
    const sseLines = [
      'data: {invalid json}\n\n',
      `data: ${JSON.stringify(mockAgentLog)}\n\n`,
    ]
    const stream = buildSSEStream(sseLines)
    mockFetch.mockResolvedValue(makeFetchResponse(stream))

    const onEvent = vi.fn()
    const onError = vi.fn()
    const { result } = renderHook(() => useSSE({
      onEvent,
      onComplete: vi.fn(),
      onError,
    }))

    await act(async () => {
      result.current.start('テスト')
      await new Promise(r => setTimeout(r, 50))
    })

    // Valid event still processed
    expect(onEvent).toHaveBeenCalledTimes(1)
    // No fatal error
    expect(onError).not.toHaveBeenCalled()
  })

  it('handles multi-chunk SSE data split across reads', async () => {
    const encoder = new TextEncoder()
    const fullLine = `data: ${JSON.stringify(mockAgentLog)}\n\n`
    const half = Math.floor(fullLine.length / 2)
    const chunk1 = fullLine.slice(0, half)
    const chunk2 = fullLine.slice(half)

    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(encoder.encode(chunk1))
        controller.enqueue(encoder.encode(chunk2))
        controller.close()
      },
    })
    mockFetch.mockResolvedValue(makeFetchResponse(stream))

    const onEvent = vi.fn()
    const { result } = renderHook(() => useSSE({
      onEvent,
      onComplete: vi.fn(),
      onError: vi.fn(),
    }))

    await act(async () => {
      result.current.start('テスト')
      await new Promise(r => setTimeout(r, 50))
    })

    expect(onEvent).toHaveBeenCalledWith(mockAgentLog)
  })
})
