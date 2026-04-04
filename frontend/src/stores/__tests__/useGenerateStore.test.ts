import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useGenerateStore } from '../useGenerateStore'
import * as generateApi from '../../api/generate'
import type { GenerateResponse, AgentLogEntry } from '../../types'

vi.mock('../../api/generate')

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

const mockResponse: GenerateResponse = {
  id: 'abc-123',
  summary: 'Excelの集計処理',
  python_code: 'import pandas as pd',
  steps: ['ステップ1', 'ステップ2'],
  tips: 'ヒント',
}

const mockLogEntry: AgentLogEntry = {
  phase: 'U',
  action: 'start',
  content: 'タスクとデータを分析中',
  timestamp: '2024-01-01T00:00:00Z',
}

describe('useGenerateStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useGenerateStore.getState().reset()
    })
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  // --- Existing state tests ---

  it('has correct initial state', () => {
    const { result } = renderHook(() => useGenerateStore())

    expect(result.current.task).toBe('')
    expect(result.current.response).toBeNull()
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('setTask updates the task field', () => {
    const { result } = renderHook(() => useGenerateStore())

    act(() => {
      result.current.setTask('新しいタスク')
    })

    expect(result.current.task).toBe('新しいタスク')
  })

  it('generate sets loading false and response on success', async () => {
    vi.mocked(generateApi.postGenerate).mockResolvedValueOnce(mockResponse)

    const { result } = renderHook(() => useGenerateStore())

    act(() => {
      result.current.setTask('テスト')
    })

    await act(async () => {
      await result.current.generate()
    })

    expect(result.current.loading).toBe(false)
    expect(result.current.response).toEqual(mockResponse)
    expect(result.current.error).toBeNull()
  })

  it('generate calls postGenerate with the current task', async () => {
    vi.mocked(generateApi.postGenerate).mockResolvedValueOnce(mockResponse)

    const { result } = renderHook(() => useGenerateStore())

    act(() => {
      result.current.setTask('Excelを処理して')
    })

    await act(async () => {
      await result.current.generate()
    })

    expect(generateApi.postGenerate).toHaveBeenCalledWith('Excelを処理して', undefined)
  })

  it('generate calls postGenerate with fileId when provided', async () => {
    vi.mocked(generateApi.postGenerate).mockResolvedValueOnce(mockResponse)

    const { result } = renderHook(() => useGenerateStore())

    act(() => {
      result.current.setTask('ファイルを処理して')
    })

    await act(async () => {
      await result.current.generate('file-id-123')
    })

    expect(generateApi.postGenerate).toHaveBeenCalledWith('ファイルを処理して', 'file-id-123')
  })

  it('generate sets error on API failure', async () => {
    vi.mocked(generateApi.postGenerate).mockRejectedValueOnce(new Error('API Error'))

    const { result } = renderHook(() => useGenerateStore())

    act(() => {
      result.current.setTask('テスト')
    })

    await act(async () => {
      await result.current.generate()
    })

    expect(result.current.loading).toBe(false)
    expect(result.current.response).toBeNull()
    expect(result.current.error).toBe('コード生成に失敗しました。もう一度お試しください。')
  })

  it('reset clears all state', async () => {
    vi.mocked(generateApi.postGenerate).mockResolvedValueOnce(mockResponse)

    const { result } = renderHook(() => useGenerateStore())

    act(() => {
      result.current.setTask('テスト')
    })

    await act(async () => {
      await result.current.generate()
    })

    act(() => {
      result.current.reset()
    })

    expect(result.current.task).toBe('')
    expect(result.current.response).toBeNull()
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('generate does not call API when task is empty', async () => {
    const { result } = renderHook(() => useGenerateStore())

    await act(async () => {
      await result.current.generate()
    })

    expect(generateApi.postGenerate).not.toHaveBeenCalled()
    expect(result.current.loading).toBe(false)
  })

  // --- New agentLog state tests ---

  it('has initial agentLog as empty array', () => {
    const { result } = renderHook(() => useGenerateStore())
    expect(result.current.agentLog).toEqual([])
  })

  it('has initial isStreaming as false', () => {
    const { result } = renderHook(() => useGenerateStore())
    expect(result.current.isStreaming).toBe(false)
  })

  it('addLogEntry appends an entry to agentLog', () => {
    const { result } = renderHook(() => useGenerateStore())

    act(() => {
      result.current.addLogEntry(mockLogEntry)
    })

    expect(result.current.agentLog).toHaveLength(1)
    expect(result.current.agentLog[0]).toEqual(mockLogEntry)
  })

  it('addLogEntry is immutable — does not mutate previous state', () => {
    const { result } = renderHook(() => useGenerateStore())

    let snapshotBefore: AgentLogEntry[] = []

    act(() => {
      snapshotBefore = result.current.agentLog
      result.current.addLogEntry(mockLogEntry)
    })

    expect(snapshotBefore).toHaveLength(0)
    expect(result.current.agentLog).toHaveLength(1)
  })

  it('addLogEntry accumulates multiple entries in order', () => {
    const { result } = renderHook(() => useGenerateStore())

    const entry2: AgentLogEntry = { ...mockLogEntry, phase: 'B', content: 'ツール合成中' }

    act(() => {
      result.current.addLogEntry(mockLogEntry)
      result.current.addLogEntry(entry2)
    })

    expect(result.current.agentLog).toHaveLength(2)
    expect(result.current.agentLog[0].phase).toBe('A')
    expect(result.current.agentLog[1].phase).toBe('B')
  })

  it('setStreaming updates isStreaming to true', () => {
    const { result } = renderHook(() => useGenerateStore())

    act(() => {
      result.current.setStreaming(true)
    })

    expect(result.current.isStreaming).toBe(true)
  })

  it('setStreaming updates isStreaming to false', () => {
    const { result } = renderHook(() => useGenerateStore())

    act(() => {
      result.current.setStreaming(true)
    })
    act(() => {
      result.current.setStreaming(false)
    })

    expect(result.current.isStreaming).toBe(false)
  })

  it('reset clears agentLog and isStreaming', async () => {
    const { result } = renderHook(() => useGenerateStore())

    act(() => {
      result.current.addLogEntry(mockLogEntry)
      result.current.setStreaming(true)
    })

    act(() => {
      result.current.reset()
    })

    expect(result.current.agentLog).toEqual([])
    expect(result.current.isStreaming).toBe(false)
  })

  // --- generateSSE tests ---

  describe('generateSSE', () => {
    let mockFetch: ReturnType<typeof vi.fn>

    beforeEach(() => {
      mockFetch = vi.fn()
      global.fetch = mockFetch
    })

    it('does not call fetch when task is empty', async () => {
      const { result } = renderHook(() => useGenerateStore())

      await act(async () => {
        await result.current.generateSSE()
      })

      expect(mockFetch).not.toHaveBeenCalled()
      expect(result.current.loading).toBe(false)
    })

    it('sets loading true and clears agentLog before streaming', async () => {
      mockFetch.mockReturnValue(new Promise(() => {}))

      const { result } = renderHook(() => useGenerateStore())

      act(() => {
        result.current.setTask('テスト')
        result.current.addLogEntry(mockLogEntry)
      })

      act(() => {
        void result.current.generateSSE()
      })

      expect(result.current.loading).toBe(true)
      expect(result.current.agentLog).toEqual([])
      expect(result.current.isStreaming).toBe(true)
    })

    it('calls fetch with correct POST body including file_id', async () => {
      mockFetch.mockReturnValue(new Promise(() => {}))

      const { result } = renderHook(() => useGenerateStore())

      act(() => {
        result.current.setTask('Excelを処理して')
      })

      act(() => {
        void result.current.generateSSE('file-123')
      })

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/generate/stream',
        expect.objectContaining({
          method: 'POST',
          headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
          body: JSON.stringify({ task: 'Excelを処理して', file_id: 'file-123' }),
        })
      )
    })

    it('calls fetch without file_id when not provided', async () => {
      mockFetch.mockReturnValue(new Promise(() => {}))

      const { result } = renderHook(() => useGenerateStore())

      act(() => {
        result.current.setTask('タスクのみ')
      })

      act(() => {
        void result.current.generateSSE()
      })

      expect(mockFetch).toHaveBeenCalledWith(
        '/api/generate/stream',
        expect.objectContaining({
          body: JSON.stringify({ task: 'タスクのみ' }),
        })
      )
    })

    it('appends agent_log SSE events to agentLog', async () => {
      const logEntry: AgentLogEntry = {
        phase: 'A',
        action: 'start',
        content: 'Excel構造を分析中...',
        timestamp: '2024-01-01T00:00:00Z',
      }
      const stream = buildSSEStream([`data: ${JSON.stringify(logEntry)}\n\n`])
      mockFetch.mockResolvedValue({ ok: true, status: 200, body: stream })

      const { result } = renderHook(() => useGenerateStore())

      act(() => {
        result.current.setTask('テスト')
      })

      await act(async () => {
        await result.current.generateSSE()
        await new Promise((r) => setTimeout(r, 50))
      })

      expect(result.current.agentLog).toHaveLength(1)
      expect(result.current.agentLog[0]).toEqual(logEntry)
    })

    it('sets response when phase is "complete"', async () => {
      const completeEvent: AgentLogEntry = {
        phase: 'complete',
        action: 'done',
        content: JSON.stringify(mockResponse),
        timestamp: '2024-01-01T00:00:00Z',
      }
      const stream = buildSSEStream([`data: ${JSON.stringify(completeEvent)}\n\n`])
      mockFetch.mockResolvedValue({ ok: true, status: 200, body: stream })

      const { result } = renderHook(() => useGenerateStore())

      act(() => {
        result.current.setTask('テスト')
      })

      await act(async () => {
        await result.current.generateSSE()
        await new Promise((r) => setTimeout(r, 50))
      })

      expect(result.current.response).toEqual(mockResponse)
      expect(result.current.loading).toBe(false)
      expect(result.current.isStreaming).toBe(false)
    })

    it('sets error when phase is "error"', async () => {
      const errorEvent: AgentLogEntry = {
        phase: 'error',
        action: 'error',
        content: 'サーバーエラーが発生しました',
        timestamp: '2024-01-01T00:00:00Z',
      }
      const stream = buildSSEStream([`data: ${JSON.stringify(errorEvent)}\n\n`])
      mockFetch.mockResolvedValue({ ok: true, status: 200, body: stream })

      const { result } = renderHook(() => useGenerateStore())

      act(() => {
        result.current.setTask('テスト')
      })

      await act(async () => {
        await result.current.generateSSE()
        await new Promise((r) => setTimeout(r, 50))
      })

      expect(result.current.error).toBe('サーバーエラーが発生しました')
      expect(result.current.loading).toBe(false)
    })

    it('sets error when fetch response is not ok', async () => {
      mockFetch.mockResolvedValue({ ok: false, status: 500, body: null })

      const { result } = renderHook(() => useGenerateStore())

      act(() => {
        result.current.setTask('テスト')
      })

      await act(async () => {
        await result.current.generateSSE()
        await new Promise((r) => setTimeout(r, 50))
      })

      expect(result.current.error).toBe('コード生成に失敗しました。もう一度お試しください。')
      expect(result.current.loading).toBe(false)
      expect(result.current.isStreaming).toBe(false)
    })

    it('sets error when fetch throws (network error)', async () => {
      mockFetch.mockRejectedValue(new Error('Network failure'))

      const { result } = renderHook(() => useGenerateStore())

      act(() => {
        result.current.setTask('テスト')
      })

      await act(async () => {
        await result.current.generateSSE()
        await new Promise((r) => setTimeout(r, 50))
      })

      expect(result.current.error).toBe('コード生成に失敗しました。もう一度お試しください。')
      expect(result.current.loading).toBe(false)
      expect(result.current.isStreaming).toBe(false)
    })

    it('accumulates multiple agent log entries in order', async () => {
      const entry1: AgentLogEntry = {
        phase: 'A',
        action: 'start',
        content: '探索開始',
        timestamp: '2024-01-01T00:00:00Z',
      }
      const entry2: AgentLogEntry = {
        phase: 'B',
        action: 'start',
        content: 'ツール合成開始',
        timestamp: '2024-01-01T00:00:01Z',
      }
      const stream = buildSSEStream([
        `data: ${JSON.stringify(entry1)}\n\n`,
        `data: ${JSON.stringify(entry2)}\n\n`,
      ])
      mockFetch.mockResolvedValue({ ok: true, status: 200, body: stream })

      const { result } = renderHook(() => useGenerateStore())

      act(() => {
        result.current.setTask('テスト')
      })

      await act(async () => {
        await result.current.generateSSE()
        await new Promise((r) => setTimeout(r, 50))
      })

      expect(result.current.agentLog).toHaveLength(2)
      expect(result.current.agentLog[0].phase).toBe('A')
      expect(result.current.agentLog[1].phase).toBe('B')
    })

    it('sets loading false and isStreaming false after stream ends', async () => {
      const completeEvent: AgentLogEntry = {
        phase: 'complete',
        action: 'done',
        content: JSON.stringify(mockResponse),
        timestamp: '2024-01-01T00:00:00Z',
      }
      const stream = buildSSEStream([`data: ${JSON.stringify(completeEvent)}\n\n`])
      mockFetch.mockResolvedValue({ ok: true, status: 200, body: stream })

      const { result } = renderHook(() => useGenerateStore())

      act(() => {
        result.current.setTask('テスト')
      })

      await act(async () => {
        await result.current.generateSSE()
        await new Promise((r) => setTimeout(r, 50))
      })

      expect(result.current.loading).toBe(false)
      expect(result.current.isStreaming).toBe(false)
    })
  })
})
