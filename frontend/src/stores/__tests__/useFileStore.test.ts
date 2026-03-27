import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useFileStore } from '../useFileStore'
import * as uploadApi from '../../api/upload'
import type { UploadResponse } from '../../types'

vi.mock('../../api/upload')

const mockUploadResponse: UploadResponse = {
  file_id: 'file-xyz-999',
  filename: 'data.xlsx',
  sheets: [
    {
      name: 'Sheet1',
      total_rows: 200,
      headers: ['col1', 'col2'],
      types: { col1: 'string', col2: 'integer' },
      preview: [{ col1: 'foo', col2: 1 }],
    },
  ],
}

function makeFile(name = 'test.xlsx', size = 1024): File {
  return new File(['x'.repeat(size)], name, {
    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  })
}

describe('useFileStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useFileStore.getState().reset()
    })
  })

  describe('initial state', () => {
    it('has null file', () => {
      const { result } = renderHook(() => useFileStore())
      expect(result.current.file).toBeNull()
    })

    it('has null uploadResponse', () => {
      const { result } = renderHook(() => useFileStore())
      expect(result.current.uploadResponse).toBeNull()
    })

    it('has activeSheet index 0', () => {
      const { result } = renderHook(() => useFileStore())
      expect(result.current.activeSheet).toBe(0)
    })

    it('has loading false', () => {
      const { result } = renderHook(() => useFileStore())
      expect(result.current.loading).toBe(false)
    })

    it('has null error', () => {
      const { result } = renderHook(() => useFileStore())
      expect(result.current.error).toBeNull()
    })
  })

  describe('upload', () => {
    it('sets loading true during upload', async () => {
      let resolveUpload!: (value: UploadResponse) => void
      vi.mocked(uploadApi.uploadFile).mockReturnValueOnce(
        new Promise((resolve) => {
          resolveUpload = resolve
        })
      )

      const { result } = renderHook(() => useFileStore())
      const file = makeFile()

      act(() => {
        result.current.upload(file)
      })

      expect(result.current.loading).toBe(true)

      await act(async () => {
        resolveUpload(mockUploadResponse)
      })
    })

    it('sets file and uploadResponse on success', async () => {
      vi.mocked(uploadApi.uploadFile).mockResolvedValueOnce(mockUploadResponse)

      const { result } = renderHook(() => useFileStore())
      const file = makeFile()

      await act(async () => {
        await result.current.upload(file)
      })

      expect(result.current.file).toBe(file)
      expect(result.current.uploadResponse).toEqual(mockUploadResponse)
      expect(result.current.loading).toBe(false)
      expect(result.current.error).toBeNull()
    })

    it('resets activeSheet to 0 on new upload', async () => {
      vi.mocked(uploadApi.uploadFile).mockResolvedValueOnce(mockUploadResponse)

      const { result } = renderHook(() => useFileStore())

      act(() => {
        result.current.setActiveSheet(1)
      })

      await act(async () => {
        await result.current.upload(makeFile())
      })

      expect(result.current.activeSheet).toBe(0)
    })

    it('sets error and clears loading on API failure', async () => {
      vi.mocked(uploadApi.uploadFile).mockRejectedValueOnce(new Error('Upload failed'))

      const { result } = renderHook(() => useFileStore())

      await act(async () => {
        await result.current.upload(makeFile())
      })

      expect(result.current.loading).toBe(false)
      expect(result.current.error).toBeTruthy()
      expect(result.current.uploadResponse).toBeNull()
    })

    it('calls uploadFile with the provided file', async () => {
      vi.mocked(uploadApi.uploadFile).mockResolvedValueOnce(mockUploadResponse)

      const { result } = renderHook(() => useFileStore())
      const file = makeFile('my-data.xlsx')

      await act(async () => {
        await result.current.upload(file)
      })

      expect(uploadApi.uploadFile).toHaveBeenCalledWith(file)
    })

    it('clears previous error before uploading', async () => {
      vi.mocked(uploadApi.uploadFile).mockRejectedValueOnce(new Error('First error'))

      const { result } = renderHook(() => useFileStore())

      await act(async () => {
        await result.current.upload(makeFile())
      })

      expect(result.current.error).toBeTruthy()

      vi.mocked(uploadApi.uploadFile).mockResolvedValueOnce(mockUploadResponse)

      await act(async () => {
        await result.current.upload(makeFile())
      })

      expect(result.current.error).toBeNull()
    })
  })

  describe('setActiveSheet', () => {
    it('updates activeSheet index', () => {
      const { result } = renderHook(() => useFileStore())

      act(() => {
        result.current.setActiveSheet(2)
      })

      expect(result.current.activeSheet).toBe(2)
    })

    it('accepts index 0', () => {
      const { result } = renderHook(() => useFileStore())

      act(() => {
        result.current.setActiveSheet(1)
        result.current.setActiveSheet(0)
      })

      expect(result.current.activeSheet).toBe(0)
    })
  })

  describe('reset', () => {
    it('clears all state back to initial values', async () => {
      vi.mocked(uploadApi.uploadFile).mockResolvedValueOnce(mockUploadResponse)

      const { result } = renderHook(() => useFileStore())

      await act(async () => {
        await result.current.upload(makeFile())
      })

      act(() => {
        result.current.setActiveSheet(1)
        result.current.reset()
      })

      expect(result.current.file).toBeNull()
      expect(result.current.uploadResponse).toBeNull()
      expect(result.current.activeSheet).toBe(0)
      expect(result.current.loading).toBe(false)
      expect(result.current.error).toBeNull()
    })
  })
})
