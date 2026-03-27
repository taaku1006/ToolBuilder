import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TaskInput } from '../TaskInput'

const mockSetTask = vi.fn()
const mockGenerate = vi.fn()

const mockState = {
  task: '',
  loading: false,
  setTask: mockSetTask,
  generate: mockGenerate,
}

vi.mock('../../stores/useGenerateStore', () => ({
  useGenerateStore: () => mockState,
}))

describe('TaskInput', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockState.task = ''
    mockState.loading = false
  })

  it('renders a textarea', () => {
    render(<TaskInput />)
    expect(screen.getByRole('textbox')).toBeInTheDocument()
  })

  it('renders the Generate button', () => {
    render(<TaskInput />)
    expect(screen.getByRole('button', { name: /生成/ })).toBeInTheDocument()
  })

  it('calls setTask when user types in the textarea', async () => {
    const user = userEvent.setup()
    render(<TaskInput />)

    await user.type(screen.getByRole('textbox'), 'A')

    expect(mockSetTask).toHaveBeenCalledWith('A')
  })

  it('calls generate when Generate button is clicked', async () => {
    const user = userEvent.setup()
    render(<TaskInput />)

    await user.click(screen.getByRole('button', { name: /生成/ }))

    expect(mockGenerate).toHaveBeenCalledTimes(1)
  })

  it('calls generate with undefined fileId when no fileId prop is given', async () => {
    const user = userEvent.setup()
    render(<TaskInput />)

    await user.click(screen.getByRole('button', { name: /生成/ }))

    expect(mockGenerate).toHaveBeenCalledWith(undefined)
  })

  it('calls generate with fileId when fileId prop is provided', async () => {
    const user = userEvent.setup()
    render(<TaskInput fileId="file-abc-123" />)

    await user.click(screen.getByRole('button', { name: /生成/ }))

    expect(mockGenerate).toHaveBeenCalledWith('file-abc-123')
  })

  it('calls generate when Cmd+Enter is pressed in textarea', async () => {
    const user = userEvent.setup()
    render(<TaskInput />)

    const textarea = screen.getByRole('textbox')
    await user.click(textarea)
    await user.keyboard('{Meta>}{Enter}{/Meta}')

    expect(mockGenerate).toHaveBeenCalledTimes(1)
  })

  it('disables the button when loading is true', () => {
    mockState.loading = true
    render(<TaskInput />)

    expect(screen.getByRole('button', { name: /生成/ })).toBeDisabled()
  })

  it('disables the textarea when loading is true', () => {
    mockState.loading = true
    render(<TaskInput />)

    expect(screen.getByRole('textbox')).toBeDisabled()
  })

  it('shows placeholder text in textarea', () => {
    render(<TaskInput />)
    expect(screen.getByPlaceholderText(/タスクを日本語で入力/)).toBeInTheDocument()
  })

  it('shows loading text in button when loading', () => {
    mockState.loading = true
    render(<TaskInput />)

    expect(screen.getByRole('button', { name: /生成中/ })).toBeInTheDocument()
  })
})
