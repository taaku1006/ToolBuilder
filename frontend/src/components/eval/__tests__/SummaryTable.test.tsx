import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SummaryTable } from '../SummaryTable'
import type { EvalReport, Architecture } from '../../../api/eval'

const mockReport: EvalReport = {
  summary: {
    v1: {
      success_rate: 0.8,
      avg_tokens: 1500,
      avg_duration_ms: 5000,
      avg_retries: 1.2,
      avg_cost_usd: 0.0025,
      total_cost_usd: 0.01,
      total_runs: 4,
    },
    v2: {
      success_rate: 0.5,
      avg_tokens: 2000,
      avg_duration_ms: 8000,
      avg_retries: 2.0,
      avg_cost_usd: 0.004,
      total_cost_usd: 0.016,
      total_runs: 4,
    },
  },
  comparison_matrix: {},
  best_architecture: 'v1',
  architecture_ids: ['v1', 'v2'],
  test_case_ids: ['tc-001'],
}

const mockArchs: Architecture[] = [
  {
    id: 'v1',
    phases: ['A', 'C', 'D'],
    model: 'gpt-4o',
    debug_retry_limit: 3,
    temperature: 0.0,
    description: 'Baseline',
    pipeline: null,
  },
  {
    id: 'v2',
    phases: ['C', 'D'],
    model: 'gpt-4o-mini',
    debug_retry_limit: 1,
    temperature: 0.0,
    description: 'Minimal',
    pipeline: null,
  },
]

describe('SummaryTable', () => {
  it('renders architecture IDs in table', () => {
    render(<SummaryTable report={mockReport} archs={mockArchs} />)
    expect(screen.getByText('v1')).toBeInTheDocument()
    expect(screen.getByText('v2')).toBeInTheDocument()
  })

  it('shows BEST label for best architecture', () => {
    render(<SummaryTable report={mockReport} archs={mockArchs} />)
    expect(screen.getByText('BEST')).toBeInTheDocument()
  })

  it('renders success rates', () => {
    render(<SummaryTable report={mockReport} archs={mockArchs} />)
    // 80% and 50% should be displayed
    expect(screen.getByText('80%')).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
  })

  it('renders avg tokens', () => {
    render(<SummaryTable report={mockReport} archs={mockArchs} />)
    expect(screen.getByText('1,500')).toBeInTheDocument()
    expect(screen.getByText('2,000')).toBeInTheDocument()
  })

  it('renders column headers', () => {
    render(<SummaryTable report={mockReport} archs={mockArchs} />)
    expect(screen.getByText('Architecture')).toBeInTheDocument()
    expect(screen.getByText('Success')).toBeInTheDocument()
    expect(screen.getByText('Avg Tokens')).toBeInTheDocument()
  })
})
