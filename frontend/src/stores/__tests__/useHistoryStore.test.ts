import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useHistoryStore } from '../useHistoryStore'
import * as historyApi from '../../api/history'
import type { HistoryItem, HistoryListResponse } from '../../types'

vi.mock('../../api/history')

const mockHistoryItem: HistoryItem = {
  id: 'hist-001',
  created_at: '2026-03-27T10:00:00Z',
  task: 'Excelを集計して',
  file_name: 'data.xlsx',
  summary: 'Excelファイルを読み込んで集計します',
  python_code: 'import pandas as pd\ndf = pd.read_excel("data.xlsx")',
  steps: ['ファイルを読み込む', 'データを集計する'],
  tips: 'pandasが必要です',
  memo: null,
  exec_stdout: 'Done\n',
  exec_stderr: null,
}

const mockListResponse: HistoryListResponse = {
  items: [mockHistoryItem],
  total: 1,
}

describe('useHistoryStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useHistoryStore.getState().reset()
    })
  })

  it('has correct initial state', () => {
    const { result } = renderHook(() => useHistoryStore())

    expect(result.current.items).toEqual([])
    expect(result.current.total).toBe(0)
    expect(result.current.selectedId).toBeNull()
    expect(result.current.searchQuery).toBe('')
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('fetchHistory sets items and total on success', async () => {
    vi.mocked(historyApi.getHistory).mockResolvedValueOnce(mockListResponse)

    const { result } = renderHook(() => useHistoryStore())

    await act(async () => {
      await result.current.fetchHistory()
    })

    expect(result.current.items).toEqual([mockHistoryItem])
    expect(result.current.total).toBe(1)
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('fetchHistory calls getHistory with query when provided', async () => {
    vi.mocked(historyApi.getHistory).mockResolvedValueOnce(mockListResponse)

    const { result } = renderHook(() => useHistoryStore())

    await act(async () => {
      await result.current.fetchHistory('Excel')
    })

    expect(historyApi.getHistory).toHaveBeenCalledWith('Excel')
  })

  it('fetchHistory calls getHistory without query by default', async () => {
    vi.mocked(historyApi.getHistory).mockResolvedValueOnce(mockListResponse)

    const { result } = renderHook(() => useHistoryStore())

    await act(async () => {
      await result.current.fetchHistory()
    })

    expect(historyApi.getHistory).toHaveBeenCalledWith(undefined)
  })

  it('fetchHistory sets error on API failure', async () => {
    vi.mocked(historyApi.getHistory).mockRejectedValueOnce(new Error('Network Error'))

    const { result } = renderHook(() => useHistoryStore())

    await act(async () => {
      await result.current.fetchHistory()
    })

    expect(result.current.loading).toBe(false)
    expect(result.current.items).toEqual([])
    expect(result.current.error).toBe('履歴の取得に失敗しました。')
  })

  it('fetchHistory sets loading true during fetch', async () => {
    let resolvePromise!: (value: HistoryListResponse) => void
    const promise = new Promise<HistoryListResponse>((resolve) => {
      resolvePromise = resolve
    })
    vi.mocked(historyApi.getHistory).mockReturnValueOnce(promise)

    const { result } = renderHook(() => useHistoryStore())

    act(() => {
      void result.current.fetchHistory()
    })

    expect(result.current.loading).toBe(true)

    await act(async () => {
      resolvePromise(mockListResponse)
    })

    expect(result.current.loading).toBe(false)
  })

  it('selectItem sets selectedId', () => {
    const { result } = renderHook(() => useHistoryStore())

    act(() => {
      result.current.selectItem('hist-001')
    })

    expect(result.current.selectedId).toBe('hist-001')
  })

  it('selectItem replaces previously selected id', () => {
    const { result } = renderHook(() => useHistoryStore())

    act(() => {
      result.current.selectItem('hist-001')
    })
    act(() => {
      result.current.selectItem('hist-002')
    })

    expect(result.current.selectedId).toBe('hist-002')
  })

  it('deleteItem calls deleteHistory and removes item from list', async () => {
    vi.mocked(historyApi.getHistory).mockResolvedValueOnce(mockListResponse)
    vi.mocked(historyApi.deleteHistory).mockResolvedValueOnce(undefined)

    const { result } = renderHook(() => useHistoryStore())

    await act(async () => {
      await result.current.fetchHistory()
    })

    await act(async () => {
      await result.current.deleteItem('hist-001')
    })

    expect(historyApi.deleteHistory).toHaveBeenCalledWith('hist-001')
    expect(result.current.items).toEqual([])
    expect(result.current.total).toBe(0)
  })

  it('deleteItem clears selectedId when deleting the selected item', async () => {
    vi.mocked(historyApi.getHistory).mockResolvedValueOnce(mockListResponse)
    vi.mocked(historyApi.deleteHistory).mockResolvedValueOnce(undefined)

    const { result } = renderHook(() => useHistoryStore())

    await act(async () => {
      await result.current.fetchHistory()
    })

    act(() => {
      result.current.selectItem('hist-001')
    })

    await act(async () => {
      await result.current.deleteItem('hist-001')
    })

    expect(result.current.selectedId).toBeNull()
  })

  it('deleteItem sets error on API failure', async () => {
    vi.mocked(historyApi.deleteHistory).mockRejectedValueOnce(new Error('Forbidden'))

    const { result } = renderHook(() => useHistoryStore())

    await act(async () => {
      await result.current.deleteItem('hist-001')
    })

    expect(result.current.error).toBe('履歴の削除に失敗しました。')
  })

  it('setSearchQuery updates searchQuery', () => {
    const { result } = renderHook(() => useHistoryStore())

    act(() => {
      result.current.setSearchQuery('Excel')
    })

    expect(result.current.searchQuery).toBe('Excel')
  })

  it('reset clears all state', async () => {
    vi.mocked(historyApi.getHistory).mockResolvedValueOnce(mockListResponse)

    const { result } = renderHook(() => useHistoryStore())

    await act(async () => {
      await result.current.fetchHistory()
    })

    act(() => {
      result.current.selectItem('hist-001')
      result.current.setSearchQuery('Excel')
    })

    act(() => {
      result.current.reset()
    })

    expect(result.current.items).toEqual([])
    expect(result.current.total).toBe(0)
    expect(result.current.selectedId).toBeNull()
    expect(result.current.searchQuery).toBe('')
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
  })
})
