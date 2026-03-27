import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useGenerateStore } from '../useGenerateStore'
import * as generateApi from '../../api/generate'
import type { GenerateResponse } from '../../types'

vi.mock('../../api/generate')

const mockResponse: GenerateResponse = {
  id: 'abc-123',
  summary: 'Excelの集計処理',
  python_code: 'import pandas as pd',
  steps: ['ステップ1', 'ステップ2'],
  tips: 'ヒント',
}

describe('useGenerateStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useGenerateStore.getState().reset()
    })
  })

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
})
