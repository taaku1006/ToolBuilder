import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act, waitFor } from '@testing-library/react'
import { useEvalData } from '../useEvalData'

vi.mock('../../api/eval', () => ({
  getArchitectures: vi.fn(),
  getTestCases: vi.fn(),
  listRuns: vi.fn(),
}))

import { getArchitectures, getTestCases, listRuns } from '../../api/eval'

const mockArchitectures = [
  {
    id: 'v2_adaptive',
    phases: ['U', 'G', 'VF', 'L'],
    model: 'gpt-4o',
    debug_retry_limit: 3,
    temperature: 0.0,
    description: 'Adaptive Pipeline v2',
    pipeline: null,
  },
]

const mockTestCases = [
  {
    id: 'tc-001',
    task: 'Generate report',
    description: 'Test case 1',
    file_path: null,
    expected_file_path: null,
    expected_success: true,
  },
]

const mockRuns = [
  { run_id: 'run-001', status: 'completed', best_architecture: 'v1' },
]

describe('useEvalData', () => {
  beforeEach(() => {
    vi.mocked(getArchitectures).mockResolvedValue(mockArchitectures)
    vi.mocked(getTestCases).mockResolvedValue(mockTestCases)
    vi.mocked(listRuns).mockResolvedValue(mockRuns)
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('starts with empty data and loading state', () => {
    const { result } = renderHook(() => useEvalData())
    expect(result.current.archs).toEqual([])
    expect(result.current.cases).toEqual([])
    expect(result.current.pastRuns).toEqual([])
    expect(result.current.loading).toBe(true)
    expect(result.current.error).toBeNull()
  })

  it('loads archs, cases, and pastRuns on mount', async () => {
    const { result } = renderHook(() => useEvalData())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.archs).toEqual(mockArchitectures)
    expect(result.current.cases).toEqual(mockTestCases)
    expect(result.current.pastRuns).toEqual(mockRuns)
  })

  it('sets error state when API call fails', async () => {
    vi.mocked(getArchitectures).mockRejectedValue(new Error('Network error'))

    const { result } = renderHook(() => useEvalData())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    expect(result.current.error).toBe('Network error')
    expect(result.current.archs).toEqual([])
  })

  it('reload function re-fetches data', async () => {
    const { result } = renderHook(() => useEvalData())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    const updatedArchs = [{ ...mockArchitectures[0], id: 'v2' }]
    vi.mocked(getArchitectures).mockResolvedValue(updatedArchs)

    await act(async () => {
      await result.current.reload()
    })

    expect(result.current.archs).toEqual(updatedArchs)
  })

  it('reloadCases re-fetches only test cases', async () => {
    const { result } = renderHook(() => useEvalData())

    await waitFor(() => {
      expect(result.current.loading).toBe(false)
    })

    const updatedCases = [{ ...mockTestCases[0], id: 'tc-002' }]
    vi.mocked(getTestCases).mockResolvedValue(updatedCases)

    await act(async () => {
      await result.current.reloadCases()
    })

    expect(result.current.cases).toEqual(updatedCases)
    // archs should not have been re-fetched again (only once on mount + reloadCases)
    expect(getTestCases).toHaveBeenCalledTimes(2)
  })

  it('exposes reload and reloadCases as functions', async () => {
    const { result } = renderHook(() => useEvalData())
    expect(typeof result.current.reload).toBe('function')
    expect(typeof result.current.reloadCases).toBe('function')
  })
})
