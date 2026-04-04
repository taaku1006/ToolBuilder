import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AgentLog } from '../AgentLog'
import type { AgentLogEntry } from '../../types'

const phaseUEntry: AgentLogEntry = {
  phase: 'U',
  action: 'start',
  content: 'タスクとデータを分析中',
  timestamp: '2024-01-01T00:00:00Z',
}

const phaseUEntry2: AgentLogEntry = {
  phase: 'U',
  action: 'complete',
  content: '複雑度: standard, 戦略: pandas',
  timestamp: '2024-01-01T00:00:01Z',
}

const phaseGEntry: AgentLogEntry = {
  phase: 'G',
  action: 'start',
  content: 'コード生成中 (standard モード)',
  timestamp: '2024-01-01T00:00:02Z',
}

const phaseVFEntry: AgentLogEntry = {
  phase: 'VF',
  action: 'start',
  content: '検証 (attempt 1/4)',
  timestamp: '2024-01-01T00:00:03Z',
}

const phaseLEntry: AgentLogEntry = {
  phase: 'L',
  action: 'done',
  content: '学習完了',
  timestamp: '2024-01-01T00:00:04Z',
}

describe('AgentLog', () => {
  it('renders nothing when agentLog is empty', () => {
    const { container } = render(<AgentLog agentLog={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders the section heading', () => {
    render(<AgentLog agentLog={[phaseUEntry]} />)
    expect(screen.getByText('エージェントログ')).toBeInTheDocument()
  })

  it('renders Phase U with correct label', () => {
    render(<AgentLog agentLog={[phaseUEntry]} />)
    expect(screen.getByText('Phase U: 分析・戦略')).toBeInTheDocument()
  })

  it('renders Phase G with correct label', () => {
    render(<AgentLog agentLog={[phaseGEntry]} />)
    expect(screen.getByText('Phase G: コード生成')).toBeInTheDocument()
  })

  it('renders Phase VF with correct label', () => {
    render(<AgentLog agentLog={[phaseVFEntry]} />)
    expect(screen.getByText('Phase VF: 検証・修正')).toBeInTheDocument()
  })

  it('renders Phase L with correct label', () => {
    render(<AgentLog agentLog={[phaseLEntry]} />)
    expect(screen.getByText('Phase L: 学習')).toBeInTheDocument()
  })

  it('groups entries by phase', () => {
    render(<AgentLog agentLog={[phaseUEntry, phaseUEntry2, phaseGEntry]} />)
    expect(screen.getByText('Phase U: 分析・戦略')).toBeInTheDocument()
    expect(screen.getByText('Phase G: コード生成')).toBeInTheDocument()
    const phaseHeaders = screen.getAllByRole('button')
    expect(phaseHeaders).toHaveLength(2)
  })

  it('shows content entries inside their phase', () => {
    render(<AgentLog agentLog={[phaseUEntry, phaseUEntry2]} />)
    expect(screen.getByText('タスクとデータを分析中')).toBeInTheDocument()
    expect(screen.getByText('複雑度: standard, 戦略: pandas')).toBeInTheDocument()
  })

  it('collapses phase content when header is clicked', async () => {
    const user = userEvent.setup()
    render(<AgentLog agentLog={[phaseUEntry]} />)

    const header = screen.getByRole('button', { name: /Phase U/ })
    await user.click(header)

    expect(screen.queryByText('タスクとデータを分析中')).not.toBeVisible()
  })

  it('shows completed status when phase has action "done"', () => {
    render(<AgentLog agentLog={[phaseLEntry]} />)
    expect(screen.getByText('完了')).toBeInTheDocument()
  })

  it('shows running status for phase without action "done"', () => {
    render(<AgentLog agentLog={[phaseGEntry]} />)
    expect(screen.getByText('実行中')).toBeInTheDocument()
  })

  it('renders all v2 phases when all entries are present', () => {
    render(
      <AgentLog
        agentLog={[phaseUEntry, phaseGEntry, phaseVFEntry, phaseLEntry]}
      />
    )
    expect(screen.getByText('Phase U: 分析・戦略')).toBeInTheDocument()
    expect(screen.getByText('Phase G: コード生成')).toBeInTheDocument()
    expect(screen.getByText('Phase VF: 検証・修正')).toBeInTheDocument()
    expect(screen.getByText('Phase L: 学習')).toBeInTheDocument()
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
})
