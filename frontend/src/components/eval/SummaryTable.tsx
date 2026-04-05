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
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-gray-800">
            <th className="text-left py-1.5 px-2 text-gray-500 font-normal uppercase tracking-wide text-[10px]">Architecture</th>
            <th className="text-center py-1.5 px-2 text-gray-500 font-normal uppercase tracking-wide text-[10px]">Success</th>
            <th className="text-right py-1.5 px-2 text-gray-500 font-normal uppercase tracking-wide text-[10px]">Tokens</th>
            <th className="text-right py-1.5 px-2 text-gray-500 font-normal uppercase tracking-wide text-[10px]">Cost</th>
            <th className="text-right py-1.5 px-2 text-gray-500 font-normal uppercase tracking-wide text-[10px]">Time</th>
            <th className="text-right py-1.5 px-2 text-gray-500 font-normal uppercase tracking-wide text-[10px]">Retries</th>
            <th className="text-right py-1.5 px-2 text-gray-500 font-normal uppercase tracking-wide text-[10px]">Runs</th>
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
                className={`border-b border-gray-800/50 ${isBest ? 'bg-green-950/20' : ''}`}
              >
                <td className="py-1.5 px-2 max-w-xs">
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono text-gray-200">{archId}</span>
                    {isBest && (
                      <span className="inline-block w-1.5 h-1.5 rounded-full bg-green-400" title="Best" />
                    )}
                  </div>
                  {arch && (
                    <div className="mt-0.5 flex items-center gap-1.5">
                      <span className="text-[10px] text-gray-600 font-mono">{arch.model}</span>
                    </div>
                  )}
                </td>
                <td className="py-1.5 px-2">
                  <SuccessBar rate={row.success_rate} ciLow={row.ci_low} ciHigh={row.ci_high} />
                  <ErrorBreakdown breakdown={row.error_breakdown} />
                </td>
                <td className="text-right py-1.5 px-2 text-gray-400 font-mono">
                  {Math.round(row.avg_tokens).toLocaleString()}
                </td>
                <td className="text-right py-1.5 px-2 text-green-400/80 font-mono">
                  ${row.avg_cost_usd?.toFixed(4) ?? '—'}
                </td>
                <td className="text-right py-1.5 px-2 text-gray-400 font-mono">
                  {(row.avg_duration_ms / 1000).toFixed(1)}s
                </td>
                <td className="text-right py-1.5 px-2 text-gray-400 font-mono">
                  {row.avg_retries.toFixed(1)}
                </td>
                <td className="text-right py-1.5 px-2 text-gray-400 font-mono">
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
