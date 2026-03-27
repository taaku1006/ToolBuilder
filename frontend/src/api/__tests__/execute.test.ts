import { describe, it, expect, vi, beforeEach } from 'vitest'
import { postExecute } from '../execute'
import client from '../client'
import type { ExecuteResponse } from '../../types'

vi.mock('../client', () => ({
  default: {
    post: vi.fn(),
  },
}))

const mockResponse: ExecuteResponse = {
  stdout: 'Hello, World!\n',
  stderr: '',
  elapsed_ms: 123,
  output_files: [],
  success: true,
}

describe('postExecute', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls POST /execute with code string', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockResponse })

    await postExecute('print("Hello")')

    expect(client.post).toHaveBeenCalledWith('/execute', { code: 'print("Hello")' })
  })

  it('includes file_id in the body when provided', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockResponse })

    await postExecute('print("Hello")', 'file-abc-123')

    expect(client.post).toHaveBeenCalledWith('/execute', {
      code: 'print("Hello")',
      file_id: 'file-abc-123',
    })
  })

  it('omits file_id from body when not provided', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockResponse })

    await postExecute('print("Hello")')

    const body = vi.mocked(client.post).mock.calls[0][1] as Record<string, unknown>
    expect(body).not.toHaveProperty('file_id')
  })

  it('returns the ExecuteResponse from the API', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockResponse })

    const result = await postExecute('print("Hello")')

    expect(result).toEqual(mockResponse)
  })

  it('returns response with stderr and success false on execution error', async () => {
    const errorResponse: ExecuteResponse = {
      stdout: '',
      stderr: 'NameError: name "x" is not defined',
      elapsed_ms: 45,
      output_files: [],
      success: false,
    }
    vi.mocked(client.post).mockResolvedValueOnce({ data: errorResponse })

    const result = await postExecute('print(x)')

    expect(result.success).toBe(false)
    expect(result.stderr).toBe('NameError: name "x" is not defined')
  })

  it('returns response with output_files when present', async () => {
    const responseWithFiles: ExecuteResponse = {
      stdout: 'Done\n',
      stderr: '',
      elapsed_ms: 500,
      output_files: ['output.csv', 'chart.png'],
      success: true,
    }
    vi.mocked(client.post).mockResolvedValueOnce({ data: responseWithFiles })

    const result = await postExecute('some code')

    expect(result.output_files).toEqual(['output.csv', 'chart.png'])
  })

  it('propagates network errors from the API client', async () => {
    const error = new Error('Network Error')
    vi.mocked(client.post).mockRejectedValueOnce(error)

    await expect(postExecute('print("Hello")')).rejects.toThrow('Network Error')
  })

  it('handles empty code string', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockResponse })

    await postExecute('')

    expect(client.post).toHaveBeenCalledWith('/execute', { code: '' })
  })
})
