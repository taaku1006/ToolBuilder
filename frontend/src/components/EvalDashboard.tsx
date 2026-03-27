import { useCallback, useEffect, useRef, useState } from 'react'
import {
  type Architecture,
  type EvalTestCase,
  type RunStatus,
  type PastRun,
  type EvalReport,
  getArchitectures,
  getTestCases,
  startRun,
  stopRun,
  getRunStatus,
  listRuns,
  createTestCase,
  deleteTestCase,
} from '../api/eval'

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

const PHASE_INFO: Record<string, { label: string; color: string; description: string }> = {
  A: {
    label: 'A',
    color: 'bg-blue-900 text-blue-300',
    description: 'Excel構造の探索 — シート名・カラム・データ型・統計情報を自動分析',
  },
  B: {
    label: 'B',
    color: 'bg-purple-900 text-purple-300',
    description: 'ツール必要性の内省 — カスタムツールが必要か判断し、必要なら生成・実行',
  },
  C: {
    label: 'C',
    color: 'bg-green-900 text-green-300',
    description: 'メインコード生成 — 全コンテキストからPythonコードを生成',
  },
  D: {
    label: 'D',
    color: 'bg-yellow-900 text-yellow-300',
    description: '自律デバッグ — 実行→エラー→修正→再実行を自動リトライ',
  },
  E: {
    label: 'E',
    color: 'bg-pink-900 text-pink-300',
    description: 'スキル保存提案 — 成功したコードをスキルとして保存を提案',
  },
}

function PhaseTag({ phase }: { phase: string }) {
  const info = PHASE_INFO[phase]
  return (
    <span className={`px-1.5 py-0.5 rounded text-xs font-mono ${info?.color ?? 'bg-gray-700 text-gray-300'}`}>
      {phase}
    </span>
  )
}

