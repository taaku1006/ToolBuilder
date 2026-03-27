import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SkillsPanel } from '../SkillsPanel'
import { useSkillsStore } from '../../stores/useSkillsStore'
import type { SkillItem, SkillSuggestion } from '../../types'

const mockFetchSkills = vi.fn()
const mockSelectSkill = vi.fn()
const mockRemoveSkill = vi.fn()
const mockSetSuggestions = vi.fn()
const mockSaveSkill = vi.fn()
const mockReset = vi.fn()

let storeState: ReturnType<typeof useSkillsStore> = {
  skills: [],
  suggestions: [],
  selectedSkillId: null,
  loading: false,
  error: null,
  fetchSkills: mockFetchSkills,
  setSuggestions: mockSetSuggestions,
  selectSkill: mockSelectSkill,
  saveSkill: mockSaveSkill,
  removeSkill: mockRemoveSkill,
  reset: mockReset,
}

vi.mock('../../stores/useSkillsStore', () => ({
  useSkillsStore: () => storeState,
}))

const mockSkillItem: SkillItem = {
  id: 'skill-001',
  created_at: '2026-03-27T10:00:00Z',
  title: 'Excel集計スキル',
  tags: ['excel', 'pandas'],
  python_code: 'import pandas as pd',
  file_schema: null,
  task_summary: '集計処理',
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
  title: '類似Excelスキル',
  tags: ['excel'],
  similarity: 0.85,
}

function setupStore(overrides: Partial<ReturnType<typeof useSkillsStore>> = {}) {
  storeState = {
    skills: [],
    suggestions: [],
    selectedSkillId: null,
    loading: false,
    error: null,
    fetchSkills: mockFetchSkills,
    setSuggestions: mockSetSuggestions,
    selectSkill: mockSelectSkill,
    saveSkill: mockSaveSkill,
    removeSkill: mockRemoveSkill,
    reset: mockReset,
    ...overrides,
  }
}

