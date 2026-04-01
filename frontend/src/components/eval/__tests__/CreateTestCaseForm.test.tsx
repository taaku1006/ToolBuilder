import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CreateTestCaseForm } from '../CreateTestCaseForm'

vi.mock('../../../api/eval', () => ({
  createTestCase: vi.fn(),
}))

import { createTestCase } from '../../../api/eval'

describe('CreateTestCaseForm', () => {
  beforeEach(() => {
    vi.mocked(createTestCase).mockResolvedValue({
      id: 'new-tc-001',
      task: 'Test task',
      description: 'Test desc',
      file_path: null,
      expected_file_path: null,
      expected_success: true,
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  it('renders form fields', () => {
    render(<CreateTestCaseForm onCreated={vi.fn()} onClose={vi.fn()} />)
    expect(screen.getByPlaceholderText(/タスク指示文/)).toBeInTheDocument()
    expect(screen.getByPlaceholderText(/Description/)).toBeInTheDocument()
  })

  it('renders submit button', () => {
    render(<CreateTestCaseForm onCreated={vi.fn()} onClose={vi.fn()} />)
    expect(screen.getByText('Add Test Case')).toBeInTheDocument()
  })

  it('submit button is disabled when task is empty', () => {
    render(<CreateTestCaseForm onCreated={vi.fn()} onClose={vi.fn()} />)
    const submitBtn = screen.getByText('Add Test Case')
    expect(submitBtn).toBeDisabled()
  })

  it('submit button is enabled when task has value', async () => {
    const user = userEvent.setup()
    render(<CreateTestCaseForm onCreated={vi.fn()} onClose={vi.fn()} />)

    await user.type(screen.getByPlaceholderText(/タスク指示文/), 'My task')
    expect(screen.getByText('Add Test Case')).not.toBeDisabled()
  })

  it('calls createTestCase with task and description on submit', async () => {
    const user = userEvent.setup()
    const onCreated = vi.fn()
    const onClose = vi.fn()

    render(<CreateTestCaseForm onCreated={onCreated} onClose={onClose} />)

    await user.type(screen.getByPlaceholderText(/タスク指示文/), 'My task')
    await user.type(screen.getByPlaceholderText(/Description/), 'My desc')

    fireEvent.submit(screen.getByRole('button', { name: 'Add Test Case' }).closest('form')!)

    await waitFor(() => {
      expect(createTestCase).toHaveBeenCalledWith('My task', 'My desc', undefined, undefined)
    })
  })

  it('calls onCreated and onClose after successful submission', async () => {
    const user = userEvent.setup()
    const onCreated = vi.fn()
    const onClose = vi.fn()

    render(<CreateTestCaseForm onCreated={onCreated} onClose={onClose} />)

    await user.type(screen.getByPlaceholderText(/タスク指示文/), 'My task')
    fireEvent.submit(screen.getByRole('button', { name: 'Add Test Case' }).closest('form')!)

    await waitFor(() => {
      expect(onCreated).toHaveBeenCalled()
      expect(onClose).toHaveBeenCalled()
    })
  })

  it('shows error message when createTestCase fails', async () => {
    vi.mocked(createTestCase).mockRejectedValue(new Error('API error'))
    const user = userEvent.setup()

    render(<CreateTestCaseForm onCreated={vi.fn()} onClose={vi.fn()} />)

    await user.type(screen.getByPlaceholderText(/タスク指示文/), 'My task')
    fireEvent.submit(screen.getByRole('button', { name: 'Add Test Case' }).closest('form')!)

    await waitFor(() => {
      expect(screen.getByText('API error')).toBeInTheDocument()
    })
  })

  it('calls onClose when cancel button is clicked', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()

    render(<CreateTestCaseForm onCreated={vi.fn()} onClose={onClose} />)

    await user.click(screen.getByRole('button', { name: '✕' }))
    expect(onClose).toHaveBeenCalled()
  })
})