function ArchDetailPanel({ arch }: { arch: Architecture }) {
  const allPhases = ['A', 'B', 'C', 'D', 'E']
  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3">
      <div className="flex items-center justify-between">
        <div>
          <span className="font-mono text-sm text-white">{arch.id}</span>
          <span className="text-xs text-gray-500 ml-3">{arch.model} / temp:{arch.temperature} / retry:{arch.debug_retry_limit}</span>
        </div>
      </div>
      {arch.description && (
        <div className="text-sm text-gray-300">{arch.description}</div>
      )}
      <div className="space-y-1.5">
        <div className="text-xs text-gray-500 uppercase tracking-wide">Pipeline</div>
        <div className="flex items-center gap-1">
          {allPhases.map((p, i) => {
            const active = arch.phases.includes(p)
            const info = PHASE_INFO[p]
            return (
              <div key={p} className="flex items-center">
                {i > 0 && (
                  <span className={`mx-1 text-xs ${active ? 'text-gray-500' : 'text-gray-700'}`}>→</span>
                )}
                <span
                  className={`px-2 py-1 rounded text-xs font-mono ${
                    active
                      ? info?.color ?? 'bg-gray-700 text-gray-300'
                      : 'bg-gray-800 text-gray-600 line-through'
                  }`}
                >
                  {p}
                </span>
              </div>
            )
          })}
        </div>
      </div>
      <div className="space-y-1">
        {allPhases.map((p) => {
          const active = arch.phases.includes(p)
          const info = PHASE_INFO[p]
          if (!info) return null
          return (
            <div key={p} className={`flex items-start gap-2 text-xs ${active ? 'text-gray-300' : 'text-gray-600 line-through'}`}>
              <PhaseTag phase={p} />
              <span>{info.description}</span>
              {!active && <span className="text-gray-600 no-underline ml-1">(skip)</span>}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function SuccessBar({ rate }: { rate: number }) {
  const pct = Math.round(rate * 100)
  const color =
    pct >= 80 ? 'bg-green-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-gray-400">{pct}%</span>
    </div>
  )
}

function ComparisonMatrix({
  report,
}: {
  report: EvalReport
}) {
  const { comparison_matrix, architecture_ids, test_case_ids } = report
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-700">
            <th className="text-left py-2 px-3 text-gray-400">Test Case</th>
            {architecture_ids.map((a) => (
              <th key={a} className="text-center py-2 px-3 text-gray-400 font-mono text-xs">
                {a}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {test_case_ids.map((caseId) => (
            <tr key={caseId} className="border-b border-gray-800">
              <td className="py-2 px-3 text-gray-300 font-mono text-xs">{caseId}</td>
              {architecture_ids.map((archId) => {
                const ok = comparison_matrix[caseId]?.[archId]
                return (
                  <td key={archId} className="text-center py-2 px-3">
                    <span className={ok ? 'text-green-400' : 'text-red-400'}>
                      {ok ? 'OK' : 'NG'}
                    </span>
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function SummaryTable({ report, archs }: { report: EvalReport; archs: Architecture[] }) {
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
                      <div className="flex items-center gap-1.5 mt-1">
                        {arch.phases.map((p) => (
                          <PhaseTag key={p} phase={p} />
                        ))}
                        <span className="text-xs text-gray-600 ml-1">{arch.model}</span>
                      </div>
                    </div>
                  )}
                </td>
                <td className="py-2 px-3">
                  <SuccessBar rate={row.success_rate} />
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

function CreateTestCaseForm({
  onCreated,
}: {
  onCreated: () => void
}) {
  const [task, setTask] = useState('')
  const [description, setDescription] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!task.trim()) return
    setSubmitting(true)
    setFormError(null)
    try {
      await createTestCase(task.trim(), description.trim(), file ?? undefined)
      setTask('')
      setDescription('')
      setFile(null)
      if (fileRef.current) fileRef.current.value = ''
      onCreated()
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Failed to create')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 border border-gray-700 rounded-lg p-4 bg-gray-800/50">
      <div className="text-xs font-medium text-gray-400 uppercase tracking-wide">New Test Case</div>

      <input
        type="text"
        placeholder="Task (e.g. 売上を集計してください)"
        value={task}
        onChange={(e) => setTask(e.target.value)}
        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-600"
      />

      <input
        type="text"
        placeholder="Description (optional)"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-600"
      />

      <div className="flex items-center gap-3">
        <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-400 hover:text-gray-200 transition-colors">
          <input
            ref={fileRef}
            type="file"
            accept=".xlsx,.xls,.csv"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="hidden"
          />
          <span className="px-3 py-1.5 bg-gray-700 rounded-lg text-xs">
            {file ? file.name : 'Upload File (.xlsx/.csv)'}
          </span>
        </label>

        {file && (
          <button
            type="button"
            onClick={() => { setFile(null); if (fileRef.current) fileRef.current.value = '' }}
            className="text-xs text-red-400 hover:text-red-300"
          >
            Clear
          </button>
        )}

        <div className="flex-1" />

        <button
          type="submit"
          disabled={!task.trim() || submitting}
          className="px-4 py-1.5 bg-green-700 hover:bg-green-600 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg text-xs font-medium transition-colors"
        >
          {submitting ? 'Creating...' : 'Add Test Case'}
        </button>
      </div>

      {formError && (
        <div className="text-xs text-red-400">{formError}</div>
      )}
    </form>
  )
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function EvalDashboard() {
  const [archs, setArchs] = useState<Architecture[]>([])
  const [cases, setCases] = useState<EvalTestCase[]>([])
  const [pastRuns, setPastRuns] = useState<PastRun[]>([])

  const [selectedArchs, setSelectedArchs] = useState<Set<string>>(new Set())
  const [selectedCases, setSelectedCases] = useState<Set<string>>(new Set())
  const [detailArchId, setDetailArchId] = useState<string | null>(null)

  const [runStatus, setRunStatus] = useState<RunStatus | null>(null)
  const [viewingReport, setViewingReport] = useState<EvalReport | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const reloadCases = useCallback(() => {
    getTestCases().then(setCases).catch(() => {})
  }, [])

  // Load initial data
  useEffect(() => {
    Promise.all([getArchitectures(), getTestCases(), listRuns()])
      .then(([a, c, r]) => {
        setArchs(a)
        setCases(c)
        setPastRuns(r)
      })
      .catch((e) => setError(e.message))
  }, [])

  // Polling for run status
  const startPolling = useCallback((runId: string) => {
    if (pollRef.current) clearInterval(pollRef.current)
    pollRef.current = setInterval(async () => {
      try {
        const status = await getRunStatus(runId)
        setRunStatus(status)
        if (status.status !== 'running') {
          if (pollRef.current) clearInterval(pollRef.current)
          pollRef.current = null
          if (status.report) setViewingReport(status.report as EvalReport)
          listRuns().then(setPastRuns).catch(() => {})
        }
      } catch {
        if (pollRef.current) clearInterval(pollRef.current)
        pollRef.current = null
      }
    }, 2000)
  }, [])

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current)
    }
  }, [])

  const handleStop = async () => {
    if (!runStatus) return
    try {
      await stopRun(runStatus.run_id)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to stop')
    }
  }

  const handleRun = async () => {
    setLoading(true)
    setError(null)
    setViewingReport(null)
    try {
      const archIds = selectedArchs.size > 0 ? [...selectedArchs] : undefined
      const caseIds = selectedCases.size > 0 ? [...selectedCases] : undefined
      const status = await startRun(archIds, caseIds)
      setRunStatus(status)
      startPolling(status.run_id)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Unknown error')
    } finally {
      setLoading(false)
    }
  }

  const handleViewPastRun = async (runId: string) => {
    try {
      const status = await getRunStatus(runId)
      if (status.report) setViewingReport(status.report as EvalReport)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load run')
    }
  }

  const toggleArch = (id: string) => {
    setSelectedArchs((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const handleDeleteCase = async (id: string) => {
    try {
      await deleteTestCase(id)
      setSelectedCases((prev) => {
        const next = new Set(prev)
        next.delete(id)
        return next
      })
      reloadCases()
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to delete')
    }
  }

  const toggleCase = (id: string) => {
    setSelectedCases((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const isRunning = runStatus?.status === 'running'

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
      <h2 className="text-xl font-semibold text-white">Agent Architecture Eval</h2>

      {error && (
        <div className="bg-red-950 border border-red-800 text-red-300 rounded-lg px-4 py-3 text-sm">
          {error}
        </div>
      )}

      {/* Architecture selection */}
      <div className="bg-gray-900 rounded-lg p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-300">
          Architectures
          <span className="text-gray-500 ml-2 font-normal">
            ({selectedArchs.size === 0 ? 'all' : selectedArchs.size} selected)
          </span>
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-2">
          {archs.map((a) => (
            <div key={a.id} className="flex flex-col gap-1">
              <div
                className={`text-left p-3 rounded-lg border transition-colors cursor-pointer ${
                  selectedArchs.has(a.id) || selectedArchs.size === 0
                    ? 'border-blue-600 bg-blue-950/30'
                    : 'border-gray-700 bg-gray-800/50 opacity-50'
                }`}
              >
                <div className="flex items-center justify-between">
                  <button onClick={() => toggleArch(a.id)} className="flex-1 text-left">
                    <div className="font-mono text-xs text-gray-200">{a.id}</div>
                    <div className="text-xs text-gray-500 mt-1">{a.description}</div>
                    <div className="flex gap-1 mt-2">
                      {a.phases.map((p) => (
                        <PhaseTag key={p} phase={p} />
                      ))}
                    </div>
                    <div className="text-xs text-gray-600 mt-1">
                      {a.model} / retry:{a.debug_retry_limit}
                    </div>
                  </button>
                  <button
                    onClick={() => setDetailArchId(detailArchId === a.id ? null : a.id)}
                    className="text-xs text-gray-500 hover:text-gray-300 px-2 py-1 transition-colors"
                    title="Show architecture detail"
                  >
                    {detailArchId === a.id ? '▼' : '▶'} Detail
                  </button>
                </div>
              </div>
              {detailArchId === a.id && <ArchDetailPanel arch={a} />}
            </div>
          ))}
        </div>
      </div>

      {/* Test case selection */}
      <div className="bg-gray-900 rounded-lg p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-300">
          Test Cases
          <span className="text-gray-500 ml-2 font-normal">
            ({selectedCases.size === 0 ? 'all' : selectedCases.size} selected)
          </span>
        </h3>

        <CreateTestCaseForm onCreated={reloadCases} />

        <div className="space-y-2">
          {cases.map((c) => (
            <div
              key={c.id}
              className={`p-3 rounded-lg border transition-colors ${
                selectedCases.has(c.id) || selectedCases.size === 0
                  ? 'border-blue-600 bg-blue-950/30'
                  : 'border-gray-700 bg-gray-800/50 opacity-50'
              }`}
            >
              <div className="flex items-center gap-3">
                <button
                  onClick={() => toggleCase(c.id)}
                  className="flex-1 text-left"
                >
                  <div className="flex items-center gap-3">
                    <span className="font-mono text-xs text-gray-400">
                      {c.id.length > 12 ? c.id.slice(0, 8) + '...' : c.id}
                    </span>
                    <span className="text-sm text-gray-200">{c.task}</span>
                    {c.file_path && (
                      <span className="text-xs px-1.5 py-0.5 bg-indigo-900 text-indigo-300 rounded">
                        file
                      </span>
                    )}
                  </div>
                  {c.description && (
                    <div className="text-xs text-gray-500 mt-1">{c.description}</div>
                  )}
                </button>
                <button
                  onClick={() => handleDeleteCase(c.id)}
                  className="text-xs text-gray-600 hover:text-red-400 transition-colors px-2 py-1"
                  title="Delete test case"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Run button + progress */}
      <div className="flex items-center gap-4">
        <button
          onClick={handleRun}
          disabled={loading || isRunning}
          className="px-6 py-2.5 bg-blue-600 hover:bg-blue-500 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg font-medium text-sm transition-colors"
        >
          {isRunning ? 'Running...' : 'Run Eval'}
        </button>

        {isRunning && (
          <button
            onClick={handleStop}
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

      {/* Results */}
      {viewingReport && (
        <div className="space-y-6">
          <div className="bg-gray-900 rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-medium text-gray-300">Summary</h3>
            <SummaryTable report={viewingReport} archs={archs} />
          </div>

          <div className="bg-gray-900 rounded-lg p-4 space-y-3">
            <h3 className="text-sm font-medium text-gray-300">Comparison Matrix</h3>
            <ComparisonMatrix report={viewingReport} />
          </div>
        </div>
      )}

      {/* Past runs */}
      {pastRuns.length > 0 && (
        <div className="bg-gray-900 rounded-lg p-4 space-y-3">
          <h3 className="text-sm font-medium text-gray-300">Past Runs</h3>
          <div className="space-y-1">
            {pastRuns.map((r) => (
              <button
                key={r.run_id}
                onClick={() => handleViewPastRun(r.run_id)}
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
      )}
    </div>
  )
}
