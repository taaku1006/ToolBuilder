import { PHASE_ORDER } from '../../constants/phases'
import type { Architecture } from '../../api/eval'
import { PhaseTag } from './shared/PhaseTag'
import { FlowBlock } from './shared/FlowBlock'
import { FlowArrow } from './shared/FlowArrow'

interface ArchDetailPanelProps {
  arch: Architecture
}

function MagenticOneFlow({ arch }: { arch: Architecture }) {
  const cfg = arch.pipeline as Record<string, unknown> | null
  const maxOuterLoops = (cfg?.max_outer_loops as number) ?? 5
  const maxTurns = (cfg?.max_turns as number) ?? 20
  const maxStalls = (cfg?.max_stalls as number) ?? 3

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm text-white">{arch.id}</span>
        <span className="text-xs text-gray-500">{arch.model}</span>
      </div>
      {arch.description && <div className="text-xs text-gray-400">{arch.description}</div>}

      <div className="flex flex-col items-start gap-0">
        <div className="border border-dashed border-amber-700/50 rounded-lg p-3 w-full relative">
          <div className="text-[10px] text-amber-400 font-mono absolute -top-2 left-2 bg-gray-800 px-1">
            Outer Loop (Task Ledger) x{maxOuterLoops}
          </div>

          <div className="flex flex-col items-start gap-0 mt-1">
            <FlowBlock label="Orchestrator" phase="M1E_Orchestrator" active>
              <span>事実収集 + 計画立案</span>
            </FlowBlock>

            <FlowArrow />

            <div className="border border-dashed border-cyan-700/50 rounded-lg p-3 w-full relative">
              <div className="text-[10px] text-cyan-400 font-mono absolute -top-2 left-2 bg-gray-800 px-1">
                Inner Loop (Progress Ledger) x{maxTurns}
              </div>

              <div className="flex flex-col items-start gap-0 mt-1">
                <FlowBlock label="Progress Ledger" phase="M1E_Orchestrator" active>
                  <span>進捗評価 + 次のエージェント選択</span>
                </FlowBlock>

                <FlowArrow />

                <div className="flex items-center gap-2">
                  <FlowBlock label="Coder" phase="M1E_Coder" active>
                    <span>コード生成</span>
                  </FlowBlock>
                  <span className="text-gray-500 text-xs">or</span>
                  <FlowBlock label="Terminal" phase="M1E_Terminal" active>
                    <span>コード実行</span>
                  </FlowBlock>
                </div>

                <div className="flex items-center gap-1 mt-1">
                  <span className="text-cyan-500 text-[10px]">
                    ↺ stall {maxStalls}回で外ループへ
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1 mt-2">
            <span className="text-amber-500 text-[10px]">
              ↺ stall時: Task Ledger 更新 → 再計画
            </span>
          </div>
        </div>

        <FlowArrow />

        <FlowBlock label="Final Answer" phase="M1E_Orchestrator" active>
          <span>最終回答生成</span>
        </FlowBlock>
      </div>
    </div>
  )
}

function V2PipelineFlow({ arch }: { arch: Architecture }) {
  const v2 = (arch as unknown as Record<string, unknown>).v2_config as Record<string, unknown> | null
  const maxReplan = (v2?.max_replan as number) ?? 2
  const memoryEnabled = (v2?.memory_enabled as boolean) ?? true
  const maxAttempts = (v2?.max_attempts as Record<string, number>) ?? { simple: 2, standard: 4, complex: 6 }

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm text-white">{arch.id}</span>
        <span className="text-xs text-gray-500">{arch.model}</span>
      </div>
      {arch.description && <div className="text-xs text-gray-400">{arch.description}</div>}

      <div className="flex flex-col items-start gap-0">
        {/* Stage 1: UNDERSTAND */}
        <FlowBlock label="U: Understand" phase="U" active>
          <span>
            ファイル分析 (Python) + 戦略決定 (LLM)
            {memoryEnabled && <span className="ml-1 text-teal-400">+ Memory</span>}
          </span>
        </FlowBlock>

        <FlowArrow />

        {/* Outer loop: replan */}
        <div className="border border-dashed border-yellow-700/50 rounded-lg p-3 w-full relative">
          <div className="text-[10px] text-yellow-400 font-mono absolute -top-2 left-2 bg-gray-800 px-1">
            Outer Loop (replan) x{maxReplan}
          </div>

          <div className="flex flex-col items-start gap-0 mt-1">
            {/* Stage 2: GENERATE */}
            <FlowBlock label="G: Generate" phase="G" active>
              <span>
                コード生成 (SIMPLE: {maxAttempts.simple} / STD: {maxAttempts.standard} / COMPLEX: {maxAttempts.complex})
              </span>
            </FlowBlock>

            <FlowArrow />

            {/* Stage 3: VERIFY-FIX */}
            <div className="border border-dashed border-blue-700/50 rounded-lg p-3 w-full relative">
              <div className="text-[10px] text-blue-400 font-mono absolute -top-2 left-2 bg-gray-800 px-1">
                Inner Loop (Verify-Fix)
              </div>

              <div className="flex flex-col items-start gap-0 mt-1">
                <div className="flex items-center gap-2">
                  <FlowBlock label="Verifier" phase="VF" active>
                    <span>実行チェック → 機械比較 → LLM評価</span>
                  </FlowBlock>
                </div>

                <FlowArrow />

                <div className="flex items-center gap-2">
                  <FlowBlock label="RecoveryManager" phase="VF" active>
                    <span>失敗分析 (Python)</span>
                  </FlowBlock>
                  <span className="text-gray-600 text-xs">→</span>
                  <FlowBlock label="Fixer" phase="G" active>
                    <span>コード修正 (LLM)</span>
                  </FlowBlock>
                </div>
              </div>

              <div className="flex items-center gap-1 mt-1">
                <span className="text-blue-500 text-[10px]">
                  ↺ fix → 再検証 / replan → 戦略変更 / escalate → 停止
                </span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1 mt-2">
            <span className="text-yellow-500 text-[10px]">
              ↺ stuck時: Strategize に戻ってアプローチ変更
            </span>
          </div>
        </div>

        <FlowArrow />

        {/* Stage 4: LEARN */}
        <FlowBlock label="L: Learn" phase="L" active={memoryEnabled}>
          <span>パターン・gotcha を記録</span>
        </FlowBlock>
      </div>
    </div>
  )
}

export function ArchDetailPanel({ arch }: ArchDetailPanelProps) {
  const isMagenticOne =
    arch.architecture_type === 'magentic_one_embed' ||
    arch.architecture_type === 'magentic_one_pkg'

  if (isMagenticOne) {
    return <MagenticOneFlow arch={arch} />
  }

  // v2 adaptive (default)
  if (arch.pipeline) {
    return <V2PipelineFlow arch={arch} />
  }

  // Fallback: simple phase tags
  const phases = arch.phases?.length ? arch.phases : [...PHASE_ORDER]
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-2">
      <div className="font-mono text-sm text-white">{arch.id}</div>
      <div className="text-xs text-gray-500">{arch.description}</div>
      <div className="flex items-center gap-1">
        {phases.map((ph, i) => (
          <div key={ph} className="flex items-center">
            {i > 0 && <span className="mx-1 text-xs text-gray-600">→</span>}
            <PhaseTag phase={ph} />
          </div>
        ))}
      </div>
    </div>
  )
}
