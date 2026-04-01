import type { Architecture, EvalTestCase, RunStatus } from '../../api/eval'

interface RunControlsProps {
  isRunning: boolean
  loading: boolean
  runStatus: RunStatus | null
  archs: Architecture[]
  cases: EvalTestCase[]
  selectedArchs: Set<string>
  selectedCases: Set<string>
  onRun: () => void
  onStop: () => void
}

export function RunControls({
  isRunning,
  loading,
  runStatus,
  archs,
  cases,
  selectedArchs,
  selectedCases,
  onRun,
  onStop,
}: RunControlsProps) {
  return (
    <div className="flex items-center gap-4">
      <button
        onClick={onRun}
        disabled={loading || isRunning}
        className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg font-medium text-sm transition-colors"
      >
        {isRunning ? 'Running...' : 'Run Eval'}
      </button>

      {isRunning && (
        <button
          onClick={onStop}
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
  )
}
