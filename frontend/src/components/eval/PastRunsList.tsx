import type { PastRun } from '../../api/eval'

interface PastRunsListProps {
  pastRuns: PastRun[]
  onViewRun: (runId: string) => void
}

export function PastRunsList({ pastRuns, onViewRun }: PastRunsListProps) {
  return (
    <div className="bg-gray-900 rounded-lg p-4 space-y-3">
      <h3 className="text-sm font-medium text-gray-300">Past Runs</h3>
      <div className="space-y-1">
        {pastRuns.map((r) => (
          <button
            key={r.run_id}
            onClick={() => onViewRun(r.run_id)}
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
  )
}
