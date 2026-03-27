import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Sidebar } from '../layout/Sidebar'
import type { HistoryItem } from '../../types'

const mockFetchHistory = vi.fn()
const mockSelectItem = vi.fn()
const mockDeleteItem = vi.fn()
const mockSetSearchQuery = vi.fn()

const mockStoreState = {
  items: [] as HistoryItem[],
  total: 0,
  selectedId: null as string | null,
  searchQuery: '',
  loading: false,
  error: null as string | null,
  fetchHistory: mockFetchHistory,
  selectItem: mockSelectItem,
  deleteItem: mockDeleteItem,
  setSearchQuery: mockSetSearchQuery,
  reset: vi.fn(),
}

vi.mock('../../stores/useHistoryStore', () => ({
  useHistoryStore: () => mockStoreState,
}))

const mockItem1: HistoryItem = {
  id: 'hist-001',
  created_at: '2026-03-27T10:00:00Z',
  task: 'Excelを集計して',
  file_name: 'data.xlsx',
  summary: 'Excelファイルを読み込んで集計します',
  python_code: 'import pandas as pd',
  steps: ['ステップ1'],
  tips: 'ヒント',
  memo: null,
  exec_stdout: null,
  exec_stderr: null,
}

const mockItem2: HistoryItem = {
  id: 'hist-002',
  created_at: '2026-03-26T09:00:00Z',
  task: 'CSVを変換して',
  file_name: null,
  summary: 'CSV変換処理',
  python_code: 'import csv',
  steps: null,
  tips: null,
  memo: null,
  exec_stdout: null,
  exec_stderr: null,
}

describe('Sidebar', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockStoreState.items = []
    mockStoreState.total = 0
    mockStoreState.selectedId = null
    mockStoreState.searchQuery = ''
    mockStoreState.loading = false
    mockStoreState.error = null
  })

  it('renders the sidebar with search input', () => {
    render(<Sidebar />)

    expect(screen.getByPlaceholderText(/履歴を検索/)).toBeInTheDocument()
  })

  it('renders a heading for the history section', () => {
    render(<Sidebar />)

    expect(screen.getByText('履歴')).toBeInTheDocument()
  })

  it('calls fetchHistory on mount', () => {
    render(<Sidebar />)

    expect(mockFetchHistory).toHaveBeenCalledTimes(1)
  })

  it('shows empty state message when no history items', () => {
    render(<Sidebar />)

    expect(screen.getByText(/履歴がありません/)).toBeInTheDocument()
  })

  it('renders history items when present', () => {
    mockStoreState.items = [mockItem1, mockItem2]
    render(<Sidebar />)

    expect(screen.getByText('Excelを集計して')).toBeInTheDocument()
    expect(screen.getByText('CSVを変換して')).toBeInTheDocument()
  })

  it('calls selectItem when a history item is clicked', async () => {
    const user = userEvent.setup()
    mockStoreState.items = [mockItem1]
    render(<Sidebar />)

    await user.click(screen.getByText('Excelを集計して'))

    expect(mockSelectItem).toHaveBeenCalledWith('hist-001')
  })

  it('highlights the selected history item', () => {
    mockStoreState.items = [mockItem1, mockItem2]
    mockStoreState.selectedId = 'hist-001'
    render(<Sidebar />)

    const selectedItem = screen.getByText('Excelを集計して').closest('[data-testid="history-item"]')
    expect(selectedItem).toHaveClass('border-blue-500')
  })

  it('does not highlight unselected items', () => {
    mockStoreState.items = [mockItem1, mockItem2]
    mockStoreState.selectedId = 'hist-001'
    render(<Sidebar />)

    const unselectedItem = screen
      .getByText('CSVを変換して')
      .closest('[data-testid="history-item"]')
    expect(unselectedItem).not.toHaveClass('border-blue-500')
  })

  it('renders a delete button for each history item', () => {
    mockStoreState.items = [mockItem1, mockItem2]
    render(<Sidebar />)

    const deleteButtons = screen.getAllByRole('button', { name: /削除/ })
    expect(deleteButtons).toHaveLength(2)
  })

  it('calls deleteItem when delete button is clicked', async () => {
    const user = userEvent.setup()
    mockStoreState.items = [mockItem1]
    render(<Sidebar />)

    await user.click(screen.getByRole('button', { name: /削除/ }))

    expect(mockDeleteItem).toHaveBeenCalledWith('hist-001')
  })

  it('calls setSearchQuery and fetchHistory when search input changes', async () => {
    const user = userEvent.setup()
    mockFetchHistory.mockResolvedValue(undefined)
    render(<Sidebar />)

    const searchInput = screen.getByPlaceholderText(/履歴を検索/)
    await user.type(searchInput, 'Excel')

    expect(mockSetSearchQuery).toHaveBeenCalled()
  })

  it('shows loading state when loading is true', () => {
    mockStoreState.loading = true
    render(<Sidebar />)

    expect(screen.getByText(/読み込み中/)).toBeInTheDocument()
  })

  it('shows error message when error is set', () => {
    mockStoreState.error = '履歴の取得に失敗しました。'
    render(<Sidebar />)

    expect(screen.getByText('履歴の取得に失敗しました。')).toBeInTheDocument()
  })

  it('displays the date of each history item', () => {
    mockStoreState.items = [mockItem1]
    render(<Sidebar />)

    expect(screen.getByText(/2026/)).toBeInTheDocument()
  })

  it('does not render empty state when items are present', () => {
    mockStoreState.items = [mockItem1]
    render(<Sidebar />)

    expect(screen.queryByText(/履歴がありません/)).not.toBeInTheDocument()
  })
})
