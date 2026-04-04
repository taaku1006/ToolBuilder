import { useState } from 'react'
import type { EvalReport, ResultDetail } from '../../api/eval'
import { getResultFiles } from '../../api/eval'
import { ResultDetailPanel } from './ResultDetailPanel'

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

interface ComparisonMatrixProps {
  report: EvalReport
  runId?: string
}

export function ComparisonMatrix({ report, runId }: ComparisonMatrixProps) {
  const { comparison_matrix, result_details, architecture_ids, test_case_ids } = report
  const [expandedCell, setExpandedCell] = useState<{ caseId: string; archId: string } | null>(null)

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

  const toggleDetail = (caseId: string, archId: string) => {
    setExpandedCell((prev) =>
      prev?.caseId === caseId && prev?.archId === archId ? null : { caseId, archId }
    )
  }

  const colSpan = architecture_ids.length + 1

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
            <>
              <tr key={caseId} className="border-b border-gray-800">
                <td className="py-2 px-3 text-gray-300 font-mono text-xs">{caseId.slice(0, 8)}</td>
                {architecture_ids.map((archId) => {
                  const ok = comparison_matrix[caseId]?.[archId]
                  const detail = result_details?.[caseId]?.[archId]
                  const qs = detail?.quality_score
                  const ls = detail?.llm_eval_score
                  const hasFiles = detail?.output_files && detail.output_files.length > 0
                  const isExpanded = expandedCell?.caseId === caseId && expandedCell?.archId === archId

                  return (
                    <td key={archId} className={`text-center py-2 px-2 ${qs != null ? scoreBg(qs, 1.0) : ''}`}>
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
                          <button
                            onClick={() => toggleDetail(caseId, archId)}
                            className={`text-[9px] px-1.5 py-0.5 rounded transition-colors ${
                              isExpanded
                                ? 'bg-blue-700 text-white'
                                : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                            }`}
                          >
                            {isExpanded ? 'Close' : 'Details'}
                          </button>
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
                    </td>
                  )
                })}
              </tr>
              {/* Expanded detail row */}
              {expandedCell?.caseId === caseId && runId && (
                <tr key={`${caseId}__detail`} className="border-b border-gray-700">
                  <td colSpan={colSpan} className="p-2">
                    <ResultDetailPanel
                      runId={runId}
                      archId={expandedCell.archId}
                      caseId={caseId}
                    />
                  </td>
                </tr>
              )}
            </>
          ))}
        </tbody>
      </table>
    </div>
  )
}
