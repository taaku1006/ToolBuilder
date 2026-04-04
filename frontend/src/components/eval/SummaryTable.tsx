import type { EvalReport, Architecture } from '../../api/eval'
import { PhaseTag } from './shared/PhaseTag'
import { SuccessBar } from './shared/SuccessBar'
import { ErrorBreakdown } from './ErrorBreakdown'

interface SummaryTableProps {
  report: EvalReport
  archs: Architecture[]
}

export function SummaryTable({ report, archs }: SummaryTableProps) {
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
                      <div className="flex items-center gap-1 mt-1 flex-wrap">
                        <PhaseTag phase="U" />
                        <PhaseTag phase="G" />
                        <PhaseTag phase="VF" />
                        <PhaseTag phase="L" />
                        <span className="text-xs text-gray-600 ml-1">{arch.model}</span>
                      </div>
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
