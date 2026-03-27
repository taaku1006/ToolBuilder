import { describe, it, expect, vi, beforeEach } from 'vitest'
import { getHistory, getHistoryItem, deleteHistory, createHistory } from '../history'
import client from '../client'
import type { HistoryItem, HistoryListResponse } from '../../types'

vi.mock('../client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

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

describe('getHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls GET /history without query when not provided', async () => {
    vi.mocked(client.get).mockResolvedValueOnce({ data: mockListResponse })

    await getHistory()

    expect(client.get).toHaveBeenCalledWith('/history', { params: {} })
  })

  it('calls GET /history with query param when provided', async () => {
    vi.mocked(client.get).mockResolvedValueOnce({ data: mockListResponse })

    await getHistory('Excel')

    expect(client.get).toHaveBeenCalledWith('/history', { params: { q: 'Excel' } })
  })

  it('returns HistoryListResponse from the API', async () => {
    vi.mocked(client.get).mockResolvedValueOnce({ data: mockListResponse })

    const result = await getHistory()

    expect(result).toEqual(mockListResponse)
  })

  it('returns empty list when no history exists', async () => {
    const emptyResponse: HistoryListResponse = { items: [], total: 0 }
    vi.mocked(client.get).mockResolvedValueOnce({ data: emptyResponse })

    const result = await getHistory()

    expect(result.items).toHaveLength(0)
    expect(result.total).toBe(0)
  })

  it('propagates errors from the API client', async () => {
    vi.mocked(client.get).mockRejectedValueOnce(new Error('Network Error'))

    await expect(getHistory()).rejects.toThrow('Network Error')
  })
})

describe('getHistoryItem', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls GET /history/:id with the correct id', async () => {
    vi.mocked(client.get).mockResolvedValueOnce({ data: mockHistoryItem })

    await getHistoryItem('hist-001')

    expect(client.get).toHaveBeenCalledWith('/history/hist-001')
  })

  it('returns a HistoryItem from the API', async () => {
    vi.mocked(client.get).mockResolvedValueOnce({ data: mockHistoryItem })

    const result = await getHistoryItem('hist-001')

    expect(result).toEqual(mockHistoryItem)
  })

  it('propagates 404 errors', async () => {
    vi.mocked(client.get).mockRejectedValueOnce(new Error('Not Found'))

    await expect(getHistoryItem('nonexistent')).rejects.toThrow('Not Found')
  })
})

describe('deleteHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls DELETE /history/:id with the correct id', async () => {
    vi.mocked(client.delete).mockResolvedValueOnce({ data: null })

    await deleteHistory('hist-001')

    expect(client.delete).toHaveBeenCalledWith('/history/hist-001')
  })

  it('resolves without a value on success', async () => {
    vi.mocked(client.delete).mockResolvedValueOnce({ data: null })

    const result = await deleteHistory('hist-001')

    expect(result).toBeUndefined()
  })

  it('propagates errors from the API client', async () => {
    vi.mocked(client.delete).mockRejectedValueOnce(new Error('Forbidden'))

    await expect(deleteHistory('hist-001')).rejects.toThrow('Forbidden')
  })
})

describe('createHistory', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls POST /history with the provided data', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockHistoryItem })

    const data = {
      task: 'Excelを集計して',
      python_code: 'import pandas as pd',
      file_name: 'data.xlsx',
      summary: '集計処理',
      steps: ['ステップ1'],
      tips: 'ヒント',
    }

    await createHistory(data)

    expect(client.post).toHaveBeenCalledWith('/history', data)
  })

  it('returns the created HistoryItem', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockHistoryItem })

    const result = await createHistory({
      task: 'Excelを集計して',
      python_code: 'import pandas as pd',
    })

    expect(result).toEqual(mockHistoryItem)
  })

  it('propagates errors from the API client', async () => {
    vi.mocked(client.post).mockRejectedValueOnce(new Error('Validation Error'))

    await expect(
      createHistory({ task: 'test', python_code: 'print()' }),
    ).rejects.toThrow('Validation Error')
  })

  it('handles minimal required fields', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockHistoryItem })

    const data = { task: 'simple task', python_code: 'pass' }
    await createHistory(data)

    expect(client.post).toHaveBeenCalledWith('/history', data)
  })
})
