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
    <div className="flex items-center gap-3">
      <button
        onClick={onRun}
        disabled={loading || isRunning}
        className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-800 disabled:text-gray-600 text-white rounded text-xs font-medium transition-colors"
      >
        {isRunning ? 'Running...' : 'Run'}
      </button>

      {isRunning && (
        <button
          onClick={onStop}
          className="px-3 py-1.5 bg-red-900/80 hover:bg-red-800 text-red-300 rounded text-xs font-medium transition-colors"
        >
          Stop
        </button>
      )}

      {isRunning && runStatus && (
        <div className="flex items-center gap-2">
          <div className="w-32 h-1.5 bg-gray-800 rounded-full overflow-hidden">
            <div
              className="h-full bg-blue-500 rounded-full transition-all duration-500"
              style={{ width: `${(runStatus.progress / runStatus.total) * 100}%` }}
            />
          </div>
          <span className="text-[10px] text-gray-500 font-mono">
            {runStatus.progress}/{runStatus.total}
          </span>
        </div>
      )}

      <span className="text-[10px] text-gray-600 font-mono">
        {(selectedArchs.size || archs.length)}a x {(selectedCases.size || cases.length)}c = {(selectedArchs.size || archs.length) * (selectedCases.size || cases.length)}
      </span>
    </div>
  )
}
