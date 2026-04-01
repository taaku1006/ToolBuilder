import { useState } from 'react'
import type { EvalReport, ResultDetail } from '../../api/eval'
import { getResultFiles } from '../../api/eval'

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

function DetailPopup({ detail, onClose }: { detail: ResultDetail; onClose: () => void }) {
  const qd = detail.quality_details
  const ld = detail.llm_eval_details
  return (
    <div className="absolute z-50 top-full left-1/2 -translate-x-1/2 mt-1 w-80 bg-gray-800 border border-gray-600 rounded-lg p-3 shadow-xl text-left">
      <button onClick={onClose} className="absolute top-1 right-2 text-gray-500 hover:text-gray-300 text-xs">x</button>
      <div className="text-xs space-y-2">
        {qd && (
          <div>
            <div className="font-semibold text-pink-300 mb-1">F: Mechanical ({Math.round((detail.quality_score ?? 0) * 100)}%)</div>
            {qd.missing_sheets && qd.missing_sheets.length > 0 && (
              <div className="text-red-400">Missing: {qd.missing_sheets.join(', ')}</div>
            )}
            {qd.extra_sheets && qd.extra_sheets.length > 0 && (
              <div className="text-yellow-400">Extra: {qd.extra_sheets.join(', ')}</div>
            )}
            {qd.error && <div className="text-red-400">Error: {qd.error}</div>}
          </div>
        )}
        {ld && (
          <div>
            <div className="font-semibold text-purple-300 mb-1">G: LLM Eval ({detail.llm_eval_score?.toFixed(1)}/10)</div>
            <div className="grid grid-cols-3 gap-1 text-[10px]">
              <span>Semantic: {ld.semantic_correctness ?? '—'}/10</span>
              <span>Integrity: {ld.data_integrity ?? '—'}/10</span>
              <span>Complete: {ld.completeness ?? '—'}/10</span>
            </div>
            {ld.reasoning && (
              <div className="mt-1 text-gray-400 leading-tight max-h-24 overflow-y-auto">{ld.reasoning}</div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

interface ComparisonMatrixProps {
  report: EvalReport
  runId?: string
}

export function ComparisonMatrix({ report, runId }: ComparisonMatrixProps) {
  const { comparison_matrix, result_details, architecture_ids, test_case_ids } = report
  const [expandedCell, setExpandedCell] = useState<string | null>(null)

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

  return (
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
            <tr key={caseId} className="border-b border-gray-800">
              <td className="py-2 px-3 text-gray-300 font-mono text-xs">{caseId}</td>
              {architecture_ids.map((archId) => {
                const ok = comparison_matrix[caseId]?.[archId]
                const detail = result_details?.[caseId]?.[archId]
                const cellKey = `${caseId}__${archId}`
                const isExpanded = expandedCell === cellKey
                const qs = detail?.quality_score
                const ls = detail?.llm_eval_score
                const hasFiles = detail?.output_files && detail.output_files.length > 0

                return (
                  <td key={archId} className={`text-center py-2 px-2 relative ${qs != null ? scoreBg(qs, 1.0) : ''}`}>
                    <div className="flex flex-col items-center gap-0.5">
                      <span className={ok ? 'text-green-400 font-bold' : 'text-red-400 font-bold'}>
                        {ok ? 'OK' : 'NG'}
                      </span>
                      {qs != null && (
                        <span className={`text-[10px] font-mono ${scoreColor(qs, 1.0)}`}>
                          F:{Math.round(qs * 100)}%
                        </span>
                      )}
                      {ls != null && (
                        <span className={`text-[10px] font-mono ${scoreColor(ls, 10)}`}>
                          G:{ls.toFixed(1)}
                        </span>
                      )}
                      <div className="flex gap-1 mt-0.5">
                        {detail && (
                          <button
                            onClick={() => setExpandedCell(isExpanded ? null : cellKey)}
                            className="text-[9px] px-1 py-0.5 rounded bg-gray-700 hover:bg-gray-600 text-gray-300"
                            title="Show details"
                          >
                            Details
                          </button>
                        )}
                        {hasFiles && (
                          <button
                            onClick={() => handleDownload(archId, caseId)}
                            className="text-[9px] px-1 py-0.5 rounded bg-blue-900 hover:bg-blue-800 text-blue-300"
                            title="Download output files"
                          >
                            DL
                          </button>
                        )}
                      </div>
                    </div>
                    {isExpanded && detail && (
                      <DetailPopup detail={detail} onClose={() => setExpandedCell(null)} />
                    )}
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
