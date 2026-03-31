import { useCallback, useEffect, useRef, useState } from 'react'
import {
  type Architecture,
  type EvalTestCase,
  type RunStatus,
  type PastRun,
  type EvalReport,
  type ResultDetail,
  getArchitectures,
  getTestCases,
  startRun,
  stopRun,
  getRunStatus,
  listRuns,
  createTestCase,
  deleteTestCase,
  getRunSnapshot,
  getResultFiles,
  diffRuns,
  compareRuns,
  type RunSnapshot,
  type SnapshotDiff,
  type RunComparisonResult,
} from '../api/eval'

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

import { PHASE_DEFINITIONS, PHASE_ORDER } from '../constants/phases'

const PHASE_INFO = PHASE_DEFINITIONS

function PhaseTag({ phase }: { phase: string }) {
  const info = PHASE_INFO[phase]
  return (
    <span className={`px-1.5 py-0.5 rounded text-xs font-mono ${info?.color ?? 'bg-gray-700 text-gray-300'}`}>
      {phase}
    </span>
  )
}

function FlowBlock({
  label,
  phase,
  active,
  children,
}: {
  label: string
  phase?: string
  active: boolean
  children?: React.ReactNode
}) {
  const info = phase ? PHASE_INFO[phase] : null
  return (
    <div
      className={`border rounded-lg px-3 py-2 text-xs ${
        active
          ? `${info?.color ?? 'bg-gray-700 text-gray-300'} border-gray-600`
          : 'bg-gray-800/30 text-gray-600 border-gray-700/50 opacity-50'
      }`}
    >
      <div className="font-mono font-medium">{label}</div>
      {children && <div className="mt-1 font-sans">{children}</div>}
    </div>
  )
}

function FlowArrow({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center py-0.5">
      <div className="w-px h-3 bg-gray-600" />
      <div className="text-gray-600 text-[10px]">▼{label ? ` ${label}` : ''}</div>
    </div>
  )
}

function ArchDetailPanel({ arch }: { arch: Architecture }) {
  const p = arch.pipeline

  // Fallback for legacy phases-only configs
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

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <span className="font-mono text-sm text-white">{arch.id}</span>
        <span className="text-xs text-gray-500">{arch.model} / retry:{p.debug_retry_limit}</span>
      </div>
      {arch.description && <div className="text-xs text-gray-400">{arch.description}</div>}

      {/* Flow chart */}
      <div className="flex flex-col items-start gap-0">
        {/* Row 1: Explore + Reflect */}
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

        {/* Row 2: Code Gen + Debug (or Planner loop) */}
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

        {/* Row 3: Eval Debug (Phase F) */}
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
          {/* Replan loop arrow */}
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

        {/* Row 3b: LLM Eval Debug (Phase G) */}
        <FlowBlock label="G: LLM Eval" phase="E" active={p.llm_eval_debug ?? false}>
          <span>
            LLM評価デバッグ
            {p.llm_eval_debug && (
              <span className="ml-1 text-purple-400">
                (閾値:{p.llm_eval_score_threshold ?? 7.0}/10 x{p.llm_eval_retry_limit ?? 2})
              </span>
            )}
          </span>
        </FlowBlock>

        <FlowArrow />

        {/* Row 4: Skills */}
        <FlowBlock label="E: Skills" phase="E" active={p.skills ?? true}>
          <span>スキル保存提案</span>
        </FlowBlock>
      </div>
    </div>
  )
}

function SuccessBar({ rate, ciLow, ciHigh }: { rate: number; ciLow?: number; ciHigh?: number }) {
  const pct = Math.round(rate * 100)
  const color =
    pct >= 80 ? 'bg-green-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <div className="text-xs">
        <span className="text-gray-400">{pct}%</span>
        {ciLow != null && ciHigh != null && (
          <span className="text-gray-600 ml-1">
            ({Math.round(ciLow * 100)}-{Math.round(ciHigh * 100)}%)
          </span>
        )}
      </div>
    </div>
  )
}

const ERROR_COLORS: Record<string, string> = {
  json_parse: 'bg-orange-900/50 text-orange-300',
  syntax_error: 'bg-red-900/50 text-red-300',
  runtime_error: 'bg-red-900/50 text-red-400',
  timeout: 'bg-yellow-900/50 text-yellow-300',
  api_error: 'bg-purple-900/50 text-purple-300',
  file_not_found: 'bg-blue-900/50 text-blue-300',
  unknown: 'bg-gray-700/50 text-gray-400',
}

function ErrorBreakdown({ breakdown }: { breakdown?: Record<string, number> }) {
  if (!breakdown) return null
  const errors = Object.entries(breakdown).filter(([k]) => k !== 'none')
  if (errors.length === 0) return null
  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {errors.map(([cat, count]) => (
        <span key={cat} className={`text-xs px-1.5 py-0.5 rounded ${ERROR_COLORS[cat] ?? ERROR_COLORS.unknown}`}>
          {cat}: {count}
        </span>
      ))}
    </div>
  )
}

