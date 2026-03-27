import { describe, it, expect, vi, beforeEach } from 'vitest'
import { uploadFile } from '../upload'
import client from '../client'
import type { UploadResponse } from '../../types'

vi.mock('../client', () => ({
  default: {
    post: vi.fn(),
  },
}))

const mockUploadResponse: UploadResponse = {
  file_id: 'file-abc-123',
  filename: 'sales.xlsx',
  sheets: [
    {
      name: 'Sheet1',
      total_rows: 100,
      headers: ['date', 'amount', 'category'],
      types: { date: 'datetime', amount: 'float', category: 'string' },
      preview: [
        { date: '2024-01-01', amount: 1000, category: 'A' },
        { date: '2024-01-02', amount: 2000, category: 'B' },
      ],
    },
  ],
}

describe('uploadFile', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls POST /upload with multipart/form-data', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockUploadResponse })

    const file = new File(['content'], 'sales.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    await uploadFile(file)

    expect(client.post).toHaveBeenCalledWith(
      '/upload',
      expect.any(FormData),
      expect.objectContaining({
        headers: { 'Content-Type': 'multipart/form-data' },
      })
    )
  })

  it('appends the file to FormData with key "file"', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockUploadResponse })

    const file = new File(['content'], 'sales.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    await uploadFile(file)

    const formData = vi.mocked(client.post).mock.calls[0][1] as FormData
    expect(formData.get('file')).toBe(file)
  })

  it('returns UploadResponse from the API', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockUploadResponse })

    const file = new File(['content'], 'sales.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const result = await uploadFile(file)

    expect(result).toEqual(mockUploadResponse)
  })

  it('propagates network errors', async () => {
    vi.mocked(client.post).mockRejectedValueOnce(new Error('Network Error'))

    const file = new File(['content'], 'sales.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })

    await expect(uploadFile(file)).rejects.toThrow('Network Error')
  })

  it('propagates 400 validation errors from server', async () => {
    const error = Object.assign(new Error('Request failed with status code 400'), {
      response: { status: 400, data: { detail: 'File too large' } },
    })
    vi.mocked(client.post).mockRejectedValueOnce(error)

    const file = new File(['content'], 'big.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })

    await expect(uploadFile(file)).rejects.toThrow()
  })

  it('returns response with multiple sheets', async () => {
    const multiSheetResponse: UploadResponse = {
      file_id: 'multi-sheet-id',
      filename: 'workbook.xlsx',
      sheets: [
        {
          name: 'January',
          total_rows: 50,
          headers: ['a'],
          types: { a: 'string' },
          preview: [],
        },
        {
          name: 'February',
          total_rows: 60,
          headers: ['b'],
          types: { b: 'number' },
          preview: [],
        },
      ],
    }
    vi.mocked(client.post).mockResolvedValueOnce({ data: multiSheetResponse })

    const file = new File(['content'], 'workbook.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
    const result = await uploadFile(file)

    expect(result.sheets).toHaveLength(2)
    expect(result.sheets[0].name).toBe('January')
    expect(result.sheets[1].name).toBe('February')
  })
})
