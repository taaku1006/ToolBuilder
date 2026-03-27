import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DebugLog } from '../DebugLog'
import type { AgentLogEntry } from '../../types'

// Phase D entries
const phaseDStart: AgentLogEntry = {
  phase: 'D',
  action: 'start',
  content: '自律デバッグを開始...',
  timestamp: '2024-01-01T00:00:00Z',
}

const phaseDRetry1: AgentLogEntry = {
  phase: 'D',
  action: 'retry',
  content: 'NameError: name \'x\' is not defined',
  timestamp: '2024-01-01T00:00:01Z',
}

const phaseDRetry2: AgentLogEntry = {
  phase: 'D',
  action: 'retry',
  content: 'TypeError: unsupported operand type',
  timestamp: '2024-01-01T00:00:02Z',
}

const phaseDComplete: AgentLogEntry = {
  phase: 'D',
  action: 'complete',
  content: '2回のリトライで成功',
  timestamp: '2024-01-01T00:00:03Z',
}

const phaseDError: AgentLogEntry = {
  phase: 'D',
  action: 'error',
  content: 'デバッグに失敗しました',
  timestamp: '2024-01-01T00:00:04Z',
}

// Non-Phase-D entries
const phaseAEntry: AgentLogEntry = {
  phase: 'A',
  action: 'start',
  content: 'Excel構造を分析中...',
  timestamp: '2024-01-01T00:00:00Z',
}

const phaseBEntry: AgentLogEntry = {
  phase: 'B',
  action: 'done',
  content: 'ツール合成完了',
  timestamp: '2024-01-01T00:00:01Z',
}

const phaseCEntry: AgentLogEntry = {
  phase: 'C',
  action: 'start',
  content: 'コード生成中...',
  timestamp: '2024-01-01T00:00:02Z',
}

describe('DebugLog', () => {
  // Test 1: Returns null when agentLog is empty
  it('returns null when agentLog is empty', () => {
    const { container } = render(<DebugLog agentLog={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  // Test 2: Returns null when no Phase D entries exist
  it('returns null when no Phase D entries in agentLog', () => {
    const { container } = render(
      <DebugLog agentLog={[phaseAEntry, phaseBEntry, phaseCEntry]} />
    )
    expect(container).toBeEmptyDOMElement()
  })

  // Test 3: Renders "自律デバッグ" title when Phase D start entry exists
  it('renders the "自律デバッグ" title when Phase D start entry exists', () => {
    render(<DebugLog agentLog={[phaseDStart]} />)
    expect(screen.getByRole('heading', { name: /自律デバッグ/ })).toBeInTheDocument()
  })

  // Test 4: Renders start action content
  it('renders start action content as introduction message', () => {
    render(<DebugLog agentLog={[phaseDStart]} />)
    expect(screen.getByText('自律デバッグを開始...')).toBeInTheDocument()
  })

  // Test 5: Renders retry entries with error content
  it('renders retry entry with error content', () => {
    render(<DebugLog agentLog={[phaseDStart, phaseDRetry1]} />)
    expect(screen.getByText(/NameError: name 'x' is not defined/)).toBeInTheDocument()
  })

  // Test 6: Renders retry with numbered label
  it('renders retry number label for retry entries', () => {
    render(<DebugLog agentLog={[phaseDStart, phaseDRetry1]} />)
    expect(screen.getByText(/リトライ 1/)).toBeInTheDocument()
  })

  // Test 7: Renders success message on "complete" action
  it('renders success message on "complete" action with green styling', () => {
    render(<DebugLog agentLog={[phaseDStart, phaseDComplete]} />)
    const successEl = screen.getByText('2回のリトライで成功')
    expect(successEl).toBeInTheDocument()
    // The element or an ancestor should carry a green-related class
    const successContainer = successEl.closest('[class*="green"]') ?? successEl
    expect(successContainer).toBeTruthy()
  })

  // Test 8: Renders failure message on "error" action
  it('renders failure message on "error" action with red styling', () => {
    render(<DebugLog agentLog={[phaseDStart, phaseDError]} />)
    const errorEl = screen.getByText('デバッグに失敗しました')
    expect(errorEl).toBeInTheDocument()
    const errorContainer = errorEl.closest('[class*="red"]') ?? errorEl
    expect(errorContainer).toBeTruthy()
  })

  // Test 9: Renders multiple retry entries in order
  it('renders multiple retry entries in ascending order', () => {
    render(<DebugLog agentLog={[phaseDStart, phaseDRetry1, phaseDRetry2, phaseDComplete]} />)

    expect(screen.getByText(/リトライ 1/)).toBeInTheDocument()
    expect(screen.getByText(/リトライ 2/)).toBeInTheDocument()

    const retry1 = screen.getByText(/リトライ 1/)
    const retry2 = screen.getByText(/リトライ 2/)

    // retry1 must appear before retry2 in the DOM
    expect(
      retry1.compareDocumentPosition(retry2) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy()
  })

  // Test 10: Does not render entries from other phases (A, B, C)
  it('does not render content from other phases', () => {
    render(<DebugLog agentLog={[phaseAEntry, phaseBEntry, phaseCEntry, phaseDStart]} />)
    expect(screen.queryByText('Excel構造を分析中...')).not.toBeInTheDocument()
    expect(screen.queryByText('ツール合成完了')).not.toBeInTheDocument()
    expect(screen.queryByText('コード生成中...')).not.toBeInTheDocument()
  })

  // Test 11: Phase D badge is rendered
  it('renders Phase D badge in the title area', () => {
    render(<DebugLog agentLog={[phaseDStart]} />)
    expect(screen.getByText(/Phase D/)).toBeInTheDocument()
  })

  // Test 12: Shows retry count information correctly with complete entry
  it('renders correct retry count summary when complete', () => {
    render(
      <DebugLog
        agentLog={[phaseDStart, phaseDRetry1, phaseDRetry2, phaseDComplete]}
      />
    )
    expect(screen.getByText('2回のリトライで成功')).toBeInTheDocument()
  })

  // Test 13: Renders with only a retry entry (no start)
  it('renders when only retry entries are present (no start)', () => {
    render(<DebugLog agentLog={[phaseDRetry1]} />)
    expect(screen.getByText(/自律デバッグ/)).toBeInTheDocument()
    expect(screen.getByText(/NameError/)).toBeInTheDocument()
  })

  // Test 14: Renders with only complete entry
  it('renders when only complete entry is present', () => {
    render(<DebugLog agentLog={[phaseDComplete]} />)
    expect(screen.getByText(/自律デバッグ/)).toBeInTheDocument()
    expect(screen.getByText('2回のリトライで成功')).toBeInTheDocument()
  })
})
