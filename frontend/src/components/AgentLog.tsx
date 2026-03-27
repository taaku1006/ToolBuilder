import { useState } from 'react'
import type { AgentLogEntry } from '../types'

const PHASE_LABELS: Record<string, string> = {
  A: '探索',
  B: 'ツール合成',
  C: 'コード生成',
  D: '自律デバッグ',
  E: 'Skills保存',
}

interface PhaseGroup {
  phase: string
  label: string
  entries: AgentLogEntry[]
  isDone: boolean
}

function groupByPhase(agentLog: AgentLogEntry[]): PhaseGroup[] {
  const phaseOrder: string[] = []
  const phaseMap = new Map<string, AgentLogEntry[]>()

  for (const entry of agentLog) {
    if (!phaseMap.has(entry.phase)) {
      phaseOrder.push(entry.phase)
      phaseMap.set(entry.phase, [])
    }
    phaseMap.get(entry.phase)!.push(entry)
  }

  return phaseOrder.map((phase) => {
    const entries = phaseMap.get(phase) ?? []
    const lastEntry = entries[entries.length - 1]
    const isDone = lastEntry?.action === 'done'
    const label = PHASE_LABELS[phase] ?? phase

    return { phase, label, entries, isDone }
  })
}

interface PhaseAccordionProps {
  group: PhaseGroup
}

function PhaseAccordion({ group }: PhaseAccordionProps) {
  const [isOpen, setIsOpen] = useState(true)

  const statusLabel = group.isDone ? '完了' : '実行中'
  const statusClass = group.isDone
    ? 'text-green-400 text-xs font-medium'
    : 'text-yellow-400 text-xs font-medium'

  return (
    <div className="border border-gray-700 rounded-lg overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between px-4 py-3 bg-gray-800 hover:bg-gray-750 text-left transition-colors"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
      >
        <span className="text-sm font-medium text-gray-200">
          Phase {group.phase}: {group.label}
        </span>
        <span className={statusClass}>{statusLabel}</span>
      </button>

      <div
        className="overflow-hidden"
        style={{ display: isOpen ? 'block' : 'none' }}
        aria-hidden={!isOpen}
      >
        <ul className="px-4 py-2 space-y-1 bg-gray-900">
          {group.entries.map((entry, idx) => (
            <li key={idx} className="flex items-start gap-2 text-sm text-gray-400">
              <span className="mt-0.5 text-gray-600 select-none">&#x251C;&#x2500;</span>
              <span>{entry.content}</span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

interface AgentLogProps {
  agentLog: AgentLogEntry[]
}

export function AgentLog({ agentLog }: AgentLogProps) {
  if (agentLog.length === 0) return null

  const groups = groupByPhase(agentLog)

  return (
    <section aria-label="エージェントログ">
      <h2 className="text-sm font-semibold text-gray-400 mb-3">エージェントログ</h2>
      <div className="space-y-2">
        {groups.map((group) => (
          <PhaseAccordion key={group.phase} group={group} />
        ))}
      </div>
    </section>
  )
}
