import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { FileUpload } from '../FileUpload'

const mockUpload = vi.fn()
const mockReset = vi.fn()

const mockState = {
  file: null as File | null,
  uploadResponse: null,
  loading: false,
  error: null as string | null,
  upload: mockUpload,
  reset: mockReset,
  setActiveSheet: vi.fn(),
  activeSheet: 0,
}

vi.mock('../../stores/useFileStore', () => ({
  useFileStore: () => mockState,
}))

function makeFile(name = 'data.xlsx', sizeBytes = 1024, type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'): File {
  const file = new File(['x'], name, { type })
  Object.defineProperty(file, 'size', { value: sizeBytes })
  return file
}

describe('FileUpload', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockState.file = null
    mockState.loading = false
    mockState.error = null
    mockState.uploadResponse = null
  })

  describe('rendering', () => {
    it('renders the drop zone', () => {
      render(<FileUpload />)
      expect(screen.getByTestId('drop-zone')).toBeInTheDocument()
    })

    it('renders instruction text', () => {
      render(<FileUpload />)
      expect(screen.getByText(/ドロップ|クリック/i)).toBeInTheDocument()
    })

    it('renders accepted file type hint', () => {
      render(<FileUpload />)
      expect(screen.getByText(/xlsx|xls|csv/i)).toBeInTheDocument()
    })

    it('renders a hidden file input', () => {
      render(<FileUpload />)
      const input = document.querySelector('input[type="file"]')
      expect(input).toBeInTheDocument()
    })
  })

  describe('file input', () => {
    it('accepts .xlsx, .xls, .csv file types', () => {
      render(<FileUpload />)
      const input = document.querySelector('input[type="file"]') as HTMLInputElement
      expect(input.accept).toContain('.xlsx')
      expect(input.accept).toContain('.xls')
      expect(input.accept).toContain('.csv')
    })

    it('calls upload when a valid file is selected', async () => {
      mockUpload.mockResolvedValueOnce(undefined)
      render(<FileUpload />)

      const input = document.querySelector('input[type="file"]') as HTMLInputElement
      const file = makeFile()
      await userEvent.upload(input, file)

      expect(mockUpload).toHaveBeenCalledWith(file)
    })

    it('does not call upload when file exceeds 50MB', async () => {
      render(<FileUpload />)

      const input = document.querySelector('input[type="file"]') as HTMLInputElement
      const bigFile = makeFile('big.xlsx', 51 * 1024 * 1024)
      await userEvent.upload(input, bigFile)

      expect(mockUpload).not.toHaveBeenCalled()
    })

    it('shows size error when file exceeds 50MB', async () => {
      render(<FileUpload />)

      const input = document.querySelector('input[type="file"]') as HTMLInputElement
      const bigFile = makeFile('big.xlsx', 51 * 1024 * 1024)
      await userEvent.upload(input, bigFile)

      expect(screen.getByText(/50MB以下/i)).toBeInTheDocument()
    })
  })

  describe('drag and drop', () => {
    it('adds highlight class when dragging over drop zone', () => {
      render(<FileUpload />)
      const dropZone = screen.getByTestId('drop-zone')

      fireEvent.dragOver(dropZone, { preventDefault: vi.fn() })

      expect(dropZone).toHaveClass('border-blue-500')
    })

    it('removes highlight class when drag leaves drop zone', () => {
      render(<FileUpload />)
      const dropZone = screen.getByTestId('drop-zone')

      fireEvent.dragOver(dropZone, { preventDefault: vi.fn() })
      fireEvent.dragLeave(dropZone)

      expect(dropZone).not.toHaveClass('border-blue-500')
    })

    it('calls upload when a valid file is dropped', async () => {
      mockUpload.mockResolvedValueOnce(undefined)
      render(<FileUpload />)

      const dropZone = screen.getByTestId('drop-zone')
      const file = makeFile()

      fireEvent.drop(dropZone, {
        preventDefault: vi.fn(),
        dataTransfer: { files: [file] },
      })

      await waitFor(() => {
        expect(mockUpload).toHaveBeenCalledWith(file)
      })
    })

    it('shows size error when dropped file exceeds 50MB', async () => {
      render(<FileUpload />)

      const dropZone = screen.getByTestId('drop-zone')
      const bigFile = makeFile('big.xlsx', 51 * 1024 * 1024)

      fireEvent.drop(dropZone, {
        preventDefault: vi.fn(),
        dataTransfer: { files: [bigFile] },
      })

      expect(screen.getByText(/50MB以下/i)).toBeInTheDocument()
    })

    it('does not call upload when dropped file exceeds 50MB', async () => {
      render(<FileUpload />)

      const dropZone = screen.getByTestId('drop-zone')
      const bigFile = makeFile('big.xlsx', 51 * 1024 * 1024)

      fireEvent.drop(dropZone, {
        preventDefault: vi.fn(),
        dataTransfer: { files: [bigFile] },
      })

      expect(mockUpload).not.toHaveBeenCalled()
    })
  })

  describe('loading state', () => {
    it('shows loading spinner when loading is true', () => {
      mockState.loading = true
      render(<FileUpload />)

      expect(screen.getByTestId('upload-spinner')).toBeInTheDocument()
    })

    it('disables drop zone interaction during loading', () => {
      mockState.loading = true
      render(<FileUpload />)

      const dropZone = screen.getByTestId('drop-zone')
      expect(dropZone).toHaveClass('cursor-not-allowed')
    })
  })

  describe('success state', () => {
    it('shows filename after successful upload', () => {
      mockState.file = makeFile('my-sales.xlsx')
      mockState.uploadResponse = {
        file_id: 'f1',
        filename: 'my-sales.xlsx',
        sheets: [],
      }
      render(<FileUpload />)

      expect(screen.getByText('my-sales.xlsx')).toBeInTheDocument()
    })
  })

  describe('error state', () => {
    it('shows error message when error is set', () => {
      mockState.error = 'アップロードに失敗しました'
      render(<FileUpload />)

      expect(screen.getByText('アップロードに失敗しました')).toBeInTheDocument()
    })

    it('does not show error message when error is null', () => {
      mockState.error = null
      render(<FileUpload />)

      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })
  })
})