function PhaseBreakdown({ report, archs }: { report: EvalReport; archs: Architecture[] }) {
  const { summary } = report
  const archIds = Object.keys(summary)
  const archMap = Object.fromEntries(archs.map((a) => [a.id, a]))
  // Collect all phases dynamically from data, maintain logical order
  const phaseOrder = [...PHASE_ORDER]
  const seenPhases = new Set<string>()
  for (const id of archIds) {
    const pt = summary[id]?.avg_phase_tokens
    if (pt) {
      for (const p of Object.keys(pt)) {
        seenPhases.add(p)
      }
    }
  }
  const allPhases = phaseOrder.filter((p) => seenPhases.has(p))

  // Check if any architecture has phase token data
  const hasData = archIds.some((id) => {
    const pt = summary[id]?.avg_phase_tokens
    return pt && Object.keys(pt).length > 0
  })
  if (!hasData) return null

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="text-left py-2 px-3 text-gray-400">Architecture</th>
            {allPhases.map((p) => (
              <th key={p} className="text-center py-2 px-2">
                <PhaseTag phase={p} />
              </th>
            ))}
            <th className="text-right py-2 px-3 text-gray-400">Total</th>
          </tr>
        </thead>
        <tbody>
          {archIds.map((archId) => {
            const row = summary[archId]
            const pt = row.avg_phase_tokens ?? {}
            const arch = archMap[archId]
            const model = arch?.model ?? 'gpt-4o'
            const totalPt = Object.values(pt).reduce((a, b) => a + b, 0)

            // Find the phase with the most tokens (bottleneck)
            const maxPhase = Object.entries(pt).reduce(
              (max, [phase, tokens]) => (tokens > max[1] ? [phase, tokens] : max),
              ['', 0],
            )[0]

            return (
              <tr key={archId} className="border-b border-gray-800">
                <td className="py-2 px-3 font-mono text-xs text-gray-300">{archId}</td>
                {allPhases.map((p) => {
                  const tokens = pt[p]
                  if (tokens == null || tokens === 0) {
                    return (
                      <td key={p} className="text-center py-2 px-2 text-gray-700 text-xs">—</td>
                    )
                  }
                  const isMax = p === maxPhase && Object.keys(pt).length > 1
                  return (
                    <td key={p} className={`text-center py-2 px-2 font-mono text-xs ${isMax ? 'text-yellow-400' : 'text-gray-400'}`}>
                      <div>{Math.round(tokens).toLocaleString()}</div>
                      <div className="text-[10px] text-gray-600">tok</div>
                    </td>
                  )
                })}
                <td className="text-right py-2 px-3 font-mono text-xs text-gray-300">
                  {Math.round(totalPt).toLocaleString()}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function scoreColor(score: number, max: number): string {
  const ratio = score / max
  if (ratio >= 0.85) return 'text-green-400'
  if (ratio >= 0.6) return 'text-yellow-400'
  return 'text-red-400'
}

function scoreBg(score: number, max: number): string {
  const ratio = score / max
  if (ratio >= 0.85) return 'bg-green-900/20'
  if (ratio >= 0.6) return 'bg-yellow-900/20'
  return 'bg-red-900/20'
}

function ScoreBar({ value, max, colorClass }: { value: number; max: number; colorClass: string }) {
  const pct = Math.round((value / max) * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-gray-700 rounded-full h-1.5">
        <div className={`h-1.5 rounded-full ${colorClass}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs font-mono w-10 text-right">{max === 10 ? `${value.toFixed(1)}/10` : `${pct}%`}</span>
    </div>
  )
}

function DetailDrawer({
  detail,
  archId,
  caseLabel,
  onClose,
  onDownload,
}: {
  detail: ResultDetail
  archId: string
  caseLabel: string
  onClose: () => void
  onDownload?: () => void
}) {
  const qd = detail.quality_details
  const ld = detail.llm_eval_details
  const qs = detail.quality_score ?? 0
  const ls = detail.llm_eval_score

  return (
    <>
      {/* Backdrop */}
      <div className="fixed inset-0 z-40 bg-black/50" onClick={onClose} />
      {/* Drawer */}
      <div className="fixed right-0 top-0 h-full w-[420px] z-50 bg-gray-900 border-l border-gray-700 flex flex-col shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between px-4 py-3 border-b border-gray-700">
          <div className="min-w-0">
            <div className="text-xs text-gray-500 font-mono truncate">{archId}</div>
            <div className="text-sm text-gray-200 mt-0.5 truncate">{caseLabel}</div>
          </div>
          <button onClick={onClose} className="ml-3 text-gray-500 hover:text-gray-200 text-lg leading-none flex-shrink-0">
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-4 py-3 space-y-5 text-sm">
          {/* F: Mechanical */}
          {qd && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="font-semibold text-pink-300">F: Mechanical</span>
                <span className={`text-xs font-mono ${scoreColor(qs, 1.0)}`}>{Math.round(qs * 100)}%</span>
              </div>
              <ScoreBar value={qs} max={1.0} colorClass={qs >= 0.85 ? 'bg-green-500' : qs >= 0.6 ? 'bg-yellow-500' : 'bg-red-500'} />
              {qd.missing_sheets && qd.missing_sheets.length > 0 && (
                <div className="mt-2">
                  <div className="text-xs text-gray-500 mb-1">Missing sheets</div>
                  <ul className="list-disc list-inside space-y-0.5">
                    {qd.missing_sheets.map((s) => (
                      <li key={s} className="text-xs text-red-400 font-mono">{s}</li>
                    ))}
                  </ul>
                </div>
              )}
              {qd.extra_sheets && qd.extra_sheets.length > 0 && (
                <div className="mt-2">
                  <div className="text-xs text-gray-500 mb-1">Extra sheets</div>
                  <ul className="list-disc list-inside space-y-0.5">
                    {qd.extra_sheets.map((s) => (
                      <li key={s} className="text-xs text-yellow-400 font-mono">{s}</li>
                    ))}
                  </ul>
                </div>
              )}
              {qd.error && (
                <div className="mt-2 text-xs text-red-400 bg-red-900/20 rounded p-2">{qd.error}</div>
              )}
            </div>
          )}

          {/* G: LLM Eval */}
          {ld && ls != null && (
            <div>
              <div className="flex items-center gap-2 mb-2">
                <span className="font-semibold text-purple-300">G: LLM Eval</span>
                <span className={`text-xs font-mono ${scoreColor(ls, 10)}`}>{ls.toFixed(1)}/10</span>
              </div>
              <ScoreBar value={ls} max={10} colorClass={ls >= 8.5 ? 'bg-green-500' : ls >= 6 ? 'bg-yellow-500' : 'bg-red-500'} />
              <div className="mt-3 space-y-2">
                <div>
                  <div className="text-xs text-gray-500 mb-1">Semantic Correctness</div>
                  <ScoreBar value={ld.semantic_correctness} max={10} colorClass={ld.semantic_correctness >= 8.5 ? 'bg-green-500' : ld.semantic_correctness >= 6 ? 'bg-yellow-500' : 'bg-red-500'} />
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">Data Integrity</div>
                  <ScoreBar value={ld.data_integrity} max={10} colorClass={ld.data_integrity >= 8.5 ? 'bg-green-500' : ld.data_integrity >= 6 ? 'bg-yellow-500' : 'bg-red-500'} />
                </div>
                <div>
                  <div className="text-xs text-gray-500 mb-1">Completeness</div>
                  <ScoreBar value={ld.completeness} max={10} colorClass={ld.completeness >= 8.5 ? 'bg-green-500' : ld.completeness >= 6 ? 'bg-yellow-500' : 'bg-red-500'} />
                </div>
              </div>
              {ld.reasoning && (
                <div className="mt-3">
                  <div className="text-xs text-gray-500 mb-1">Reasoning</div>
                  <div className="text-xs text-gray-300 leading-relaxed bg-gray-800 rounded p-3">{ld.reasoning}</div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer */}
        {onDownload && (
          <div className="px-4 py-3 border-t border-gray-700">
            <button
              onClick={onDownload}
              className="w-full py-2 rounded bg-blue-800 hover:bg-blue-700 text-blue-200 text-sm"
            >
              Download Output Files
            </button>
          </div>
        )}
      </div>
    </>
  )
}

function ComparisonMatrix({
  report,
  runId,
  cases,
}: {
  report: EvalReport
  runId?: string
  cases?: EvalTestCase[]
}) {
  const { comparison_matrix, result_details, architecture_ids, test_case_ids } = report
  const [drawerCell, setDrawerCell] = useState<string | null>(null)

  const caseMap = new Map(cases?.map((c) => [c.id, c.description ?? c.id]) ?? [])

  const handleDownload = async (archId: string, caseId: string) => {
    if (!runId) return
    try {
      const data = await getResultFiles(runId, archId, caseId)
      for (const f of data.files) {
        window.open(`/api/download/${f.path}`, '_blank')
      }
    } catch {
      // No files available
    }
  }

  const drawerCellParts = drawerCell?.split('__')
  const drawerCaseId = drawerCellParts?.[0]
  const drawerArchId = drawerCellParts?.[1]
  const drawerDetail = drawerCaseId && drawerArchId ? result_details?.[drawerCaseId]?.[drawerArchId] : undefined

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-700">
              <th className="text-left py-2 px-3 text-gray-400">Test Case</th>
              {architecture_ids.map((a) => (
                <th key={a} className="text-center py-2 px-3 text-gray-400 font-mono text-xs">
                  {a}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {test_case_ids.map((caseId) => (
              <tr key={caseId} className="border-b border-gray-800 hover:bg-gray-800/30">
                <td className="py-2 px-3 text-gray-300 text-xs max-w-[160px]">
                  <div className="truncate" title={caseId}>{caseMap.get(caseId) ?? caseId}</div>
                </td>
                {architecture_ids.map((archId) => {
                  const ok = comparison_matrix[caseId]?.[archId]
                  const detail = result_details?.[caseId]?.[archId]
                  const cellKey = `${caseId}__${archId}`
                  const qs = detail?.quality_score
                  const ls = detail?.llm_eval_score
                  const hasFiles = detail?.output_files && detail.output_files.length > 0

                  return (
                    <td
                      key={archId}
                      className={`text-center py-2 px-2 ${qs != null ? scoreBg(qs, 1.0) : ''}`}
                    >
                      <div className="flex flex-col items-center gap-0.5">
                        <span className={ok ? 'text-green-400 font-bold text-xs' : 'text-red-400 font-bold text-xs'}>
                          {ok ? 'OK' : 'NG'}
                        </span>
                        {qs != null && (
                          <span className={`text-[10px] font-mono ${scoreColor(qs, 1.0)}`}>
                            {Math.round(qs * 100)}%
                          </span>
                        )}
                        {ls != null && (
                          <span className={`text-[10px] font-mono ${scoreColor(ls, 10)}`}>
                            {ls.toFixed(1)}
                          </span>
                        )}
                        {detail && (
                          <button
                            onClick={() => setDrawerCell(cellKey)}
                            className="text-[9px] px-1.5 py-0.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300 mt-0.5"
                          >
                            Detail
                          </button>
                        )}
                        {!detail && hasFiles && (
                          <button
                            onClick={() => handleDownload(archId, caseId)}
                            className="text-[9px] px-1.5 py-0.5 rounded bg-blue-900 hover:bg-blue-800 text-blue-300 mt-0.5"
                          >
                            DL
                          </button>
                        )}
                      </div>
                    </td>
                  )
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {drawerCell && drawerDetail && drawerCaseId && drawerArchId && (
        <DetailDrawer
          detail={drawerDetail}
          archId={drawerArchId}
          caseLabel={caseMap.get(drawerCaseId) ?? drawerCaseId}
          onClose={() => setDrawerCell(null)}
          onDownload={drawerDetail.output_files && drawerDetail.output_files.length > 0
            ? () => handleDownload(drawerArchId, drawerCaseId)
            : undefined
          }
        />
      )}
    </>
  )
}

function PromptSnapshotView({ snapshot }: { snapshot: RunSnapshot }) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const prompts = Object.entries(snapshot.prompt_contents)

  return (
    <div className="space-y-2">
      <div className="text-xs text-gray-500 font-mono">
        snapshot: {snapshot.snapshot_hash.slice(0, 16)}...
      </div>
      {prompts.map(([name, content]) => {
        const hash = snapshot.prompt_hashes[name] ?? ''
        const isOpen = expanded === name
        return (
          <div key={name} className="border border-gray-700 rounded-lg overflow-hidden">
            <button
              onClick={() => setExpanded(isOpen ? null : name)}
              className="w-full text-left px-3 py-2 flex items-center justify-between hover:bg-gray-800 transition-colors"
            >
              <div className="flex items-center gap-2">
                <PhaseTag phase={name.replace('phase_', '').toUpperCase()} />
                <span className="text-sm text-gray-300">{name}</span>
                <span className="text-xs text-gray-600 font-mono">{hash.slice(0, 12)}...</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">{content.length} chars</span>
                <span className="text-xs text-gray-600">{isOpen ? '▼' : '▶'}</span>
              </div>
            </button>
            {isOpen && (
              <pre className="px-3 py-2 bg-gray-950 text-xs text-gray-400 overflow-x-auto whitespace-pre-wrap border-t border-gray-700 max-h-64 overflow-y-auto">
                {content}
              </pre>
            )}
          </div>
        )
      })}

      {Object.keys(snapshot.architecture_configs).length > 0 && (
        <div className="border border-gray-700 rounded-lg overflow-hidden">
          <div className="px-3 py-2 text-xs text-gray-500">
            Architecture Configs: {Object.keys(snapshot.architecture_configs).join(', ')}
          </div>
        </div>
      )}
    </div>
  )
}

function RunComparisonView({
  comparison,
  diff,
}: {
  comparison: RunComparisonResult
  diff: SnapshotDiff | null
}) {
  return (
    <div className="space-y-3">
      {/* Prompt/Config diff */}
      {diff && (
        <div className="space-y-1">
          {diff.is_identical ? (
            <div className="text-xs text-gray-500">Prompts and configs are identical between runs.</div>
          ) : (
            <>
              {diff.changed_prompts.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-yellow-400">Changed prompts:</span>
                  {diff.changed_prompts.map((p) => (
                    <span key={p} className="text-xs px-1.5 py-0.5 bg-yellow-900/50 text-yellow-300 rounded font-mono">
                      {p}
                    </span>
                  ))}
                </div>
              )}
              {diff.changed_configs.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-yellow-400">Changed configs:</span>
                  {diff.changed_configs.map((c) => (
                    <span key={c} className="text-xs px-1.5 py-0.5 bg-yellow-900/50 text-yellow-300 rounded font-mono">
                      {c}
                    </span>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Regression/Fix stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-gray-800 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-red-400">{comparison.regressions.length}</div>
          <div className="text-xs text-gray-500">Regressions</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-green-400">{comparison.fixes.length}</div>
          <div className="text-xs text-gray-500">Fixes</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-gray-400">{comparison.unchanged_pass}</div>
          <div className="text-xs text-gray-500">Still Pass</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-gray-600">{comparison.unchanged_fail}</div>
          <div className="text-xs text-gray-500">Still Fail</div>
        </div>
      </div>

      {/* Regression details */}
      {comparison.regressions.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-red-400 font-medium">Regressions (pass → fail)</div>
          {comparison.regressions.map((r, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <span className="text-red-400">✕</span>
              <span className="font-mono text-gray-400">{r.architecture_id}</span>
              <span className="text-gray-600">×</span>
              <span className="font-mono text-gray-400">
                {r.test_case_id.length > 12 ? r.test_case_id.slice(0, 8) + '...' : r.test_case_id}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Fix details */}
      {comparison.fixes.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-green-400 font-medium">Fixes (fail → pass)</div>
          {comparison.fixes.map((f, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <span className="text-green-400">✓</span>
              <span className="font-mono text-gray-400">{f.architecture_id}</span>
              <span className="text-gray-600">×</span>
              <span className="font-mono text-gray-400">
                {f.test_case_id.length > 12 ? f.test_case_id.slice(0, 8) + '...' : f.test_case_id}
              </span>
            </div>
          ))}
        </div>
      )}

      {comparison.new_cases.length > 0 && (
        <div className="text-xs text-blue-400">
          {comparison.new_cases.length} new test case(s)
        </div>
      )}
    </div>
  )
}

function SummaryTable({ report, archs }: { report: EvalReport; archs: Architecture[] }) {
  const { summary, best_architecture } = report
  const archIds = Object.keys(summary)
  const archMap = Object.fromEntries(archs.map((a) => [a.id, a]))
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="text-left py-2 px-3 text-gray-400">Architecture</th>
            <th className="text-center py-2 px-3 text-gray-400">Success</th>
            <th className="text-right py-2 px-3 text-gray-400">Avg Tokens</th>
            <th className="text-right py-2 px-3 text-gray-400">Avg Cost</th>
            <th className="text-right py-2 px-3 text-gray-400">Avg Time</th>
            <th className="text-right py-2 px-3 text-gray-400">Avg Retries</th>
            <th className="text-right py-2 px-3 text-gray-400">Runs</th>
          </tr>
        </thead>
        <tbody>
          {archIds.map((archId) => {
            const row = summary[archId]
            const isBest = archId === best_architecture
            const arch = archMap[archId]
            return (
              <tr
                key={archId}
                className={`border-b border-gray-800 ${isBest ? 'bg-green-950/30' : ''}`}
              >
                <td className="py-2 px-3 max-w-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs text-gray-200">{archId}</span>
                    {isBest && (
                      <span className="text-xs text-green-400">BEST</span>
                    )}
                  </div>
                  {arch && (
                    <div className="mt-1">
                      <div className="text-xs text-gray-500">{arch.description}</div>
                      {arch.pipeline ? (
                        <div className="flex items-center gap-1 mt-1 flex-wrap">
                          {arch.pipeline.explore && <PhaseTag phase="A" />}
                          {arch.pipeline.reflect && <PhaseTag phase="B" />}
                          {arch.pipeline.decompose && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-yellow-900/50 text-yellow-300 font-mono">
                              P→[C.n→D.n]
                            </span>
                          )}
                          {!arch.pipeline.decompose && (
                            <>
                              <PhaseTag phase="C" />
                              <PhaseTag phase="D" />
                            </>
                          )}
                          {arch.pipeline.eval_debug && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-pink-900/50 text-pink-300 font-mono">
                              F{arch.pipeline.eval_retry_strategy !== 'none' ? `↺${arch.pipeline.eval_retry_strategy}` : ''}
                            </span>
                          )}
                          {arch.pipeline.llm_eval_debug && (
                            <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-900/50 text-purple-300 font-mono">
                              G
                            </span>
                          )}
                          <span className="text-xs text-gray-600 ml-1">{arch.model}</span>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1.5 mt-1">
                          {arch.phases.map((p) => (
                            <PhaseTag key={p} phase={p} />
                          ))}
                          <span className="text-xs text-gray-600 ml-1">{arch.model}</span>
                        </div>
                      )}
                    </div>
                  )}
                </td>
                <td className="py-2 px-3">
                  <SuccessBar rate={row.success_rate} ciLow={row.ci_low} ciHigh={row.ci_high} />
                  <ErrorBreakdown breakdown={row.error_breakdown} />
                </td>
                <td className="text-right py-2 px-3 text-gray-300 font-mono text-xs">
                  {Math.round(row.avg_tokens).toLocaleString()}
                </td>
                <td className="text-right py-2 px-3 text-green-400 font-mono text-xs">
                  ${row.avg_cost_usd?.toFixed(4) ?? '—'}
                </td>
                <td className="text-right py-2 px-3 text-gray-300 font-mono text-xs">
                  {(row.avg_duration_ms / 1000).toFixed(1)}s
                </td>
                <td className="text-right py-2 px-3 text-gray-300 font-mono text-xs">
                  {row.avg_retries.toFixed(1)}
                </td>
                <td className="text-right py-2 px-3 text-gray-300 font-mono text-xs">
                  {row.total_runs}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function CreateTestCaseForm({
  onCreated,
  onClose,
}: {
  onCreated: () => void
  onClose: () => void
}) {
  const [task, setTask] = useState('')
  const [description, setDescription] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [expectedFile, setExpectedFile] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const expectedFileRef = useRef<HTMLInputElement>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!task.trim()) return
    setSubmitting(true)
    setFormError(null)
    try {
      await createTestCase(task.trim(), description.trim(), file ?? undefined, expectedFile ?? undefined)
      setTask('')
      setDescription('')
      setFile(null)
      setExpectedFile(null)
      if (fileRef.current) fileRef.current.value = ''
      if (expectedFileRef.current) expectedFileRef.current.value = ''
      onCreated()
      onClose()
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Failed to create')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 border border-gray-700 rounded-lg p-4 bg-gray-800/50">
      <div className="flex items-center justify-between">
        <div className="text-xs font-medium text-gray-400 uppercase tracking-wide">New Test Case</div>
        <button type="button" onClick={onClose} className="text-xs text-gray-600 hover:text-gray-400 transition-colors">✕</button>
      </div>

      <textarea
        placeholder="タスク指示文 (e.g. 月次品質報告書を全自動生成するコードを作ってください...)"
        value={task}
        onChange={(e) => setTask(e.target.value)}
        rows={4}
        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-600 resize-y"
      />

      <input
        type="text"
        placeholder="Description (optional, short label for this test case)"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-600"
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {/* Input Excel */}
        <div className="space-y-1">
          <div className="text-xs text-gray-500">Input Excel (processing target)</div>
          <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-400 hover:text-gray-200 transition-colors">
            <input
              ref={fileRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="hidden"
            />
            <span className="px-3 py-1.5 bg-gray-700 rounded-lg text-xs w-full text-center">
              {file ? file.name : 'Upload Input File (.xlsx/.csv)'}
            </span>
          </label>
          {file && (
            <button
              type="button"
              onClick={() => { setFile(null); if (fileRef.current) fileRef.current.value = '' }}
              className="text-xs text-red-400 hover:text-red-300"
            >
              Clear
            </button>
          )}
        </div>

        {/* Expected Excel */}
        <div className="space-y-1">
          <div className="text-xs text-gray-500">Expected Output Excel (correct answer)</div>
          <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-400 hover:text-gray-200 transition-colors">
            <input
              ref={expectedFileRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={(e) => setExpectedFile(e.target.files?.[0] ?? null)}
              className="hidden"
            />
            <span className="px-3 py-1.5 bg-green-900/50 border border-green-800/50 rounded-lg text-xs w-full text-center">
              {expectedFile ? expectedFile.name : 'Upload Expected Output (.xlsx/.csv)'}
            </span>
          </label>
          {expectedFile && (
            <button
              type="button"
              onClick={() => { setExpectedFile(null); if (expectedFileRef.current) expectedFileRef.current.value = '' }}
              className="text-xs text-red-400 hover:text-red-300"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">

        <div className="flex-1" />

        <button
          type="submit"
          disabled={!task.trim() || submitting}
          className="px-4 py-1.5 bg-green-700 hover:bg-green-600 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg text-xs font-medium transition-colors"
        >
          {submitting ? 'Creating...' : 'Add Test Case'}
        </button>
      </div>

      {formError && (
        <div className="text-xs text-red-400">{formError}</div>
      )}
    </form>
  )
}

// ---------------------------------------------------------------------------
// Category grouping helpers
// ---------------------------------------------------------------------------

type ArchCategory = 'Baseline' | 'Planner' | 'Mini' | 'Other'

function getArchCategory(id: string): ArchCategory {
  const lower = id.toLowerCase()
  if (lower.includes('mini') || lower.startsWith('v8') || lower.startsWith('v9')) return 'Mini'
  if (lower.includes('planner') || lower.startsWith('v4') || lower.startsWith('v5') || lower.startsWith('v7')) return 'Planner'
  if (lower.startsWith('v1') || lower.startsWith('v2') || lower.startsWith('v3') || lower.startsWith('v6')) return 'Baseline'
  return 'Other'
}

const CATEGORY_ORDER: readonly ArchCategory[] = ['Baseline', 'Planner', 'Mini', 'Other'] as const

function groupArchitectures(archs: readonly Architecture[]): Array<{ category: ArchCategory; items: Architecture[] }> {
  const grouped = new Map<ArchCategory, Architecture[]>()
  for (const cat of CATEGORY_ORDER) {
    grouped.set(cat, [])
  }
  for (const a of archs) {
    const cat = getArchCategory(a.id)
    grouped.get(cat)!.push(a)
  }
  return CATEGORY_ORDER
    .filter((cat) => (grouped.get(cat)?.length ?? 0) > 0)
    .map((cat) => ({ category: cat, items: grouped.get(cat)! }))
}

// ---------------------------------------------------------------------------
// Phase dot indicator for table rows
// ---------------------------------------------------------------------------

function PhaseDot({ active, color }: { active: boolean; color: string }) {
  if (!active) return <span className="inline-block w-2.5 h-2.5" />
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${color}`} />
}

// ---------------------------------------------------------------------------
// Architecture table with category grouping
// ---------------------------------------------------------------------------

interface ArchitectureTableProps {
  archs: Architecture[]
  selectedArchs: Set<string>
  toggleArch: (id: string) => void
  detailArchId: string | null
  setDetailArchId: (id: string | null) => void
}

function ArchitectureTable({ archs, selectedArchs, toggleArch, detailArchId, setDetailArchId }: ArchitectureTableProps) {
  const [collapsedCategories, setCollapsedCategories] = useState<Set<ArchCategory>>(new Set())

  const toggleCategory = (cat: ArchCategory) => {
    setCollapsedCategories((prev) => {
      const next = new Set(prev)
      if (next.has(cat)) next.delete(cat)
      else next.add(cat)
      return next
    })
  }

  const groups = groupArchitectures(archs)

  const getFStrategy = (a: Architecture): string => {
    if (!a.pipeline) return a.phases.includes('F') ? 'on' : '-'
    if (!a.pipeline.eval_debug) return '-'
    if (a.pipeline.eval_retry_strategy === 'none') return 'none'
    return a.pipeline.eval_retry_strategy
  }

  const hasPhase = (a: Architecture, phase: string): boolean => {
    if (!a.pipeline) return a.phases.includes(phase)
    switch (phase) {
      case 'A': return a.pipeline.explore
      case 'B': return a.pipeline.reflect
      case 'P': return a.pipeline.decompose
      case 'C': return true
      case 'D': return true
      case 'F': return a.pipeline.eval_debug
      case 'G': return (a.pipeline as Record<string, unknown>).llm_eval_debug === true
      default: return false
    }
  }

  const getRetryLimit = (a: Architecture): number => {
    return a.pipeline?.debug_retry_limit ?? a.debug_retry_limit
  }

  const PHASE_DOT_COLORS: Record<string, string> = {
    A: 'bg-blue-400',
    B: 'bg-purple-400',
    P: 'bg-yellow-400',
    C: 'bg-green-400',
    D: 'bg-yellow-400',
    F: 'bg-pink-400',
    G: 'bg-violet-400',
  }

  const TABLE_PHASES = ['A', 'B', 'P', 'C', 'D', 'G'] as const

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 z-10 bg-gray-900">
          <tr className="border-b border-gray-700">
            <th className="text-left py-2 px-2 text-gray-500 text-xs w-8" />
            <th className="text-left py-2 px-2 text-gray-500 text-xs">ID</th>
            <th className="text-left py-2 px-2 text-gray-500 text-xs">Description</th>
            <th className="text-left py-2 px-2 text-gray-500 text-xs">Model</th>
            {TABLE_PHASES.map((p) => (
              <th key={p} className="text-center py-2 px-1 text-gray-500 text-xs w-8">{p}</th>
            ))}
            <th className="text-center py-2 px-2 text-gray-500 text-xs">F strategy</th>
            <th className="text-center py-2 px-2 text-gray-500 text-xs">Retry</th>
            <th className="text-center py-2 px-1 text-gray-500 text-xs w-12" />
          </tr>
        </thead>
        <tbody>
          {groups.map(({ category, items }) => {
            const isCollapsed = collapsedCategories.has(category)
            return (
              <ArchCategoryGroup
                key={category}
                category={category}
                items={items}
                isCollapsed={isCollapsed}
                onToggleCategory={() => toggleCategory(category)}
                selectedArchs={selectedArchs}
                toggleArch={toggleArch}
                detailArchId={detailArchId}
                setDetailArchId={setDetailArchId}
                hasPhase={hasPhase}
                getFStrategy={getFStrategy}
                getRetryLimit={getRetryLimit}
                phaseDotColors={PHASE_DOT_COLORS}
                tablePhases={TABLE_PHASES}
              />
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

interface ArchCategoryGroupProps {
  category: ArchCategory
  items: Architecture[]
  isCollapsed: boolean
  onToggleCategory: () => void
  selectedArchs: Set<string>
  toggleArch: (id: string) => void
  detailArchId: string | null
  setDetailArchId: (id: string | null) => void
  hasPhase: (a: Architecture, phase: string) => boolean
  getFStrategy: (a: Architecture) => string
  getRetryLimit: (a: Architecture) => number
  phaseDotColors: Record<string, string>
  tablePhases: readonly string[]
}

function ArchCategoryGroup({
  category,
  items,
  isCollapsed,
  onToggleCategory,
  selectedArchs,
  toggleArch,
  detailArchId,
  setDetailArchId,
  hasPhase,
  getFStrategy,
  getRetryLimit,
  phaseDotColors,
  tablePhases,
}: ArchCategoryGroupProps) {
  // Total columns: checkbox + ID + Desc + Model + 6 phases + F strategy + Retry + Detail = 13
  const colSpan = 13

  return (
    <>
      {/* Category header */}
      <tr
        className="border-b border-gray-700 bg-gray-800/60 cursor-pointer hover:bg-gray-800 transition-colors"
        onClick={onToggleCategory}
      >
        <td colSpan={colSpan} className="py-1.5 px-2">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">{isCollapsed ? '▶' : '▼'}</span>
            <span className="text-xs font-medium text-gray-300">{category}</span>
            <span className="text-xs text-gray-600">({items.length})</span>
          </div>
        </td>
      </tr>

      {/* Architecture rows */}
      {!isCollapsed && items.map((a) => {
        const isSelected = selectedArchs.has(a.id) || selectedArchs.size === 0
        const fStrategy = getFStrategy(a)
        return (
          <ArchTableRow
            key={a.id}
            arch={a}
            isSelected={isSelected}
            toggleArch={toggleArch}
            detailArchId={detailArchId}
            setDetailArchId={setDetailArchId}
            hasPhase={hasPhase}
            fStrategy={fStrategy}
            retryLimit={getRetryLimit(a)}
            phaseDotColors={phaseDotColors}
            tablePhases={tablePhases}
            colSpan={colSpan}
          />
        )
      })}
    </>
  )
}

interface ArchTableRowProps {
  arch: Architecture
  isSelected: boolean
  toggleArch: (id: string) => void
  detailArchId: string | null
  setDetailArchId: (id: string | null) => void
  hasPhase: (a: Architecture, phase: string) => boolean
  fStrategy: string
  retryLimit: number
  phaseDotColors: Record<string, string>
  tablePhases: readonly string[]
  colSpan: number
}

function ArchTableRow({
  arch,
  isSelected,
  toggleArch,
  detailArchId,
  setDetailArchId,
  hasPhase,
  fStrategy,
  retryLimit,
  phaseDotColors,
  tablePhases,
  colSpan,
}: ArchTableRowProps) {
  const isDetailOpen = detailArchId === arch.id
  return (
    <>
      <tr
        className={`border-b border-gray-800 transition-colors cursor-pointer ${
          isSelected
            ? 'bg-blue-950/30 border-l-2 border-l-blue-600'
            : 'opacity-50 hover:opacity-70'
        }`}
        onClick={() => toggleArch(arch.id)}
      >
        <td className="py-2 px-2 text-center">
          <span className={`inline-block w-3 h-3 rounded border ${
            isSelected ? 'bg-blue-600 border-blue-500' : 'border-gray-600'
          }`} />
        </td>
        <td className="py-2 px-2 font-mono text-xs text-gray-200 whitespace-nowrap">{arch.id}</td>
        <td className="py-2 px-2 text-xs text-gray-400 max-w-[200px] truncate">{arch.description}</td>
        <td className="py-2 px-2 text-xs text-gray-500 font-mono whitespace-nowrap">{arch.model}</td>
        {tablePhases.map((p) => (
          <td key={p} className="py-2 px-1 text-center">
            <PhaseDot active={hasPhase(arch, p)} color={phaseDotColors[p] ?? 'bg-gray-400'} />
          </td>
        ))}
        <td className="py-2 px-2 text-center text-xs font-mono">
          {fStrategy === '-' ? (
            <span className="text-gray-700">-</span>
          ) : (
            <span className="text-pink-400">{fStrategy}</span>
          )}
        </td>
        <td className="py-2 px-2 text-center text-xs font-mono text-gray-400">{retryLimit}</td>
        <td className="py-2 px-1 text-center" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => setDetailArchId(isDetailOpen ? null : arch.id)}
            className="text-xs text-gray-500 hover:text-gray-300 px-1 py-0.5 transition-colors"
            title="Show architecture detail"
          >
            {isDetailOpen ? '▼' : '▶'}
          </button>
        </td>
      </tr>
      {isDetailOpen && (
        <tr className="border-b border-gray-800">
          <td colSpan={colSpan} className="px-2 py-2">
            <ArchDetailPanel arch={arch} />
          </td>
        </tr>
      )}
    </>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function EvalDashboard() {
  const [archs, setArchs] = useState<Architecture[]>([])
  const [cases, setCases] = useState<EvalTestCase[]>([])
  const [pastRuns, setPastRuns] = useState<PastRun[]>([])

  const [selectedArchs, setSelectedArchs] = useState<Set<string>>(new Set())
  const [selectedCases, setSelectedCases] = useState<Set<string>>(new Set())
  const [detailArchId, setDetailArchId] = useState<string | null>(null)

  const [runStatus, setRunStatus] = useState<RunStatus | null>(null)
  const [viewingReport, setViewingReport] = useState<EvalReport | null>(null)
  const [viewingRunId, setViewingRunId] = useState<string | null>(null)
  const [snapshot, setSnapshot] = useState<RunSnapshot | null>(null)
  const [comparisonResult, setComparisonResult] = useState<RunComparisonResult | null>(null)
  const [snapshotDiff, setSnapshotDiff] = useState<SnapshotDiff | null>(null)
  const [compareBaselineId, setCompareBaselineId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showAddCase, setShowAddCase] = useState(false)

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const reloadCases = useCallback(() => {
    getTestCases().then(setCases).catch(() => {})
  }, [])

  // Load initial data
  useEffect(() => {
    Promise.all([getArchitectures(), getTestCases(), listRuns()])
      .then(([a, c, r]) => {
        setArchs(a)
        setCases(c)
        setPastRuns(r)
      })
      .catch((e) => setError(e.message))
  }, [])

  // Polling for run status
  const startPolling = useCallback((runId: string) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const status = await getRunStatus(runId)
        setRunStatus(status)
        if (status.status !== 'running') {
          if (pollRef.current) clearInterval(pollRef.current)
          pollRef.current = null
          if (status.report) {
            setViewingReport(status.report as EvalReport)
            setViewingRunId(status.run_id)
            getRunSnapshot(status.run_id).then(setSnapshot).catch(() => setSnapshot(null))
          }
          listRuns().then(setPastRuns).catch(() => {})
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current)
        pollRef.current = null
      }
    }, 2000)
  }, [])

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const handleStop = async () => {
    if (!runStatus) return
    try {
      await stopRun(runStatus.run_id)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to stop')
    }
  }

  const handleRun = async () => {
    setLoading(true)
    setError(null)
    setViewingReport(null)
    try {
      const archIds = selectedArchs.size > 0 ? [...selectedArchs] : undefined
      const caseIds = selectedCases.size > 0 ? [...selectedCases] : undefined
      const status = await startRun(archIds, caseIds)
      setRunStatus(status)
      startPolling(status.run_id)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const handleViewPastRun = async (runId: string) => {
    try {
      const status = await getRunStatus(runId)
      if (status.report) setViewingReport(status.report as EvalReport)
      setViewingRunId(runId)
      setComparisonResult(null)
      setSnapshotDiff(null)
      setCompareBaselineId(null)
      // Load snapshot (may not exist for old runs)
      try {
        const snap = await getRunSnapshot(runId)
        setSnapshot(snap)
      } catch {
        setSnapshot(null)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load run')
    }
  }

  const handleCompareRun = async (baselineId: string) => {
    if (!viewingRunId) return
    setCompareBaselineId(baselineId)
    try {
      const [comp, diff] = await Promise.all([
        compareRuns(viewingRunId, baselineId),
        diffRuns(viewingRunId, baselineId).catch(() => null),
      ])
      setComparisonResult(comp)
      setSnapshotDiff(diff)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to compare')
    }
  }

  const toggleArch = (id: string) => {
    setSelectedArchs((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleDeleteCase = async (id: string) => {
    try {
      await deleteTestCase(id)
      setSelectedCases((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
      reloadCases()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to delete')
    }
  }

  const toggleCase = (id: string) => {
    setSelectedCases((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const isRunning = runStatus?.status === 'running'

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
      <h2 className="text-xl font-semibold text-white">Agent Architecture Eval</h2>

      {error && (
        <div className="bg-red-950 border border-red-800 text-red-300 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {/* Architecture selection */}
      <div className="bg-gray-900 rounded-lg p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-300">
          Architectures
          <span className="text-gray-500 ml-2 font-normal">
            ({selectedArchs.size === 0 ? 'all' : selectedArchs.size} selected)
          </span>
        </h3>
        <ArchitectureTable
          archs={archs}
          selectedArchs={selectedArchs}
          toggleArch={toggleArch}
          detailArchId={detailArchId}
          setDetailArchId={setDetailArchId}
        />
      </div>

      {/* Test case selection */}
      <div className="bg-gray-900 rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-300">
            Test Cases
            <span className="text-gray-500 ml-2 font-normal">
              ({selectedCases.size === 0 ? 'all' : selectedCases.size} selected)
            </span>
          </h3>
          <button
            type="button"
            onClick={() => setShowAddCase((v) => !v)}
            className="text-xs px-2.5 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg transition-colors"
          >
            {showAddCase ? '✕ Cancel' : '+ Add'}
          </button>
        </div>

        {showAddCase && (
          <CreateTestCaseForm onCreated={reloadCases} onClose={() => setShowAddCase(false)} />
        )}

        {cases.length === 0 ? (
          <div className="text-xs text-gray-600 py-2">No test cases yet. Click "+ Add" to create one.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-700">
                  <th className="text-left py-1.5 px-2 text-gray-500 text-xs w-8" />
                  <th className="text-left py-1.5 px-2 text-gray-500 text-xs">Label</th>
                  <th className="text-left py-1.5 px-2 text-gray-500 text-xs">Task</th>
                  <th className="text-center py-1.5 px-2 text-gray-500 text-xs">Input</th>
                  <th className="text-center py-1.5 px-2 text-gray-500 text-xs">Expected</th>
                  <th className="text-center py-1.5 px-1 text-gray-500 text-xs w-12" />
                </tr>
              </thead>
              <tbody>
                {cases.map((c) => {
                  const isSelected = selectedCases.has(c.id) || selectedCases.size === 0
                  const label = c.description || c.id.slice(0, 8) + '...'
                  const taskPreview = c.task.length > 60 ? c.task.slice(0, 60) + '…' : c.task
                  return (
                    <tr
                      key={c.id}
                      className={`border-b border-gray-800 transition-colors cursor-pointer ${
                        isSelected ? 'bg-blue-950/20' : 'opacity-40 hover:opacity-60'
                      }`}
                      onClick={() => toggleCase(c.id)}
                      title={c.task}
                    >
                      <td className="py-2 px-2 text-center">
                        <span className={`inline-block w-3 h-3 rounded border ${
                          isSelected ? 'bg-blue-600 border-blue-500' : 'border-gray-600'
                        }`} />
                      </td>
                      <td className="py-2 px-2 text-xs font-medium text-gray-200 whitespace-nowrap max-w-[160px] truncate">
                        {label}
                      </td>
                      <td className="py-2 px-2 text-xs text-gray-400 max-w-[320px] truncate">
                        {taskPreview}
                      </td>
                      <td className="py-2 px-2 text-center">
                        {c.file_path
                          ? <span className="inline-block w-2 h-2 rounded-full bg-indigo-400" title="Input file attached" />
                          : <span className="inline-block w-2 h-2 rounded-full bg-gray-700" />}
                      </td>
                      <td className="py-2 px-2 text-center">
                        {c.expected_file_path
                          ? <span className="inline-block w-2 h-2 rounded-full bg-green-400" title="Expected file attached" />
                          : <span className="inline-block w-2 h-2 rounded-full bg-gray-700" />}
                      </td>
                      <td className="py-2 px-1 text-center" onClick={(e) => e.stopPropagation()}>
                        <button
                          onClick={() => handleDeleteCase(c.id)}
                          className="text-xs text-gray-600 hover:text-red-400 transition-colors px-1"
                          title="Delete test case"
                        >
                          ✕
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Run button + progress */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleRun}
          disabled={loading || isRunning}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg font-medium text-sm transition-colors"
        >
          {isRunning ? 'Running...' : 'Run Eval'}
        </button>

        {isRunning && (
          <button
            onClick={handleStop}
            className="px-4 py-2.5 bg-red-700 hover:bg-red-600 text-white rounded-lg font-medium text-sm transition-colors"
          >
            Stop
          </button>
        )}

        {isRunning && runStatus && (
          <div className="flex items-center gap-3">
            <div className="w-48 h-2 bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-blue-500 rounded-full transition-all duration-500"
                style={{ width: `${(runStatus.progress / runStatus.total) * 100}%` }}
              />
            </div>
            <span className="text-xs text-gray-400">
              {runStatus.progress}/{runStatus.total}
            </span>
          </div>
        )}

        <span className="text-xs text-gray-500">
          {(selectedArchs.size || archs.length)} archs x{' '}
          {(selectedCases.size || cases.length)} cases ={' '}
          {(selectedArchs.size || archs.length) * (selectedCases.size || cases.length)} runs
        </span>
      </div>

      {/* Results */}
      {viewingReport && (
        <div className="space-y-6">
          <div className="bg-gray-900 rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-medium text-gray-300">Summary</h3>
            <SummaryTable report={viewingReport} archs={archs} />
          </div>

          <div className="bg-gray-900 rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-medium text-gray-300">Phase Breakdown (Tokens)</h3>
            <PhaseBreakdown report={viewingReport} archs={archs} />
          </div>

          <div className="bg-gray-900 rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-medium text-gray-300">Comparison Matrix</h3>
            <ComparisonMatrix report={viewingReport} runId={viewingRunId ?? undefined} cases={cases} />
          </div>

          {/* Prompt Snapshot */}
          {snapshot && (
            <div className="bg-gray-900 rounded-lg p-4 space-y-3">
              <h3 className="text-sm font-medium text-gray-300">Prompt Snapshot</h3>
              <PromptSnapshotView snapshot={snapshot} />
            </div>
          )}

          {/* Run Comparison */}
          {viewingRunId && pastRuns.length > 1 && (
            <div className="bg-gray-900 rounded-lg p-4 space-y-3">
              <h3 className="text-sm font-medium text-gray-300">Compare with Previous Run</h3>
              <div className="flex flex-wrap gap-2">
                {pastRuns
                  .filter((r) => r.run_id !== viewingRunId && r.status === 'completed')
                  .map((r) => (
                    <button
                      key={r.run_id}
                      onClick={() => handleCompareRun(r.run_id)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-mono transition-colors ${
                        compareBaselineId === r.run_id
                          ? 'bg-blue-700 text-white'
                          : 'bg-gray-800 text-gray-400 hover:bg-gray-700'
                      }`}
                    >
                      {r.run_id}
                    </button>
                  ))}
              </div>
              {comparisonResult && (
                <RunComparisonView comparison={comparisonResult} diff={snapshotDiff} />
              )}
            </div>
          )}
        </div>
      )}

      {/* Past runs */}
      {pastRuns.length > 0 && (
        <div className="bg-gray-900 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-medium text-gray-300">Past Runs</h3>
          <div className="space-y-1">
            {pastRuns.map((r) => (
              <button
                key={r.run_id}
                onClick={() => handleViewPastRun(r.run_id)}
                className="w-full text-left px-3 py-2 rounded-lg hover:bg-gray-800 transition-colors flex items-center justify-between"
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono text-xs text-gray-400">{r.run_id}</span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded ${
                      r.status === 'completed'
                        ? 'bg-green-900 text-green-300'
                        : r.status === 'running'
                        ? 'bg-yellow-900 text-yellow-300'
                        : 'bg-red-900 text-red-300'
                    }`}
                  >
                    {r.status}
                  </span>
                </div>
                {r.best_architecture && (
                  <span className="text-xs text-green-400">
                    Best: {r.best_architecture}
                  </span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
