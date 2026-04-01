import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useRunPolling } from '../useRunPolling'

vi.mock('../../api/eval', () => ({
  getRunStatus: vi.fn(),
}))

import { getRunStatus } from '../../api/eval'

describe('useRunPolling', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
  })

  it('exposes startPolling and stopPolling functions', () => {
    const { result } = renderHook(() => useRunPolling(vi.fn()))
    expect(typeof result.current.startPolling).toBe('function')
    expect(typeof result.current.stopPolling).toBe('function')
  })

  it('calls getRunStatus on each poll interval', async () => {
    vi.mocked(getRunStatus).mockResolvedValue({
      run_id: 'run-001',
      status: 'running',
      progress: 1,
      total: 5,
      report: null,
    })

    const onPoll = vi.fn()
    const { result } = renderHook(() => useRunPolling(onPoll))

    act(() => {
      result.current.startPolling('run-001')
    })

    await act(async () => {
      vi.advanceTimersByTime(2000)
      await Promise.resolve()
    })

    expect(getRunStatus).toHaveBeenCalledWith('run-001')
    expect(onPoll).toHaveBeenCalled()
  })

  it('stopPolling clears the interval', async () => {
    vi.mocked(getRunStatus).mockResolvedValue({
      run_id: 'run-001',
      status: 'running',
      progress: 1,
      total: 5,
      report: null,
    })

    const onPoll = vi.fn()
    const { result } = renderHook(() => useRunPolling(onPoll))

    act(() => {
      result.current.startPolling('run-001')
    })

    act(() => {
      result.current.stopPolling()
    })

    await act(async () => {
      vi.advanceTimersByTime(6000)
      await Promise.resolve()
    })

    expect(onPoll).not.toHaveBeenCalled()
  })

  it('stops automatically when status is completed', async () => {
    vi.mocked(getRunStatus).mockResolvedValue({
      run_id: 'run-001',
      status: 'completed',
      progress: 5,
      total: 5,
      report: null,
    })

    const onPoll = vi.fn()
    const { result } = renderHook(() => useRunPolling(onPoll))

    act(() => {
      result.current.startPolling('run-001')
    })

    await act(async () => {
      vi.advanceTimersByTime(2000)
      await Promise.resolve()
    })

    // Should have called once and stopped
    const callCount = vi.mocked(getRunStatus).mock.calls.length

    await act(async () => {
      vi.advanceTimersByTime(4000)
      await Promise.resolve()
    })

    // No additional calls after auto-stop
    expect(vi.mocked(getRunStatus).mock.calls.length).toBe(callCount)
  })

  it('stops automatically when status is failed', async () => {
    vi.mocked(getRunStatus).mockResolvedValue({
      run_id: 'run-001',
      status: 'failed',
      progress: 2,
      total: 5,
      report: null,
    })

    const onPoll = vi.fn()
    const { result } = renderHook(() => useRunPolling(onPoll))

    act(() => {
      result.current.startPolling('run-001')
    })

    await act(async () => {
      vi.advanceTimersByTime(2000)
      await Promise.resolve()
    })

    const callCount = vi.mocked(getRunStatus).mock.calls.length

    await act(async () => {
      vi.advanceTimersByTime(4000)
      await Promise.resolve()
    })

    expect(vi.mocked(getRunStatus).mock.calls.length).toBe(callCount)
  })

  it('cleans up interval on unmount', async () => {
    vi.mocked(getRunStatus).mockResolvedValue({
      run_id: 'run-001',
      status: 'running',
      progress: 1,
      total: 5,
      report: null,
    })

    const onPoll = vi.fn()
    const { result, unmount } = renderHook(() => useRunPolling(onPoll))

    act(() => {
      result.current.startPolling('run-001')
    })

    unmount()

    await act(async () => {
      vi.advanceTimersByTime(6000)
      await Promise.resolve()
    })

    expect(onPoll).not.toHaveBeenCalled()
  })
})
