/**
 * Central phase definitions. All phase-related UI should reference this.
 * Order defines display order in tables and flowcharts.
 */

export interface PhaseDefinition {
  label: string
  color: string
  description: string
}

export const PHASE_DEFINITIONS: Record<string, PhaseDefinition> = {
  A: {
    label: 'A: Explore',
    color: 'bg-blue-900 text-blue-300',
    description: 'Excel構造分析',
  },
  B: {
    label: 'B: Reflect',
    color: 'bg-purple-900 text-purple-300',
    description: 'ツール必要性判断',
  },
  P: {
    label: 'P: Plan',
    color: 'bg-yellow-900 text-yellow-300',
    description: 'タスク分解',
  },
  C: {
    label: 'C: Generate',
    color: 'bg-green-900 text-green-300',
    description: 'コード生成',
  },
  D: {
    label: 'D: Debug',
    color: 'bg-yellow-900 text-yellow-300',
    description: '自律デバッグ',
  },
  F: {
    label: 'F: Mechanical Eval',
    color: 'bg-pink-900 text-pink-300',
    description: '機械評価デバッグ',
  },
  G: {
    label: 'G: LLM Eval',
    color: 'bg-violet-900 text-violet-300',
    description: 'LLM評価デバッグ',
  },
  E: {
    label: 'E: Skills',
    color: 'bg-teal-900 text-teal-300',
    description: 'スキル保存提案',
  },
}

/** Canonical display order for phases */
export const PHASE_ORDER = ['A', 'B', 'P', 'C', 'D', 'F', 'G', 'E'] as const

/** MagenticOne phase definitions */
export const MAGENTIC_ONE_PHASE_DEFINITIONS: Record<string, PhaseDefinition> = {
  M1E_Orchestrator: {
    label: 'Orchestrator',
    color: 'bg-amber-900 text-amber-300',
    description: 'Task/Progress Ledger',
  },
  M1E_Coder: {
    label: 'Coder',
    color: 'bg-green-900 text-green-300',
    description: 'コード生成',
  },
  M1E_Terminal: {
    label: 'Terminal',
    color: 'bg-cyan-900 text-cyan-300',
    description: 'コード実行',
  },
}

/** Short labels for AgentLog display */
export const PHASE_LABELS: Record<string, string> = {
  A: '探索',
  B: 'ツール合成',
  P: 'タスク分解',
  C: 'コード生成',
  D: '自律デバッグ',
  F: '機械評価デバッグ',
  G: 'LLM評価デバッグ',
  E: 'Skills保存',
  M1E_Orchestrator: 'Orchestrator',
  M1E_Coder: 'Coder',
  M1E_Terminal: 'Terminal',
}
