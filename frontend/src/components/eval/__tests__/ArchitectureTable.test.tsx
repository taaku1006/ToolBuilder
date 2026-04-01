import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ArchitectureTable } from '../ArchitectureTable'
import type { Architecture } from '../../../api/eval'

const mockArchs: Architecture[] = [
  {
    id: 'v1',
    phases: ['A', 'C', 'D'],
    model: 'gpt-4o',
    debug_retry_limit: 3,
    temperature: 0.0,
    description: 'Baseline architecture',
    pipeline: null,
  },
  {
    id: 'v4-planner',
    phases: [],
    model: 'gpt-4o-mini',
    debug_retry_limit: 2,
    temperature: 0.0,
    description: 'Planner architecture',
    pipeline: {
      explore: true,
      reflect: true,
      decompose: true,
      debug_retry_limit: 2,
      eval_debug: false,
      eval_retry_strategy: 'none',
      eval_retry_max_loops: 0,
      subtask_debug_retries: 1,
    },
  },
]

describe('ArchitectureTable', () => {
  it('renders architecture IDs', () => {
    render(
      <ArchitectureTable
        archs={mockArchs}
        selectedArchs={new Set()}
        toggleArch={vi.fn()}
        detailArchId={null}
        setDetailArchId={vi.fn()}
      />,
    )
    expect(screen.getByText('v1')).toBeInTheDocument()
    expect(screen.getByText('v4-planner')).toBeInTheDocument()
  })

  it('renders architecture descriptions', () => {
    render(
      <ArchitectureTable
        archs={mockArchs}
        selectedArchs={new Set()}
        toggleArch={vi.fn()}
        detailArchId={null}
        setDetailArchId={vi.fn()}
      />,
    )
    expect(screen.getByText('Baseline architecture')).toBeInTheDocument()
    expect(screen.getByText('Planner architecture')).toBeInTheDocument()
  })

  it('calls toggleArch when row is clicked', async () => {
    const user = userEvent.setup()
    const toggleArch = vi.fn()

    render(
      <ArchitectureTable
        archs={mockArchs}
        selectedArchs={new Set()}
        toggleArch={toggleArch}
        detailArchId={null}
        setDetailArchId={vi.fn()}
      />,
    )

    await user.click(screen.getByText('v1'))
    expect(toggleArch).toHaveBeenCalledWith('v1')
  })

  it('shows selected state for architectures in selectedArchs', () => {
    const { container } = render(
      <ArchitectureTable
        archs={mockArchs}
        selectedArchs={new Set(['v1'])}
        toggleArch={vi.fn()}
        detailArchId={null}
        setDetailArchId={vi.fn()}
      />,
    )
    // Selected row should have blue border
    const selectedRow = container.querySelector('tr.border-l-blue-600')
    expect(selectedRow).toBeInTheDocument()
  })

  it('groups architectures by category', () => {
    render(
      <ArchitectureTable
        archs={mockArchs}
        selectedArchs={new Set()}
        toggleArch={vi.fn()}
        detailArchId={null}
        setDetailArchId={vi.fn()}
      />,
    )
    expect(screen.getByText('Baseline')).toBeInTheDocument()
    expect(screen.getByText('Planner')).toBeInTheDocument()
  })

  it('renders model names', () => {
    render(
      <ArchitectureTable
        archs={mockArchs}
        selectedArchs={new Set()}
        toggleArch={vi.fn()}
        detailArchId={null}
        setDetailArchId={vi.fn()}
      />,
    )
    expect(screen.getByText('gpt-4o')).toBeInTheDocument()
    expect(screen.getByText('gpt-4o-mini')).toBeInTheDocument()
  })
})
