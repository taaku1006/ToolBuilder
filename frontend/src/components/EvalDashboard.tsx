import { useCallback, useState } from 'react'
import {
  type EvalReport,
  type RunSnapshot,
  type RunStatus,
  type RunComparisonResult,
  type SnapshotDiff,
  startRun,
  stopRun,
  getRunStatus,
  listRuns,
  deleteTestCase,
  getRunSnapshot,
  compareRuns,
  diffRuns,
} from '../api/eval'
import { useEvalData } from '../hooks/useEvalData'
import { useRunPolling } from '../hooks/useRunPolling'
import { useArchSelection } from '../hooks/useArchSelection'
import {
  ArchitectureTable,
  CreateTestCaseForm,
  PastRunsList,
  ResultsSection,
  RunControls,
  TestCaseList,
} from './eval'

export function EvalDashboard() {
  const { archs, cases, pastRuns, setPastRuns, error: dataError, reloadCases } = useEvalData()
  const { selectedArchs, toggleArch } = useArchSelection()
  const [selectedCases, setSelectedCases] = useState<Set<string>>(new Set())
  const [detailArchId, setDetailArchId] = useState<string | null>(null)

  const [runStatus, setRunStatus] = useState<RunStatus | null>(null)
  const [viewingReport, setViewingReport] = useState<EvalReport | null>(null)
  const [viewingRunId, setViewingRunId] = useState<string | null>(null)
  const [snapshot, setSnapshot] = useState<RunSnapshot | null>(null)
  const [comparisonResult, setComparisonResult] = useState<RunComparisonResult | null>(null)
  const [snapshotDiff, setSnapshotDiff] = useState<SnapshotDiff | null>(null)
  const [compareBaselineId, setCompareBaselineId] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [showAddCase, setShowAddCase] = useState(false)

  const handlePollStatus = useCallback(
    (status: RunStatus) => {
      setRunStatus(status)
      if (status.status !== 'running') {
        if (status.report) {
          setViewingReport(status.report as EvalReport)
          setViewingRunId(status.run_id)
          getRunSnapshot(status.run_id).then(setSnapshot).catch(() => setSnapshot(null))
        }
        listRuns().then(setPastRuns).catch(() => {})
      }
    },
    [setPastRuns],
  )

  const { startPolling } = useRunPolling(handlePollStatus)

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
      setViewingRunId(runId)
      setComparisonResult(null)
      setSnapshotDiff(null)
      setCompareBaselineId(null)
      try {
        const snap = await getRunSnapshot(runId)
        setSnapshot(snap)
      } catch {
        setSnapshot(null)
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load run')
    }
  }

  const handleCompareRun = async (baselineId: string) => {
    if (!viewingRunId) return
    setCompareBaselineId(baselineId)
    try {
      const [comp, diff] = await Promise.all([
        compareRuns(viewingRunId, baselineId),
        diffRuns(viewingRunId, baselineId).catch(() => null),
      ])
      setComparisonResult(comp)
      setSnapshotDiff(diff)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to compare')
    }
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

  const displayError = error ?? dataError
  const isRunning = runStatus?.status === 'running'

  return (
    <div className="max-w-6xl mx-auto px-6 py-8 space-y-6">
      <h2 className="text-xl font-semibold text-white">Agent Architecture Eval</h2>

      {displayError && (
        <div className="bg-red-950 border border-red-800 text-red-300 rounded-lg px-4 py-3 text-sm">
          {displayError}
        </div>
      )}

      <div className="bg-gray-900 rounded-lg p-4 space-y-3">
        <h3 className="text-sm font-medium text-gray-300">
          Architectures
          <span className="text-gray-500 ml-2 font-normal">
            ({selectedArchs.size === 0 ? 'all' : selectedArchs.size} selected)
          </span>
        </h3>
        <ArchitectureTable
          archs={archs}
          selectedArchs={selectedArchs}
          toggleArch={toggleArch}
          detailArchId={detailArchId}
          setDetailArchId={setDetailArchId}
        />
      </div>

      <div className="bg-gray-900 rounded-lg p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium text-gray-300">
            Test Cases
            <span className="text-gray-500 ml-2 font-normal">
              ({selectedCases.size === 0 ? 'all' : selectedCases.size} selected)
            </span>
          </h3>
          <button
            type="button"
            onClick={() => setShowAddCase((v) => !v)}
            className="text-xs px-2.5 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg transition-colors"
          >
            {showAddCase ? 'Cancel' : '+ Add'}
          </button>
        </div>

        {showAddCase && (
          <CreateTestCaseForm onCreated={reloadCases} onClose={() => setShowAddCase(false)} />
        )}

        <TestCaseList
          cases={cases}
          selectedCases={selectedCases}
          onToggleCase={toggleCase}
          onDeleteCase={handleDeleteCase}
        />
      </div>

      <RunControls
        isRunning={isRunning}
        loading={loading}
        runStatus={runStatus}
        archs={archs}
        cases={cases}
        selectedArchs={selectedArchs}
        selectedCases={selectedCases}
        onRun={handleRun}
        onStop={handleStop}
      />

      {viewingReport && (
        <ResultsSection
          report={viewingReport}
          archs={archs}
          runId={viewingRunId}
          snapshot={snapshot}
          pastRuns={pastRuns}
          compareBaselineId={compareBaselineId}
          comparisonResult={comparisonResult}
          snapshotDiff={snapshotDiff}
          onCompare={handleCompareRun}
        />
      )}

      {pastRuns.length > 0 && (
        <PastRunsList pastRuns={pastRuns} onViewRun={handleViewPastRun} />
      )}
    </div>
  )
}
