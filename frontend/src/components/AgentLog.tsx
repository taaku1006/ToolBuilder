import { useState } from 'react'
import type { AgentLogEntry } from '../types'
import { PHASE_LABELS } from '../constants/phases'

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
    <div className="border border-gray-800 rounded overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between px-3 py-1.5 bg-gray-900/50 hover:bg-gray-800/50 text-left transition-colors"
        onClick={() => setIsOpen((prev) => !prev)}
        aria-expanded={isOpen}
      >
        <div className="flex items-center gap-2">
          <span className={`inline-block w-1.5 h-1.5 rounded-full ${group.isDone ? 'bg-green-400' : 'bg-yellow-400 animate-pulse'}`} />
          <span className="text-xs font-medium text-gray-300">
            Phase {group.phase}: {group.label}
          </span>
        </div>
        <span className={statusClass}>{statusLabel}</span>
      </button>

      <div
        className="overflow-hidden"
        style={{ display: isOpen ? 'block' : 'none' }}
        aria-hidden={!isOpen}
      >
        <ul className="px-3 py-1 space-y-0.5 bg-gray-950/50">
          {group.entries.map((entry, idx) => (
            <li key={idx} className="flex items-start gap-1.5 text-xs text-gray-500">
              <span className="mt-0.5 text-gray-700 select-none">-</span>
              <span className="font-mono">{entry.content}</span>
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
      <h2 className="text-xs uppercase tracking-wide text-gray-500 mb-2">Agent Log</h2>
      <div className="space-y-1">
        {groups.map((group) => (
          <PhaseAccordion key={group.phase} group={group} />
        ))}
      </div>
    </section>
  )
}
