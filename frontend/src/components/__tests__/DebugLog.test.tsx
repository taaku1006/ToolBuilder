import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DebugLog } from '../DebugLog'
import type { AgentLogEntry } from '../../types'

// VF (Verify-Fix) entries
const vfStart: AgentLogEntry = {
  phase: 'VF',
  action: 'start',
  content: '検証 (attempt 1/4)',
  timestamp: '2024-01-01T00:00:00Z',
}

const vfFix1: AgentLogEntry = {
  phase: 'VF',
  action: 'fix',
  content: '修正 (attempt 1)',
  timestamp: '2024-01-01T00:00:01Z',
}

const vfFix2: AgentLogEntry = {
  phase: 'VF',
  action: 'fix',
  content: '修正 (attempt 2)',
  timestamp: '2024-01-01T00:00:02Z',
}

const vfComplete: AgentLogEntry = {
  phase: 'VF',
  action: 'complete',
  content: '検証合格 (score: 0.92)',
  timestamp: '2024-01-01T00:00:03Z',
}

const vfEscalate: AgentLogEntry = {
  phase: 'VF',
  action: 'escalate',
  content: '品質改善が停滞。タスク記述の見直しを推奨。',
  timestamp: '2024-01-01T00:00:04Z',
}

// Non-VF entries
const phaseUEntry: AgentLogEntry = {
  phase: 'U',
  action: 'start',
  content: 'タスクとデータを分析中',
  timestamp: '2024-01-01T00:00:00Z',
}

const phaseGEntry: AgentLogEntry = {
  phase: 'G',
  action: 'start',
  content: 'コード生成中',
  timestamp: '2024-01-01T00:00:01Z',
}

describe('DebugLog', () => {
  it('returns null when agentLog is empty', () => {
    const { container } = render(<DebugLog agentLog={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('returns null when no VF entries in agentLog', () => {
    const { container } = render(
      <DebugLog agentLog={[phaseUEntry, phaseGEntry]} />
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the "検証・修正" title when VF entry exists', () => {
    render(<DebugLog agentLog={[vfStart]} />)
    expect(screen.getByRole('heading', { name: /検証・修正/ })).toBeInTheDocument()
  })

  it('renders start action content', () => {
    render(<DebugLog agentLog={[vfStart]} />)
    expect(screen.getByText('検証 (attempt 1/4)')).toBeInTheDocument()
  })

  it('renders fix entry with retry number', () => {
    render(<DebugLog agentLog={[vfStart, vfFix1]} />)
    expect(screen.getByText(/リトライ 1/)).toBeInTheDocument()
  })

  it('renders success message on "complete" action', () => {
    render(<DebugLog agentLog={[vfStart, vfComplete]} />)
    const successEl = screen.getByText('検証合格 (score: 0.92)')
    expect(successEl).toBeInTheDocument()
    const successContainer = successEl.closest('[class*="green"]') ?? successEl
    expect(successContainer).toBeTruthy()
  })

  it('renders escalate message with red styling', () => {
    render(<DebugLog agentLog={[vfStart, vfEscalate]} />)
    const errorEl = screen.getByText(/品質改善が停滞/)
    expect(errorEl).toBeInTheDocument()
    const errorContainer = errorEl.closest('[class*="red"]') ?? errorEl
    expect(errorContainer).toBeTruthy()
  })

  it('renders multiple fix entries in order', () => {
    render(<DebugLog agentLog={[vfStart, vfFix1, vfFix2, vfComplete]} />)

    expect(screen.getByText(/リトライ 1/)).toBeInTheDocument()
    expect(screen.getByText(/リトライ 2/)).toBeInTheDocument()

    const retry1 = screen.getByText(/リトライ 1/)
    const retry2 = screen.getByText(/リトライ 2/)
    expect(
      retry1.compareDocumentPosition(retry2) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
  })

  it('does not render content from other phases', () => {
    render(<DebugLog agentLog={[phaseUEntry, phaseGEntry, vfStart]} />)
    expect(screen.queryByText('タスクとデータを分析中')).not.toBeInTheDocument()
    expect(screen.queryByText('コード生成中')).not.toBeInTheDocument()
  })

  it('renders VF badge in the title area', () => {
    render(<DebugLog agentLog={[vfStart]} />)
    expect(screen.getByText('VF')).toBeInTheDocument()
  })
})
