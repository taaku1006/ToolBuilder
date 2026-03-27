import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CodeResult } from '../CodeResult'
import type { GenerateResponse, ExecuteResponse } from '../../types'

const mockExecute = vi.fn()

const mockGenerateStoreState = {
  response: null as GenerateResponse | null,
}

const mockExecuteStoreState = {
  executeResponse: null as ExecuteResponse | null,
  executing: false,
  executeError: null as string | null,
  execute: mockExecute,
}

vi.mock('../../stores/useGenerateStore', () => ({
  useGenerateStore: () => mockGenerateStoreState,
}))

vi.mock('../../stores/useExecuteStore', () => ({
  useExecuteStore: () => mockExecuteStoreState,
}))

const mockResponse: GenerateResponse = {
  id: 'result-001',
  summary: 'Excelファイルを読み込んで集計します',
  python_code: 'import pandas as pd\ndf = pd.read_excel("data.xlsx")\nprint(df.sum())',
  steps: ['Excelを読み込む', '集計処理を実行する', '結果を表示する'],
  tips: 'pandasライブラリのインストールが必要です: pip install pandas openpyxl',
}

const mockExecuteResponse: ExecuteResponse = {
  stdout: 'col1    10\ncol2    20\ndtype: int64\n',
  stderr: '',
  elapsed_ms: 456,
  output_files: [],
  success: true,
}

describe('CodeResult', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGenerateStoreState.response = null
    mockExecuteStoreState.executeResponse = null
    mockExecuteStoreState.executing = false
    mockExecuteStoreState.executeError = null
  })

  it('renders nothing when there is no response', () => {
    const { container } = render(<CodeResult />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the python code when response is present', () => {
    mockGenerateStoreState.response = mockResponse
    render(<CodeResult />)

    expect(screen.getByText(/import pandas as pd/)).toBeInTheDocument()
  })

  it('renders the summary', () => {
    mockGenerateStoreState.response = mockResponse
    render(<CodeResult />)

    expect(screen.getByText('Excelファイルを読み込んで集計します')).toBeInTheDocument()
  })

  it('renders all steps', () => {
    mockGenerateStoreState.response = mockResponse
    render(<CodeResult />)

    expect(screen.getByText('Excelを読み込む')).toBeInTheDocument()
    expect(screen.getByText('集計処理を実行する')).toBeInTheDocument()
    expect(screen.getByText('結果を表示する')).toBeInTheDocument()
  })

  it('renders the tips', () => {
    mockGenerateStoreState.response = mockResponse
    render(<CodeResult />)

    expect(screen.getByText(/pandasライブラリのインストールが必要です/)).toBeInTheDocument()
  })

  it('renders a copy button', () => {
    mockGenerateStoreState.response = mockResponse
    render(<CodeResult />)

    expect(screen.getByRole('button', { name: /コピー/ })).toBeInTheDocument()
  })

  it('copy button writes python_code to clipboard', async () => {
    const user = userEvent.setup()
    mockGenerateStoreState.response = mockResponse

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
    mockGenerateStoreState.response = mockResponse

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
    mockGenerateStoreState.response = { ...mockResponse, steps: [] }
    render(<CodeResult />)

    expect(screen.queryByText('実行ステップ')).not.toBeInTheDocument()
  })

  it('does not render tips section when tips is empty', () => {
    mockGenerateStoreState.response = { ...mockResponse, tips: '' }
    render(<CodeResult />)

    expect(screen.queryByText('ヒント')).not.toBeInTheDocument()
  })

  // Execute button tests
  it('renders an Execute button when response is present', () => {
    mockGenerateStoreState.response = mockResponse
    render(<CodeResult />)

    expect(screen.getByRole('button', { name: /実行/ })).toBeInTheDocument()
  })

  it('calls execute from useExecuteStore when Execute button is clicked', async () => {
    const user = userEvent.setup()
    mockGenerateStoreState.response = mockResponse
    mockExecute.mockResolvedValue(undefined)
    render(<CodeResult />)

    await user.click(screen.getByRole('button', { name: /実行/ }))

    expect(mockExecute).toHaveBeenCalledWith(mockResponse.python_code, undefined)
  })

  it('Execute button is disabled during execution', () => {
    mockGenerateStoreState.response = mockResponse
    mockExecuteStoreState.executing = true
    render(<CodeResult />)

    expect(screen.getByRole('button', { name: /実行中/ })).toBeDisabled()
  })

  it('shows a loading spinner during execution', () => {
    mockGenerateStoreState.response = mockResponse
    mockExecuteStoreState.executing = true
    render(<CodeResult />)

    expect(screen.getByTestId('execute-spinner')).toBeInTheDocument()
  })

  it('renders stdout when executeResponse is present and successful', () => {
    mockGenerateStoreState.response = mockResponse
    mockExecuteStoreState.executeResponse = mockExecuteResponse
    render(<CodeResult />)

    expect(screen.getByTestId('exec-stdout')).toHaveTextContent(/col1/)
  })

  it('renders success badge when execution succeeds', () => {
    mockGenerateStoreState.response = mockResponse
    mockExecuteStoreState.executeResponse = mockExecuteResponse
    render(<CodeResult />)

    expect(screen.getByText('成功')).toBeInTheDocument()
  })

  it('renders elapsed_ms when executeResponse is present', () => {
    mockGenerateStoreState.response = mockResponse
    mockExecuteStoreState.executeResponse = mockExecuteResponse
    render(<CodeResult />)

    expect(screen.getByText(/456/)).toBeInTheDocument()
  })

  it('renders stderr in red pre block when present', () => {
    mockGenerateStoreState.response = mockResponse
    mockExecuteStoreState.executeResponse = {
      ...mockExecuteResponse,
      stderr: 'NameError: name "x" is not defined',
      success: false,
    }
    render(<CodeResult />)

    const stderrBlock = screen.getByText(/NameError/).closest('pre')
    expect(stderrBlock).toHaveClass('text-red-400')
  })

  it('renders error badge when execution fails', () => {
    mockGenerateStoreState.response = mockResponse
    mockExecuteStoreState.executeResponse = {
      ...mockExecuteResponse,
      success: false,
      stderr: 'Error occurred',
    }
    render(<CodeResult />)

    expect(screen.getByText('エラー')).toBeInTheDocument()
  })

  it('renders output file list when output_files is not empty', () => {
    mockGenerateStoreState.response = mockResponse
    mockExecuteStoreState.executeResponse = {
      ...mockExecuteResponse,
      output_files: ['output.csv', 'chart.png'],
    }
    render(<CodeResult />)

    expect(screen.getByText('output.csv')).toBeInTheDocument()
    expect(screen.getByText('chart.png')).toBeInTheDocument()
  })

  it('does not render output files section when output_files is empty', () => {
    mockGenerateStoreState.response = mockResponse
    mockExecuteStoreState.executeResponse = mockExecuteResponse
    render(<CodeResult />)

    expect(screen.queryByText('出力ファイル')).not.toBeInTheDocument()
  })

  it('does not render execution result section before any execution', () => {
    mockGenerateStoreState.response = mockResponse
    render(<CodeResult />)

    expect(screen.queryByText('実行結果')).not.toBeInTheDocument()
  })

  it('shows executeError message when present', () => {
    mockGenerateStoreState.response = mockResponse
    mockExecuteStoreState.executeError = '実行に失敗しました。'
    render(<CodeResult />)

    expect(screen.getByText('実行に失敗しました。')).toBeInTheDocument()
  })
})