describe('SkillsPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    setupStore()
  })

  // --- Lifecycle ---

  it('calls fetchSkills on mount', () => {
    render(<SkillsPanel />)
    expect(mockFetchSkills).toHaveBeenCalledTimes(1)
  })

  // --- Section heading ---

  it('renders the skills section heading', () => {
    render(<SkillsPanel />)
    expect(screen.getByText('スキル')).toBeInTheDocument()
  })

  // --- Empty state ---

  it('renders empty state when no skills or suggestions exist', () => {
    render(<SkillsPanel />)
    expect(screen.getByText('スキルがありません')).toBeInTheDocument()
  })

  it('does not render empty state when skills exist', () => {
    setupStore({ skills: [mockSkillItem] })
    render(<SkillsPanel />)
    expect(screen.queryByText('スキルがありません')).not.toBeInTheDocument()
  })

  // --- Loading state ---

  it('renders loading indicator when loading is true', () => {
    setupStore({ loading: true })
    render(<SkillsPanel />)
    expect(screen.getByText('読み込み中...')).toBeInTheDocument()
  })

  // --- Error state ---

  it('renders error message when error is set', () => {
    setupStore({ error: 'スキルの取得に失敗しました。' })
    render(<SkillsPanel />)
    expect(screen.getByText('スキルの取得に失敗しました。')).toBeInTheDocument()
  })

  // --- Skill list rendering ---

  it('renders skill titles', () => {
    setupStore({ skills: [mockSkillItem, mockSkillItem2] })
    render(<SkillsPanel />)
    expect(screen.getByText('Excel集計スキル')).toBeInTheDocument()
    expect(screen.getByText('CSV変換スキル')).toBeInTheDocument()
  })

  it('renders tags for each skill', () => {
    setupStore({ skills: [mockSkillItem] })
    render(<SkillsPanel />)
    expect(screen.getByText('excel')).toBeInTheDocument()
    expect(screen.getByText('pandas')).toBeInTheDocument()
  })

  it('renders use_count for each skill', () => {
    setupStore({ skills: [mockSkillItem] })
    render(<SkillsPanel />)
    expect(screen.getByText(/5回/)).toBeInTheDocument()
  })

  it('renders success_rate as percentage for each skill', () => {
    setupStore({ skills: [mockSkillItem] })
    render(<SkillsPanel />)
    expect(screen.getByText(/90%/)).toBeInTheDocument()
  })

  it('renders delete button per skill', () => {
    setupStore({ skills: [mockSkillItem, mockSkillItem2] })
    render(<SkillsPanel />)
    const deleteButtons = screen.getAllByRole('button', { name: '削除' })
    expect(deleteButtons).toHaveLength(2)
  })

  // --- Skill selection ---

  it('calls selectSkill when a skill card is clicked', async () => {
    const user = userEvent.setup()
    setupStore({ skills: [mockSkillItem] })
    render(<SkillsPanel />)

    await user.click(screen.getByText('Excel集計スキル'))

    expect(mockSelectSkill).toHaveBeenCalledWith('skill-001')
  })

  it('highlights the selected skill with a distinct style', () => {
    setupStore({ skills: [mockSkillItem], selectedSkillId: 'skill-001' })
    render(<SkillsPanel />)

    const skillCard = screen.getByTestId('skill-item-skill-001')
    expect(skillCard).toHaveClass('border-blue-500')
  })

  it('does not highlight non-selected skill', () => {
    setupStore({ skills: [mockSkillItem, mockSkillItem2], selectedSkillId: 'skill-001' })
    render(<SkillsPanel />)

    const unselectedCard = screen.getByTestId('skill-item-skill-002')
    expect(unselectedCard).not.toHaveClass('border-blue-500')
  })

  // --- Delete button ---

  it('calls removeSkill when delete button is clicked', async () => {
    const user = userEvent.setup()
    setupStore({ skills: [mockSkillItem] })
    render(<SkillsPanel />)

    const deleteBtn = screen.getByRole('button', { name: '削除' })
    await user.click(deleteBtn)

    expect(mockRemoveSkill).toHaveBeenCalledWith('skill-001')
  })

  it('delete button click does not trigger selectSkill', async () => {
    const user = userEvent.setup()
    setupStore({ skills: [mockSkillItem] })
    render(<SkillsPanel />)

    const deleteBtn = screen.getByRole('button', { name: '削除' })
    await user.click(deleteBtn)

    expect(mockSelectSkill).not.toHaveBeenCalled()
  })

  // --- Suggestions section ---

  it('renders suggestions section when suggestions are provided', () => {
    setupStore({ suggestions: [mockSuggestion] })
    render(<SkillsPanel />)
    expect(screen.getByText('提案スキル')).toBeInTheDocument()
  })

  it('does not render suggestions section when suggestions are empty', () => {
    render(<SkillsPanel />)
    expect(screen.queryByText('提案スキル')).not.toBeInTheDocument()
  })

  it('renders suggestion titles', () => {
    setupStore({ suggestions: [mockSuggestion] })
    render(<SkillsPanel />)
    expect(screen.getByText('類似Excelスキル')).toBeInTheDocument()
  })

  it('renders suggestion similarity score as percentage badge', () => {
    setupStore({ suggestions: [mockSuggestion] })
    render(<SkillsPanel />)
    expect(screen.getByText('85%')).toBeInTheDocument()
  })

  it('renders suggestion tags', () => {
    setupStore({ suggestions: [mockSuggestion] })
    render(<SkillsPanel />)
    const suggestionsSection = screen.getByTestId('suggestions-section')
    expect(within(suggestionsSection).getByText('excel')).toBeInTheDocument()
  })

  it('renders multiple suggestions', () => {
    const suggestion2: SkillSuggestion = {
      id: 'skill-004',
      title: '別の類似スキル',
      tags: ['csv'],
      similarity: 0.7,
    }
    setupStore({ suggestions: [mockSuggestion, suggestion2] })
    render(<SkillsPanel />)
    expect(screen.getByText('類似Excelスキル')).toBeInTheDocument()
    expect(screen.getByText('別の類似スキル')).toBeInTheDocument()
  })

  // --- Skills and suggestions together ---

  it('renders both skills and suggestions sections simultaneously', () => {
    setupStore({ skills: [mockSkillItem], suggestions: [mockSuggestion] })
    render(<SkillsPanel />)
    expect(screen.getByText('Excel集計スキル')).toBeInTheDocument()
    expect(screen.getByText('提案スキル')).toBeInTheDocument()
    expect(screen.getByText('類似Excelスキル')).toBeInTheDocument()
  })

  it('does not render empty state when only suggestions exist', () => {
    setupStore({ skills: [], suggestions: [mockSuggestion] })
    render(<SkillsPanel />)
    expect(screen.queryByText('スキルがありません')).not.toBeInTheDocument()
  })

  // --- Skill item test ids ---

  it('renders skill items with data-testid', () => {
    setupStore({ skills: [mockSkillItem] })
    render(<SkillsPanel />)
    expect(screen.getByTestId('skill-item-skill-001')).toBeInTheDocument()
  })

  // --- success_rate edge cases ---

  it('renders 100% success rate correctly', () => {
    setupStore({ skills: [mockSkillItem2] })
    render(<SkillsPanel />)
    expect(screen.getByText(/100%/)).toBeInTheDocument()
  })

  it('renders 0 use count correctly', () => {
    const zeroUseSkill: SkillItem = { ...mockSkillItem, use_count: 0 }
    setupStore({ skills: [zeroUseSkill] })
    render(<SkillsPanel />)
    expect(screen.getByText(/0回/)).toBeInTheDocument()
  })
})
