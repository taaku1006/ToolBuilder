import { PHASE_ORDER } from '../../constants/phases'
import type { EvalReport, Architecture } from '../../api/eval'
import { PhaseTag } from './shared/PhaseTag'

interface PhaseBreakdownProps {
  report: EvalReport
  archs: Architecture[]
}

export function PhaseBreakdown({ report, archs }: PhaseBreakdownProps) {
  const { summary } = report
  const archIds = Object.keys(summary)
  const archMap = Object.fromEntries(archs.map((a) => [a.id, a]))
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
            void arch?.model // referenced for potential future display
            const totalPt = Object.values(pt).reduce((a, b) => a + b, 0)

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

