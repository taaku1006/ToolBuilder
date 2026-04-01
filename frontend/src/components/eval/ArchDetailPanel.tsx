import { PHASE_ORDER } from '../../constants/phases'
import type { Architecture } from '../../api/eval'
import { PhaseTag } from './shared/PhaseTag'
import { FlowBlock } from './shared/FlowBlock'
import { FlowArrow } from './shared/FlowArrow'

interface ArchDetailPanelProps {
  arch: Architecture
}

export function ArchDetailPanel({ arch }: ArchDetailPanelProps) {
  const p = arch.pipeline

  if (!p) {
    const legacyPhases = arch.phases?.length ? arch.phases : [...PHASE_ORDER]
    return (
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-2">
        <div className="font-mono text-sm text-white">{arch.id}</div>
        <div className="text-xs text-gray-500">{arch.description}</div>
        <div className="flex items-center gap-1">
          {legacyPhases.map((ph, i) => (
            <div key={ph} className="flex items-center">
              {i > 0 && <span className="mx-1 text-xs text-gray-600">→</span>}
              <PhaseTag phase={ph} />
            </div>
          ))}
        </div>
      </div>
    )
  }

  const pipelineExt = p as unknown as Record<string, unknown>

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm text-white">{arch.id}</span>
        <span className="text-xs text-gray-500">{arch.model} / retry:{p.debug_retry_limit}</span>
      </div>
      {arch.description && <div className="text-xs text-gray-400">{arch.description}</div>}

      <div className="flex flex-col items-start gap-0">
        <div className="flex items-center gap-2">
          <FlowBlock label="A: Explore" phase="A" active={p.explore}>
            <span>Excel構造分析</span>
          </FlowBlock>
          <span className="text-gray-600 text-xs">→</span>
          <FlowBlock label="B: Reflect" phase="B" active={p.reflect}>
            <span>ツール必要性判断</span>
          </FlowBlock>
        </div>

        <FlowArrow />

        {p.decompose ? (
          <div className="border border-dashed border-yellow-700/50 rounded-lg p-2 w-full relative">
            <div className="text-[10px] text-yellow-400 font-mono absolute -top-2 left-2 bg-gray-800 px-1">
              P: Task Decomposition
            </div>
            <div className="flex items-center gap-2 mt-1">
              <FlowBlock label="P: Plan" phase="C" active>
                <span>タスク分解</span>
              </FlowBlock>
              <span className="text-gray-600 text-xs">→</span>
              <div className="border border-gray-600 rounded px-2 py-1.5 bg-gray-900/50">
                <div className="text-[10px] text-gray-400 font-mono mb-1">for each subtask:</div>
                <div className="flex items-center gap-1">
                  <FlowBlock label="C.n" phase="C" active>
                    <span>生成</span>
                  </FlowBlock>
                  <span className="text-gray-600 text-[10px]">→</span>
                  <FlowBlock label="D.n" phase="D" active>
                    <span>Debug x{p.subtask_debug_retries}</span>
                  </FlowBlock>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <FlowBlock label="C: Generate" phase="C" active>
              <span>コード生成</span>
            </FlowBlock>
            <span className="text-gray-600 text-xs">→</span>
            <FlowBlock label="D: Debug" phase="D" active>
              <span>自律修正 x{p.debug_retry_limit}</span>
            </FlowBlock>
          </div>
        )}

        <FlowArrow />

        <div className="relative w-full">
          <FlowBlock label="F: Quality Check" phase="E" active={p.eval_debug}>
            <span>
              正解 Excel 比較
              {p.eval_debug && p.eval_retry_strategy !== 'none' && (
                <span className="ml-1 text-yellow-400">
                  ({p.eval_retry_strategy} x{p.eval_retry_max_loops})
                </span>
              )}
            </span>
          </FlowBlock>
          {p.eval_debug && p.eval_retry_strategy === 'replan' && (
            <div className="absolute -right-1 top-1/2 -translate-y-1/2 flex items-center">
              <div className="text-yellow-500 text-[10px] whitespace-nowrap ml-2">
                ↺ 失敗時 P に再計画
              </div>
            </div>
          )}
          {p.eval_debug && p.eval_retry_strategy === 'restart' && (
            <div className="absolute -right-1 top-1/2 -translate-y-1/2 flex items-center">
              <div className="text-orange-500 text-[10px] whitespace-nowrap ml-2">
                ↺ 失敗時 全やり直し
              </div>
            </div>
          )}
        </div>

        <FlowArrow />

        <FlowBlock label="G: LLM Eval" phase="E" active={pipelineExt.llm_eval_debug === true}>
          <span>
            LLM評価デバッグ
            {pipelineExt.llm_eval_debug === true && (
              <span className="ml-1 text-purple-400">
                (閾値:{(pipelineExt.llm_eval_score_threshold as number) ?? 7.0}/10 x{(pipelineExt.llm_eval_retry_limit as number) ?? 2})
              </span>
            )}
          </span>
        </FlowBlock>

        <FlowArrow />

        <FlowBlock label="E: Skills" phase="E" active={(pipelineExt.skills as boolean) ?? true}>
          <span>スキル保存提案</span>
        </FlowBlock>
      </div>
    </div>
  )
}
