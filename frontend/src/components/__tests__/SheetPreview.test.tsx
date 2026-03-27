import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SheetPreview } from '../SheetPreview'
import type { SheetInfo } from '../../types'

const mockSetActiveSheet = vi.fn()

const mockState = {
  uploadResponse: null as { file_id: string; filename: string; sheets: SheetInfo[] } | null,
  activeSheet: 0,
  setActiveSheet: mockSetActiveSheet,
  file: null,
  loading: false,
  error: null,
  upload: vi.fn(),
  reset: vi.fn(),
}

vi.mock('../../stores/useFileStore', () => ({
  useFileStore: () => mockState,
}))

const sheetA: SheetInfo = {
  name: 'Sales',
  total_rows: 150,
  headers: ['date', 'amount', 'region'],
  types: { date: 'datetime', amount: 'float', region: 'string' },
  preview: [
    { date: '2024-01-01', amount: 1000, region: 'East' },
    { date: '2024-01-02', amount: 2500, region: 'West' },
  ],
}

const sheetB: SheetInfo = {
  name: 'Inventory',
  total_rows: 80,
  headers: ['item', 'qty'],
  types: { item: 'string', qty: 'integer' },
  preview: [{ item: 'Widget', qty: 50 }],
}

describe('SheetPreview', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockState.uploadResponse = null
    mockState.activeSheet = 0
  })

  describe('no upload', () => {
    it('renders nothing when uploadResponse is null', () => {
      const { container } = render(<SheetPreview />)
      expect(container.firstChild).toBeNull()
    })
  })

  describe('single sheet', () => {
    beforeEach(() => {
      mockState.uploadResponse = {
        file_id: 'f1',
        filename: 'sales.xlsx',
        sheets: [sheetA],
      }
    })

    it('renders the sheet name in the tab', () => {
      render(<SheetPreview />)
      expect(screen.getByRole('tab', { name: 'Sales' })).toBeInTheDocument()
    })

    it('shows total_rows count', () => {
      render(<SheetPreview />)
      expect(screen.getByText(/150/)).toBeInTheDocument()
    })

    it('renders all column headers', () => {
      render(<SheetPreview />)
      expect(screen.getByRole('columnheader', { name: /date/i })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: /amount/i })).toBeInTheDocument()
      expect(screen.getByRole('columnheader', { name: /region/i })).toBeInTheDocument()
    })

    it('renders preview row data', () => {
      render(<SheetPreview />)
      expect(screen.getByText('2024-01-01')).toBeInTheDocument()
      expect(screen.getByText('1000')).toBeInTheDocument()
      expect(screen.getByText('East')).toBeInTheDocument()
    })

    it('renders all preview rows', () => {
      render(<SheetPreview />)
      expect(screen.getByText('2024-01-02')).toBeInTheDocument()
      expect(screen.getByText('West')).toBeInTheDocument()
    })

    it('shows column type badges', () => {
      render(<SheetPreview />)
      expect(screen.getByText('datetime')).toBeInTheDocument()
      expect(screen.getByText('float')).toBeInTheDocument()
      expect(screen.getByText('string')).toBeInTheDocument()
    })
  })

  describe('multiple sheets', () => {
    beforeEach(() => {
      mockState.uploadResponse = {
        file_id: 'f2',
        filename: 'workbook.xlsx',
        sheets: [sheetA, sheetB],
      }
    })

    it('renders a tab for each sheet', () => {
      render(<SheetPreview />)
      expect(screen.getByRole('tab', { name: 'Sales' })).toBeInTheDocument()
      expect(screen.getByRole('tab', { name: 'Inventory' })).toBeInTheDocument()
    })

    it('shows the active sheet content by default (index 0)', () => {
      render(<SheetPreview />)
      expect(screen.getByRole('columnheader', { name: /date/i })).toBeInTheDocument()
      expect(screen.queryByRole('columnheader', { name: /item/i })).not.toBeInTheDocument()
    })

    it('calls setActiveSheet when a tab is clicked', async () => {
      const user = userEvent.setup()
      render(<SheetPreview />)

      await user.click(screen.getByRole('tab', { name: 'Inventory' }))

      expect(mockSetActiveSheet).toHaveBeenCalledWith(1)
    })

    it('shows second sheet content when activeSheet is 1', () => {
      mockState.activeSheet = 1
      render(<SheetPreview />)

      expect(screen.getByRole('columnheader', { name: /item/i })).toBeInTheDocument()
      expect(screen.queryByRole('columnheader', { name: /date/i })).not.toBeInTheDocument()
    })

    it('marks the active tab as selected', () => {
      render(<SheetPreview />)
      const activeTab = screen.getByRole('tab', { name: 'Sales' })
      expect(activeTab).toHaveAttribute('aria-selected', 'true')
    })

    it('marks inactive tabs as not selected', () => {
      render(<SheetPreview />)
      const inactiveTab = screen.getByRole('tab', { name: 'Inventory' })
      expect(inactiveTab).toHaveAttribute('aria-selected', 'false')
    })
  })

  describe('preview data', () => {
    it('renders null values as empty cells', () => {
      mockState.uploadResponse = {
        file_id: 'f3',
        filename: 'nulls.xlsx',
        sheets: [
          {
            name: 'Sheet1',
            total_rows: 1,
            headers: ['col'],
            types: { col: 'string' },
            preview: [{ col: null }],
          },
        ],
      }

      render(<SheetPreview />)
      const cells = screen.getAllByRole('cell')
      const emptyCell = cells.find((c) => c.textContent === '')
      expect(emptyCell).toBeDefined()
    })

    it('renders up to 30 rows from preview', () => {
      const rows = Array.from({ length: 35 }, (_, i) => ({ id: i }))
      mockState.uploadResponse = {
        file_id: 'f4',
        filename: 'many.xlsx',
        sheets: [
          {
            name: 'Big',
            total_rows: 5000,
            headers: ['id'],
            types: { id: 'integer' },
            preview: rows,
          },
        ],
      }

      render(<SheetPreview />)
      const dataRows = screen.getAllByRole('row').slice(1)
      expect(dataRows.length).toBeLessThanOrEqual(30)
    })
  })
})
