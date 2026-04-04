import { useState, useEffect } from 'react'
import type { ResultFullDetail, TimelineEntry, ReplanEntry } from '../../api/eval'
import { getResultDetail } from '../../api/eval'
import { PhaseTag } from './shared/PhaseTag'

// ---------------------------------------------------------------------------
// Action color mapping
// ---------------------------------------------------------------------------

const ACTION_COLORS: Record<string, string> = {
  start: 'text-gray-400',
  complete: 'text-green-400',
  fix: 'text-yellow-400',
  replan: 'text-orange-400',
  error: 'text-red-400',
  escalate: 'text-red-500',
}

// ---------------------------------------------------------------------------
// Tab definitions
// ---------------------------------------------------------------------------

type TabId = 'timeline' | 'code' | 'metrics' | 'strategy'

const TABS: Array<{ id: TabId; label: string }> = [
  { id: 'timeline', label: 'Timeline' },
  { id: 'code', label: 'Code' },
  { id: 'metrics', label: 'Metrics' },
  { id: 'strategy', label: 'Strategy' },
]

// ---------------------------------------------------------------------------
// Timeline Tab
// ---------------------------------------------------------------------------

function TimelineTab({ timeline }: { timeline: TimelineEntry[] }) {
  const [expandedIdx, setExpandedIdx] = useState<number | null>(null)

  return (
    <div className="space-y-0.5 max-h-[500px] overflow-y-auto">
      {timeline.map((entry, i) => {
        const isExpanded = expandedIdx === i
        const actionColor = ACTION_COLORS[entry.action] ?? 'text-gray-400'
        const dur = entry.duration_ms != null && entry.duration_ms > 100
          ? `${(entry.duration_ms / 1000).toFixed(1)}s`
          : ''

        return (
          <div
            key={i}
            className="flex items-start gap-2 px-2 py-1 hover:bg-gray-800/50 rounded cursor-pointer"
            onClick={() => setExpandedIdx(isExpanded ? null : i)}
          >
            <div className="flex-shrink-0 w-8 pt-0.5">
              <PhaseTag phase={entry.phase} />
            </div>
            <span className={`flex-shrink-0 w-16 text-[10px] font-mono ${actionColor}`}>
              {entry.action}
            </span>
            <span className="flex-1 text-xs text-gray-300 break-all">
              {isExpanded ? entry.content_preview : entry.content_preview.slice(0, 80)}
              {!isExpanded && entry.content_preview.length > 80 && '...'}
            </span>
            <span className="flex-shrink-0 w-16 text-right text-[10px] text-gray-500 font-mono">
              {dur}
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Code Tab
// ---------------------------------------------------------------------------

function CodeTab({ detail }: { detail: ResultFullDetail }) {
  return (
    <div className="space-y-3 max-h-[500px] overflow-y-auto">
      {/* Status badges */}
      <div className="flex items-center gap-2">
        <span className={`px-2 py-0.5 rounded text-xs font-mono ${
          detail.metrics.code_executes
            ? 'bg-green-900/40 text-green-400'
            : 'bg-red-900/40 text-red-400'
        }`}>
          {detail.metrics.code_executes ? 'Executes' : 'Does not execute'}
        </span>
        <span className="px-2 py-0.5 rounded text-xs font-mono bg-gray-800 text-gray-400">
          {detail.metrics.error_category}
        </span>
      </div>

      {/* Error message */}
      {detail.error && (
        <div className="bg-red-950/30 border border-red-900/50 rounded p-3">
          <div className="text-[10px] text-red-400 font-semibold mb-1">Error</div>
          <pre className="text-xs text-red-300 whitespace-pre-wrap break-all">{detail.error}</pre>
        </div>
      )}

      {/* Generated code */}
      <div>
        <div className="text-[10px] text-gray-500 mb-1">Generated Code</div>
        <pre className="bg-gray-950 border border-gray-800 rounded p-3 text-xs text-gray-200 whitespace-pre-wrap break-all overflow-x-auto">
          {detail.generated_code || '(no code generated)'}
        </pre>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Metrics Tab
// ---------------------------------------------------------------------------

function MetricsBar({ label, value, max, unit }: { label: string; value: number; max: number; unit: string }) {
  const pct = max > 0 ? Math.min((value / max) * 100, 100) : 0
  return (
    <div className="flex items-center gap-2">
      <span className="w-24 text-[10px] text-gray-500 text-right shrink-0">{label}</span>
      <div className="flex-1 bg-gray-800 rounded h-4 overflow-hidden">
        <div className="bg-blue-600/60 h-full rounded" style={{ width: `${pct}%` }} />
      </div>
      <span className="w-20 text-[10px] text-gray-400 font-mono text-right">
        {typeof value === 'number' ? value.toLocaleString() : value} {unit}
      </span>
    </div>
  )
}

function MetricsTab({ detail }: { detail: ResultFullDetail }) {
  const m = detail.metrics
  const phaseDurations = Object.entries(m.phase_durations_ms || {})
  const phaseTokens = Object.entries(m.phase_tokens || {})
  const maxDur = Math.max(...phaseDurations.map(([, v]) => v), 1)
  const maxTok = Math.max(...phaseTokens.map(([, v]) => v), 1)

  return (
    <div className="space-y-4 max-h-[500px] overflow-y-auto">
      {/* Summary stats */}
      <div className="grid grid-cols-3 gap-3">
        {[
          { label: 'Total Tokens', value: m.total_tokens.toLocaleString() },
          { label: 'API Calls', value: m.api_calls.toString() },
          { label: 'Duration', value: `${(m.total_duration_ms / 1000).toFixed(1)}s` },
          { label: 'Cost', value: `$${m.estimated_cost_usd?.toFixed(4) ?? '0.00'}` },
          { label: 'Retries', value: m.retry_count.toString() },
          { label: 'Model', value: detail.model },
        ].map(({ label, value }) => (
          <div key={label} className="bg-gray-800/50 rounded p-2">
            <div className="text-[10px] text-gray-500">{label}</div>
            <div className="text-sm text-gray-200 font-mono">{value}</div>
          </div>
        ))}
      </div>

      {/* Phase durations */}
      {phaseDurations.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 mb-2">Phase Durations</div>
          <div className="space-y-1">
            {phaseDurations.map(([phase, dur]) => (
              <MetricsBar key={phase} label={phase} value={Math.round(dur / 1000)} max={Math.round(maxDur / 1000)} unit="s" />
            ))}
          </div>
        </div>
      )}

      {/* Phase tokens */}
      {phaseTokens.length > 0 && (
        <div>
          <div className="text-[10px] text-gray-500 mb-2">Phase Tokens</div>
          <div className="space-y-1">
            {phaseTokens.map(([phase, tok]) => (
              <MetricsBar key={phase} label={phase} value={tok} max={maxTok} unit="tok" />
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Strategy Tab
// ---------------------------------------------------------------------------

function StrategyTab({ detail }: { detail: ResultFullDetail }) {
  const { strategy, replan_history } = detail

  return (
    <div className="space-y-4 max-h-[500px] overflow-y-auto">
      {/* Strategy card */}
      {strategy && (
        <div className="bg-gray-800/50 rounded p-3 space-y-2">
          <div className="text-xs text-gray-400 font-semibold">Initial Strategy</div>
          <div className="grid grid-cols-2 gap-2 text-xs">
            {strategy.complexity && (
              <div>
                <span className="text-gray-500">Complexity: </span>
                <span className="text-gray-200 font-mono">{strategy.complexity}</span>
              </div>
            )}
            {strategy.approach && (
              <div>
                <span className="text-gray-500">Approach: </span>
                <span className="text-gray-200 font-mono">{strategy.approach}</span>
              </div>
            )}
          </div>
          {strategy.raw_content && (
            <div className="text-[10px] text-gray-500 mt-1">{strategy.raw_content}</div>
          )}
        </div>
      )}

      {/* Replan history */}
      {replan_history.length > 0 ? (
        <div>
          <div className="text-xs text-gray-400 font-semibold mb-2">
            Replan History ({replan_history.length} replans)
          </div>
          <div className="space-y-2">
            {replan_history.map((r: ReplanEntry) => (
              <div key={r.replan_index} className="bg-orange-950/20 border border-orange-900/30 rounded p-2">
                <div className="flex items-center gap-2">
                  <span className="text-orange-400 text-xs font-mono">#{r.replan_index}</span>
                  <span className="text-[10px] text-gray-500">
                    after {r.preceding_attempts} attempts
                  </span>
                </div>
                <div className="text-xs text-gray-300 mt-1">{r.reason}</div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="text-xs text-gray-500">No replans occurred</div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Main Panel
// ---------------------------------------------------------------------------

interface ResultDetailPanelProps {
  runId: string
  archId: string
  caseId: string
}

export function ResultDetailPanel({ runId, archId, caseId }: ResultDetailPanelProps) {
  const [detail, setDetail] = useState<ResultFullDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<TabId>('timeline')

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError(null)
    getResultDetail(runId, archId, caseId)
      .then((d) => { if (!cancelled) setDetail(d) })
      .catch((e) => { if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [runId, archId, caseId])

  if (loading) {
    return <div className="p-4 text-xs text-gray-500">Loading detail...</div>
  }
  if (error) {
    return <div className="p-4 text-xs text-red-400">Error: {error}</div>
  }
  if (!detail) return null

  return (
    <div className="bg-gray-900/80 border border-gray-700 rounded-lg p-3 space-y-3">
      {/* Header */}
      <div className="flex items-center gap-3 text-xs">
        <span className={`px-2 py-0.5 rounded font-mono ${
          detail.metrics.success ? 'bg-green-900/40 text-green-400' : 'bg-red-900/40 text-red-400'
        }`}>
          {detail.metrics.success ? 'PASS' : 'FAIL'}
        </span>
        <span className="text-gray-400">{detail.model}</span>
        <span className="text-gray-600">|</span>
        <span className="text-gray-400">{(detail.metrics.total_duration_ms / 1000).toFixed(1)}s</span>
        <span className="text-gray-600">|</span>
        <span className="text-gray-400">{detail.metrics.total_tokens.toLocaleString()} tokens</span>
        <span className="text-gray-600">|</span>
        <span className="text-gray-400">{detail.metrics.api_calls} calls</span>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-gray-700 pb-1">
        {TABS.map(({ id, label }) => (
          <button
            key={id}
            onClick={() => setActiveTab(id)}
            className={`px-3 py-1 text-xs rounded-t transition-colors ${
              activeTab === id
                ? 'bg-gray-800 text-gray-100 border-b-2 border-blue-500'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {label}
            {id === 'strategy' && detail.replan_history.length > 0 && (
              <span className="ml-1 text-orange-400">({detail.replan_history.length})</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'timeline' && <TimelineTab timeline={detail.timeline} />}
      {activeTab === 'code' && <CodeTab detail={detail} />}
      {activeTab === 'metrics' && <MetricsTab detail={detail} />}
      {activeTab === 'strategy' && <StrategyTab detail={detail} />}
    </div>
  )
}
