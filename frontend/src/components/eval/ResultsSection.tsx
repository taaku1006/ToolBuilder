import type {
  Architecture,
  EvalReport,
  PastRun,
  RunComparisonResult,
  RunSnapshot,
  SnapshotDiff,
} from '../../api/eval'
import { ComparisonMatrix } from './ComparisonMatrix'
import { PhaseBreakdown } from './PhaseBreakdown'
import { PromptSnapshotView } from './PromptSnapshotView'
import { RunComparisonView } from './RunComparisonView'
import { SummaryTable } from './SummaryTable'

interface ResultsSectionProps {
  report: EvalReport
  archs: Architecture[]
  runId: string | null
  snapshot: RunSnapshot | null
  pastRuns: PastRun[]
  compareBaselineId: string | null
  comparisonResult: RunComparisonResult | null
  snapshotDiff: SnapshotDiff | null
  onCompare: (baselineId: string) => void
}

export function ResultsSection({
  report,
  archs,
  runId,
  snapshot,
  pastRuns,
  compareBaselineId,
  comparisonResult,
  snapshotDiff,
  onCompare,
}: ResultsSectionProps) {
  return (
    <div className="space-y-3">
      <div className="border border-gray-800 rounded-lg bg-gray-900/50 p-3 space-y-2">
        <h3 className="text-xs uppercase tracking-wide text-gray-500">Summary</h3>
        <SummaryTable report={report} archs={archs} />
      </div>

      <div className="border border-gray-800 rounded-lg bg-gray-900/50 p-3 space-y-2">
        <h3 className="text-xs uppercase tracking-wide text-gray-500">Phase Breakdown</h3>
        <PhaseBreakdown report={report} archs={archs} />
      </div>

      <div className="border border-gray-800 rounded-lg bg-gray-900/50 p-3 space-y-2">
        <h3 className="text-xs uppercase tracking-wide text-gray-500">Matrix</h3>
        <ComparisonMatrix report={report} runId={runId ?? undefined} />
      </div>

      {snapshot && (
        <div className="border border-gray-800 rounded-lg bg-gray-900/50 p-3 space-y-2">
          <h3 className="text-xs uppercase tracking-wide text-gray-500">Prompt Snapshot</h3>
          <PromptSnapshotView snapshot={snapshot} />
        </div>
      )}

      {runId && pastRuns.length > 1 && (
        <div className="border border-gray-800 rounded-lg bg-gray-900/50 p-3 space-y-2">
          <h3 className="text-xs uppercase tracking-wide text-gray-500">Compare</h3>
          <div className="flex flex-wrap gap-1.5">
            {pastRuns
              .filter((r) => r.run_id !== runId && r.status === 'completed')
              .map((r) => (
                <button
                  key={r.run_id}
                  onClick={() => onCompare(r.run_id)}
                  className={`px-2 py-1 rounded text-[10px] font-mono transition-colors ${
                    compareBaselineId === r.run_id
                      ? 'bg-blue-800 text-blue-200'
                      : 'bg-gray-800/80 text-gray-500 hover:bg-gray-700'
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
  )
}
