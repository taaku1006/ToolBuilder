import { describe, it, expect, vi, beforeEach } from 'vitest'
import { postGenerate } from '../generate'
import client from '../client'
import type { GenerateResponse } from '../../types'

vi.mock('../client', () => ({
  default: {
    post: vi.fn(),
  },
}))

const mockResponse: GenerateResponse = {
  id: 'test-id-123',
  summary: 'Excelファイルを読み込んで集計します',
  python_code: 'import pandas as pd\ndf = pd.read_excel("file.xlsx")',
  steps: ['ファイルを読み込む', 'データを集計する'],
  tips: 'pandasが必要です',
}

describe('postGenerate', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls POST /generate with the task string', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockResponse })

    await postGenerate('Excelを集計して')

    expect(client.post).toHaveBeenCalledWith('/generate', { task: 'Excelを集計して' })
  })

  it('includes file_id in the body when provided', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockResponse })

    await postGenerate('Excelを集計して', 'file-abc-123')

    expect(client.post).toHaveBeenCalledWith('/generate', {
      task: 'Excelを集計して',
      file_id: 'file-abc-123',
    })
  })

  it('omits file_id from the body when not provided', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockResponse })

    await postGenerate('Excelを集計して')

    const body = vi.mocked(client.post).mock.calls[0][1] as Record<string, unknown>
    expect(body).not.toHaveProperty('file_id')
  })

  it('returns the GenerateResponse from the API', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockResponse })

    const result = await postGenerate('Excelを集計して')

    expect(result).toEqual(mockResponse)
  })

  it('propagates errors from the API client', async () => {
    const error = new Error('Network Error')
    vi.mocked(client.post).mockRejectedValueOnce(error)

    await expect(postGenerate('Excelを集計して')).rejects.toThrow('Network Error')
  })

  it('handles empty task string', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockResponse })

    await postGenerate('')

    expect(client.post).toHaveBeenCalledWith('/generate', { task: '' })
  })
})
