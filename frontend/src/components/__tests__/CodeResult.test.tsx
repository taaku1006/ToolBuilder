import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CodeResult } from '../CodeResult'
import type { GenerateResponse } from '../../types'

const mockStoreState = {
  response: null as GenerateResponse | null,
}

vi.mock('../../stores/useGenerateStore', () => ({
  useGenerateStore: () => mockStoreState,
}))

const mockResponse: GenerateResponse = {
  id: 'result-001',
  summary: 'Excelファイルを読み込んで集計します',
  python_code: 'import pandas as pd\ndf = pd.read_excel("data.xlsx")\nprint(df.sum())',
  steps: ['Excelを読み込む', '集計処理を実行する', '結果を表示する'],
  tips: 'pandasライブラリのインストールが必要です: pip install pandas openpyxl',
}

describe('CodeResult', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockStoreState.response = null
  })

  it('renders nothing when there is no response', () => {
    const { container } = render(<CodeResult />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the python code when response is present', () => {
    mockStoreState.response = mockResponse
    render(<CodeResult />)

    expect(screen.getByText(/import pandas as pd/)).toBeInTheDocument()
  })

  it('renders the summary', () => {
    mockStoreState.response = mockResponse
    render(<CodeResult />)

    expect(screen.getByText('Excelファイルを読み込んで集計します')).toBeInTheDocument()
  })

  it('renders all steps', () => {
    mockStoreState.response = mockResponse
    render(<CodeResult />)

    expect(screen.getByText('Excelを読み込む')).toBeInTheDocument()
    expect(screen.getByText('集計処理を実行する')).toBeInTheDocument()
    expect(screen.getByText('結果を表示する')).toBeInTheDocument()
  })

  it('renders the tips', () => {
    mockStoreState.response = mockResponse
    render(<CodeResult />)

    expect(screen.getByText(/pandasライブラリのインストールが必要です/)).toBeInTheDocument()
  })

  it('renders a copy button', () => {
    mockStoreState.response = mockResponse
    render(<CodeResult />)

    expect(screen.getByRole('button', { name: /コピー/ })).toBeInTheDocument()
  })

  it('copy button writes python_code to clipboard', async () => {
    const user = userEvent.setup()
    mockStoreState.response = mockResponse

    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })

    render(<CodeResult />)

    await user.click(screen.getByRole('button', { name: /コピー/ }))

    expect(writeText).toHaveBeenCalledWith(mockResponse.python_code)
  })

  it('shows copied feedback after clicking copy', async () => {
    const user = userEvent.setup()
    mockStoreState.response = mockResponse

    const writeText = vi.fn().mockResolvedValue(undefined)
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText },
      configurable: true,
    })

    render(<CodeResult />)

    await user.click(screen.getByRole('button', { name: /コピー/ }))

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'コピー済み' })).toBeInTheDocument()
    })
  })

  it('does not render steps section when steps array is empty', () => {
    mockStoreState.response = { ...mockResponse, steps: [] }
    render(<CodeResult />)

    expect(screen.queryByText('実行ステップ')).not.toBeInTheDocument()
  })

  it('does not render tips section when tips is empty', () => {
    mockStoreState.response = { ...mockResponse, tips: '' }
    render(<CodeResult />)

    expect(screen.queryByText('ヒント')).not.toBeInTheDocument()
  })
})
