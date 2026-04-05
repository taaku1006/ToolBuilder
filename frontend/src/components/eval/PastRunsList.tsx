import type { PastRun } from '../../api/eval'

interface PastRunsListProps {
  pastRuns: PastRun[]
  onViewRun: (runId: string) => void
}

export function PastRunsList({ pastRuns, onViewRun }: PastRunsListProps) {
  return (
    <div className="border border-gray-800 rounded-lg bg-gray-900/50 p-3 space-y-2">
      <h3 className="text-xs uppercase tracking-wide text-gray-500">Past Runs</h3>
      <div className="space-y-0.5">
        {pastRuns.map((r) => (
          <button
            key={r.run_id}
            onClick={() => onViewRun(r.run_id)}
            className="w-full text-left px-2 py-1.5 rounded hover:bg-gray-800/50 transition-colors flex items-center justify-between"
          >
            <div className="flex items-center gap-2">
              <span
                className={`inline-block w-1.5 h-1.5 rounded-full ${
                  r.status === 'completed'
                    ? 'bg-green-400'
                    : r.status === 'running'
                    ? 'bg-yellow-400 animate-pulse'
                    : 'bg-red-400'
                }`}
              />
              <span className="font-mono text-[10px] text-gray-400">{r.run_id}</span>
            </div>
            {r.best_architecture && (
              <span className="text-[10px] text-gray-600 font-mono">
                {r.best_architecture}
              </span>
            )}
          </button>
        ))}
      </div>
    </div>
  )
}
