import { describe, it, expect, vi, beforeEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useSkillsStore } from '../useSkillsStore'
import * as skillsApi from '../../api/skills'
import type { SkillItem, SkillSuggestion } from '../../types'

vi.mock('../../api/skills')

const mockSkillItem: SkillItem = {
  id: 'skill-001',
  created_at: '2026-03-27T10:00:00Z',
  title: 'Excel集計スキル',
  tags: ['excel', 'pandas'],
  python_code: 'import pandas as pd\ndf = pd.read_excel("data.xlsx")',
  file_schema: '{"columns": ["A", "B"]}',
  task_summary: 'Excelファイルを読み込んで集計します',
  use_count: 5,
  success_rate: 0.9,
}

const mockSkillItem2: SkillItem = {
  id: 'skill-002',
  created_at: '2026-03-27T11:00:00Z',
  title: 'CSV変換スキル',
  tags: ['csv'],
  python_code: 'import csv',
  file_schema: null,
  task_summary: null,
  use_count: 2,
  success_rate: 1.0,
}

const mockSuggestion: SkillSuggestion = {
  id: 'skill-003',
  title: '類似スキル',
  tags: ['excel'],
  similarity: 0.85,
}

describe('useSkillsStore', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    act(() => {
      useSkillsStore.getState().reset()
    })
  })

  // --- Initial state ---

  it('has correct initial state', () => {
    const { result } = renderHook(() => useSkillsStore())

    expect(result.current.skills).toEqual([])
    expect(result.current.suggestions).toEqual([])
    expect(result.current.selectedSkillId).toBeNull()
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  // --- fetchSkills ---

  it('fetchSkills sets loading true while fetching', async () => {
    vi.mocked(skillsApi.getSkills).mockReturnValue(new Promise(() => {}))

    const { result } = renderHook(() => useSkillsStore())

    act(() => {
      void result.current.fetchSkills()
    })

    expect(result.current.loading).toBe(true)
  })

  it('fetchSkills sets skills and clears loading on success', async () => {
    vi.mocked(skillsApi.getSkills).mockResolvedValueOnce({
      items: [mockSkillItem, mockSkillItem2],
      total: 2,
    })

    const { result } = renderHook(() => useSkillsStore())

    await act(async () => {
      await result.current.fetchSkills()
    })

    expect(result.current.skills).toEqual([mockSkillItem, mockSkillItem2])
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  it('fetchSkills sets error on API failure', async () => {
    vi.mocked(skillsApi.getSkills).mockRejectedValueOnce(new Error('API Error'))

    const { result } = renderHook(() => useSkillsStore())

    await act(async () => {
      await result.current.fetchSkills()
    })

    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBe('スキルの取得に失敗しました。')
    expect(result.current.skills).toEqual([])
  })

  it('fetchSkills clears previous error before fetching', async () => {
    vi.mocked(skillsApi.getSkills).mockResolvedValueOnce({ items: [], total: 0 })

    const { result } = renderHook(() => useSkillsStore())

    // Manually set error state
    act(() => {
      useSkillsStore.setState({ error: '古いエラー' })
    })

    await act(async () => {
      await result.current.fetchSkills()
    })

    expect(result.current.error).toBeNull()
  })

  // --- setSuggestions ---

  it('setSuggestions updates suggestions array', () => {
    const { result } = renderHook(() => useSkillsStore())

    act(() => {
      result.current.setSuggestions([mockSuggestion])
    })

    expect(result.current.suggestions).toEqual([mockSuggestion])
  })

  it('setSuggestions replaces existing suggestions', () => {
    const { result } = renderHook(() => useSkillsStore())

    const other: SkillSuggestion = { id: 'other', title: '別スキル', tags: [], similarity: 0.5 }

    act(() => {
      result.current.setSuggestions([mockSuggestion])
    })
    act(() => {
      result.current.setSuggestions([other])
    })

    expect(result.current.suggestions).toEqual([other])
  })

  it('setSuggestions with empty array clears suggestions', () => {
    const { result } = renderHook(() => useSkillsStore())

    act(() => {
      result.current.setSuggestions([mockSuggestion])
    })
    act(() => {
      result.current.setSuggestions([])
    })

    expect(result.current.suggestions).toEqual([])
  })

  // --- selectSkill ---

  it('selectSkill sets selectedSkillId', () => {
    const { result } = renderHook(() => useSkillsStore())

    act(() => {
      result.current.selectSkill('skill-001')
    })

    expect(result.current.selectedSkillId).toBe('skill-001')
  })

  it('selectSkill with null clears selectedSkillId', () => {
    const { result } = renderHook(() => useSkillsStore())

    act(() => {
      result.current.selectSkill('skill-001')
    })
    act(() => {
      result.current.selectSkill(null)
    })

    expect(result.current.selectedSkillId).toBeNull()
  })

  // --- saveSkill ---

  it('saveSkill calls createSkill and re-fetches skills on success', async () => {
    vi.mocked(skillsApi.createSkill).mockResolvedValueOnce(mockSkillItem)
    vi.mocked(skillsApi.getSkills).mockResolvedValueOnce({
      items: [mockSkillItem],
      total: 1,
    })

    const { result } = renderHook(() => useSkillsStore())

    await act(async () => {
      await result.current.saveSkill({
        title: 'Excel集計スキル',
        tags: ['excel'],
        python_code: 'import pandas as pd',
      })
    })

    expect(skillsApi.createSkill).toHaveBeenCalledWith({
      title: 'Excel集計スキル',
      tags: ['excel'],
      python_code: 'import pandas as pd',
    })
    expect(skillsApi.getSkills).toHaveBeenCalled()
    expect(result.current.skills).toEqual([mockSkillItem])
  })

  it('saveSkill sets error on API failure', async () => {
    vi.mocked(skillsApi.createSkill).mockRejectedValueOnce(new Error('Save Error'))

    const { result } = renderHook(() => useSkillsStore())

    await act(async () => {
      await result.current.saveSkill({
        title: 'test',
        tags: [],
        python_code: 'pass',
      })
    })

    expect(result.current.error).toBe('スキルの保存に失敗しました。')
  })

  // --- removeSkill ---

  it('removeSkill calls deleteSkill and removes item from local state', async () => {
    vi.mocked(skillsApi.deleteSkill).mockResolvedValueOnce(undefined)

    const { result } = renderHook(() => useSkillsStore())

    act(() => {
      useSkillsStore.setState({ skills: [mockSkillItem, mockSkillItem2], total: 2 })
    })

    await act(async () => {
      await result.current.removeSkill('skill-001')
    })

    expect(skillsApi.deleteSkill).toHaveBeenCalledWith('skill-001')
    expect(result.current.skills).toEqual([mockSkillItem2])
  })

  it('removeSkill clears selectedSkillId when the selected skill is removed', async () => {
    vi.mocked(skillsApi.deleteSkill).mockResolvedValueOnce(undefined)

    const { result } = renderHook(() => useSkillsStore())

    act(() => {
      useSkillsStore.setState({
        skills: [mockSkillItem],
        selectedSkillId: 'skill-001',
      })
    })

    await act(async () => {
      await result.current.removeSkill('skill-001')
    })

    expect(result.current.selectedSkillId).toBeNull()
  })

  it('removeSkill keeps selectedSkillId when a different skill is removed', async () => {
    vi.mocked(skillsApi.deleteSkill).mockResolvedValueOnce(undefined)

    const { result } = renderHook(() => useSkillsStore())

    act(() => {
      useSkillsStore.setState({
        skills: [mockSkillItem, mockSkillItem2],
        selectedSkillId: 'skill-001',
      })
    })

    await act(async () => {
      await result.current.removeSkill('skill-002')
    })

    expect(result.current.selectedSkillId).toBe('skill-001')
  })

  it('removeSkill sets error on API failure', async () => {
    vi.mocked(skillsApi.deleteSkill).mockRejectedValueOnce(new Error('Delete Error'))

    const { result } = renderHook(() => useSkillsStore())

    await act(async () => {
      await result.current.removeSkill('skill-001')
    })

    expect(result.current.error).toBe('スキルの削除に失敗しました。')
  })

  // --- reset ---

  it('reset clears all state', async () => {
    vi.mocked(skillsApi.getSkills).mockResolvedValueOnce({
      items: [mockSkillItem],
      total: 1,
    })

    const { result } = renderHook(() => useSkillsStore())

    await act(async () => {
      await result.current.fetchSkills()
    })

    act(() => {
      result.current.setSuggestions([mockSuggestion])
      result.current.selectSkill('skill-001')
    })

    act(() => {
      result.current.reset()
    })

    expect(result.current.skills).toEqual([])
    expect(result.current.suggestions).toEqual([])
    expect(result.current.selectedSkillId).toBeNull()
    expect(result.current.loading).toBe(false)
    expect(result.current.error).toBeNull()
  })

  // --- Immutability ---

  it('setSuggestions does not mutate the previous suggestions array', () => {
    const { result } = renderHook(() => useSkillsStore())

    let snapshotBefore: SkillSuggestion[] = []

    act(() => {
      snapshotBefore = result.current.suggestions
      result.current.setSuggestions([mockSuggestion])
    })

    expect(snapshotBefore).toHaveLength(0)
    expect(result.current.suggestions).toHaveLength(1)
  })
})
