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
    <div className="space-y-6">
      <div className="bg-gray-900 rounded-lg p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-300">Summary</h3>
        <SummaryTable report={report} archs={archs} />
      </div>

      <div className="bg-gray-900 rounded-lg p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-300">Phase Breakdown (Tokens)</h3>
        <PhaseBreakdown report={report} archs={archs} />
      </div>

      <div className="bg-gray-900 rounded-lg p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-300">Comparison Matrix</h3>
        <ComparisonMatrix report={report} runId={runId ?? undefined} />
      </div>

      {snapshot && (
        <div className="bg-gray-900 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-medium text-gray-300">Prompt Snapshot</h3>
          <PromptSnapshotView snapshot={snapshot} />
        </div>
      )}

      {runId && pastRuns.length > 1 && (
        <div className="bg-gray-900 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-medium text-gray-300">Compare with Previous Run</h3>
          <div className="flex flex-wrap gap-2">
            {pastRuns
              .filter((r) => r.run_id !== runId && r.status === 'completed')
              .map((r) => (
                <button
                  key={r.run_id}
                  onClick={() => onCompare(r.run_id)}
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
  )
}
