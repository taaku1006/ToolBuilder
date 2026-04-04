/**
 * Central phase definitions. All phase-related UI should reference this.
 * Order defines display order in tables and flowcharts.
 *
 * v2 Adaptive Pipeline phases: U (Understand), G (Generate), VF (Verify-Fix), L (Learn)
 * MagenticOne phases: M1E_Orchestrator, M1E_Coder, M1E_Terminal
 * C phase is used for final result payload (eval runner compatibility)
 */

export interface PhaseDefinition {
  label: string
  color: string
  description: string
}

export const PHASE_DEFINITIONS: Record<string, PhaseDefinition> = {
  U: {
    label: 'U: Understand',
    color: 'bg-blue-900 text-blue-300',
    description: 'タスク・ファイル分析 + 戦略決定',
  },
  G: {
    label: 'G: Generate',
    color: 'bg-green-900 text-green-300',
    description: 'コード生成',
  },
  VF: {
    label: 'VF: Verify-Fix',
    color: 'bg-yellow-900 text-yellow-300',
    description: '検証・修正ループ',
  },
  L: {
    label: 'L: Learn',
    color: 'bg-teal-900 text-teal-300',
    description: 'パターン学習',
  },
  C: {
    label: 'C: Result',
    color: 'bg-gray-900 text-gray-300',
    description: '最終結果',
  },
}

/** Canonical display order for v2 phases */
export const PHASE_ORDER = ['U', 'G', 'VF', 'L'] as const

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
  U: '分析・戦略',
  G: 'コード生成',
  VF: '検証・修正',
  L: '学習',
  C: '結果',
  M1E_Orchestrator: 'Orchestrator',
  M1E_Coder: 'Coder',
  M1E_Terminal: 'Terminal',
}
