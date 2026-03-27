import { describe, it, expect, vi } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AgentLog } from '../AgentLog'
import type { AgentLogEntry } from '../../types'

const phaseAEntry: AgentLogEntry = {
  phase: 'A',
  action: 'start',
  content: 'Excel構造を分析中...',
  timestamp: '2024-01-01T00:00:00Z',
}

const phaseAEntry2: AgentLogEntry = {
  phase: 'A',
  action: 'result',
  content: '5列、1000行を検出',
  timestamp: '2024-01-01T00:00:01Z',
}

const phaseBEntry: AgentLogEntry = {
  phase: 'B',
  action: 'done',
  content: 'カスタムツール不要と判断',
  timestamp: '2024-01-01T00:00:02Z',
}

const phaseCEntry: AgentLogEntry = {
  phase: 'C',
  action: 'start',
  content: 'Pythonコードを生成中...',
  timestamp: '2024-01-01T00:00:03Z',
}

const phaseDEntry: AgentLogEntry = {
  phase: 'D',
  action: 'debug',
  content: 'エラーを修正中...',
  timestamp: '2024-01-01T00:00:04Z',
}

const phaseEEntry: AgentLogEntry = {
  phase: 'E',
  action: 'save',
  content: 'スキルを保存中...',
  timestamp: '2024-01-01T00:00:05Z',
}

describe('AgentLog', () => {
  it('renders nothing when agentLog is empty', () => {
    const { container } = render(<AgentLog agentLog={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the section heading', () => {
    render(<AgentLog agentLog={[phaseAEntry]} />)
    expect(screen.getByText('エージェントログ')).toBeInTheDocument()
  })

  it('renders Phase A with correct Japanese label', () => {
    render(<AgentLog agentLog={[phaseAEntry]} />)
    expect(screen.getByText('Phase A: 探索')).toBeInTheDocument()
  })

  it('renders Phase B with correct Japanese label', () => {
    render(<AgentLog agentLog={[phaseBEntry]} />)
    expect(screen.getByText('Phase B: ツール合成')).toBeInTheDocument()
  })

  it('renders Phase C with correct Japanese label', () => {
    render(<AgentLog agentLog={[phaseCEntry]} />)
    expect(screen.getByText('Phase C: コード生成')).toBeInTheDocument()
  })

  it('renders Phase D with correct Japanese label', () => {
    render(<AgentLog agentLog={[phaseDEntry]} />)
    expect(screen.getByText('Phase D: 自律デバッグ')).toBeInTheDocument()
  })

  it('renders Phase E with correct Japanese label', () => {
    render(<AgentLog agentLog={[phaseEEntry]} />)
    expect(screen.getByText('Phase E: Skills保存')).toBeInTheDocument()
  })

  it('groups entries by phase', () => {
    render(<AgentLog agentLog={[phaseAEntry, phaseAEntry2, phaseBEntry]} />)
    // Two phase headings
    expect(screen.getByText('Phase A: 探索')).toBeInTheDocument()
    expect(screen.getByText('Phase B: ツール合成')).toBeInTheDocument()
    // Only two phase blocks (not four rows)
    const phaseHeaders = screen.getAllByRole('button')
    expect(phaseHeaders).toHaveLength(2)
  })

  it('shows content entries inside their phase', () => {
    render(<AgentLog agentLog={[phaseAEntry, phaseAEntry2]} />)
    expect(screen.getByText('Excel構造を分析中...')).toBeInTheDocument()
    expect(screen.getByText('5列、1000行を検出')).toBeInTheDocument()
  })

  it('phase is expanded by default', () => {
    render(<AgentLog agentLog={[phaseAEntry]} />)
    expect(screen.getByText('Excel構造を分析中...')).toBeVisible()
  })

  it('collapses phase content when header is clicked', async () => {
    const user = userEvent.setup()
    render(<AgentLog agentLog={[phaseAEntry]} />)

    const header = screen.getByRole('button', { name: /Phase A/ })
    await user.click(header)

    expect(screen.queryByText('Excel構造を分析中...')).not.toBeVisible()
  })

  it('re-expands phase content when header is clicked again', async () => {
    const user = userEvent.setup()
    render(<AgentLog agentLog={[phaseAEntry]} />)

    const header = screen.getByRole('button', { name: /Phase A/ })
    await user.click(header)
    await user.click(header)

    expect(screen.getByText('Excel構造を分析中...')).toBeVisible()
  })

  it('shows completed status when phase has action "done"', () => {
    render(<AgentLog agentLog={[phaseBEntry]} />)
    expect(screen.getByText('完了')).toBeInTheDocument()
  })

  it('shows running status for the last phase when it does not have action "done"', () => {
    render(<AgentLog agentLog={[phaseCEntry]} />)
    expect(screen.getByText('実行中')).toBeInTheDocument()
  })

  it('shows completed when earlier phase has entries and last action is done', () => {
    render(<AgentLog agentLog={[phaseAEntry, { ...phaseAEntry2, action: 'done' }]} />)
    expect(screen.getByText('完了')).toBeInTheDocument()
  })

  it('renders multiple phases in order', () => {
    render(<AgentLog agentLog={[phaseAEntry, phaseBEntry, phaseCEntry]} />)
    const buttons = screen.getAllByRole('button')
    expect(buttons[0]).toHaveTextContent('Phase A')
    expect(buttons[1]).toHaveTextContent('Phase B')
    expect(buttons[2]).toHaveTextContent('Phase C')
  })

  it('shows different phases independently collapsible', async () => {
    const user = userEvent.setup()
    render(<AgentLog agentLog={[phaseAEntry, phaseBEntry]} />)

    // Collapse phase A
    const phaseABtn = screen.getByRole('button', { name: /Phase A/ })
    await user.click(phaseABtn)

    // Phase A content hidden, Phase B still visible
    expect(screen.queryByText('Excel構造を分析中...')).not.toBeVisible()
    expect(screen.getByText('カスタムツール不要と判断')).toBeVisible()
  })

  it('renders unknown phase with a fallback label', () => {
    const unknownEntry: AgentLogEntry = {
      phase: 'Z',
      action: 'start',
      content: '不明なフェーズ',
      timestamp: '2024-01-01T00:00:00Z',
    }
    render(<AgentLog agentLog={[unknownEntry]} />)
    expect(screen.getByText(/Phase Z/)).toBeInTheDocument()
  })

  it('applies a check mark indicator for completed phases', () => {
    render(<AgentLog agentLog={[{ ...phaseBEntry, action: 'done' }]} />)
    const header = screen.getByRole('button', { name: /Phase B/ })
    expect(header).toHaveTextContent('完了')
  })

  it('renders all five phases when all entries are present', () => {
    render(
      <AgentLog
        agentLog={[phaseAEntry, phaseBEntry, phaseCEntry, phaseDEntry, phaseEEntry]}
      />
    )
    expect(screen.getByText('Phase A: 探索')).toBeInTheDocument()
    expect(screen.getByText('Phase B: ツール合成')).toBeInTheDocument()
    expect(screen.getByText('Phase C: コード生成')).toBeInTheDocument()
    expect(screen.getByText('Phase D: 自律デバッグ')).toBeInTheDocument()
    expect(screen.getByText('Phase E: Skills保存')).toBeInTheDocument()
  })

  it('handles a single entry with no toggle side effect', () => {
    const { container } = render(<AgentLog agentLog={[phaseAEntry]} />)
    expect(container.firstChild).not.toBeNull()
  })
})
