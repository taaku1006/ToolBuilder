import type { RunComparisonResult, SnapshotDiff } from '../../api/eval'

interface RunComparisonViewProps {
  comparison: RunComparisonResult
  diff: SnapshotDiff | null
}

export function RunComparisonView({ comparison, diff }: RunComparisonViewProps) {
  return (
    <div className="space-y-3">
      {diff && (
        <div className="space-y-1">
          {diff.is_identical ? (
            <div className="text-xs text-gray-500">Prompts and configs are identical between runs.</div>
          ) : (
            <>
              {diff.changed_prompts.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-yellow-400">Changed prompts:</span>
                  {diff.changed_prompts.map((p) => (
                    <span key={p} className="text-xs px-1.5 py-0.5 bg-yellow-900/50 text-yellow-300 rounded font-mono">
                      {p}
                    </span>
                  ))}
                </div>
              )}
              {diff.changed_configs.length > 0 && (
                <div className="flex items-center gap-2">
                  <span className="text-xs text-yellow-400">Changed configs:</span>
                  {diff.changed_configs.map((c) => (
                    <span key={c} className="text-xs px-1.5 py-0.5 bg-yellow-900/50 text-yellow-300 rounded font-mono">
                      {c}
                    </span>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-gray-800 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-red-400">{comparison.regressions.length}</div>
          <div className="text-xs text-gray-500">Regressions</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-green-400">{comparison.fixes.length}</div>
          <div className="text-xs text-gray-500">Fixes</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-gray-400">{comparison.unchanged_pass}</div>
          <div className="text-xs text-gray-500">Still Pass</div>
        </div>
        <div className="bg-gray-800 rounded-lg p-3 text-center">
          <div className="text-2xl font-bold text-gray-600">{comparison.unchanged_fail}</div>
          <div className="text-xs text-gray-500">Still Fail</div>
        </div>
      </div>

      {comparison.regressions.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-red-400 font-medium">Regressions (pass → fail)</div>
          {comparison.regressions.map((r, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <span className="text-red-400">✕</span>
              <span className="font-mono text-gray-400">{r.architecture_id}</span>
              <span className="text-gray-600">×</span>
              <span className="font-mono text-gray-400">
                {r.test_case_id.length > 12 ? r.test_case_id.slice(0, 8) + '...' : r.test_case_id}
              </span>
            </div>
          ))}
        </div>
      )}

      {comparison.fixes.length > 0 && (
        <div className="space-y-1">
          <div className="text-xs text-green-400 font-medium">Fixes (fail → pass)</div>
          {comparison.fixes.map((f, i) => (
            <div key={i} className="flex items-center gap-2 text-xs">
              <span className="text-green-400">✓</span>
              <span className="font-mono text-gray-400">{f.architecture_id}</span>
              <span className="text-gray-600">×</span>
              <span className="font-mono text-gray-400">
                {f.test_case_id.length > 12 ? f.test_case_id.slice(0, 8) + '...' : f.test_case_id}
              </span>
            </div>
          ))}
        </div>
      )}

      {comparison.new_cases.length > 0 && (
        <div className="text-xs text-blue-400">
          {comparison.new_cases.length} new test case(s)
        </div>
      )}
    </div>
  )
}
