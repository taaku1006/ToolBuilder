import type { AgentLogEntry } from '../types'

interface DebugLogProps {
  agentLog: AgentLogEntry[]
}

interface RetryEntry {
  index: number
  content: string
}

function extractPhaseDData(agentLog: AgentLogEntry[]): {
  startEntry: AgentLogEntry | null
  retries: RetryEntry[]
  completeEntry: AgentLogEntry | null
  errorEntry: AgentLogEntry | null
} {
  const phaseDEntries = agentLog.filter((entry) => entry.phase === 'D')

  let startEntry: AgentLogEntry | null = null
  const retries: RetryEntry[] = []
  let completeEntry: AgentLogEntry | null = null
  let errorEntry: AgentLogEntry | null = null
  let retryCount = 0

  for (const entry of phaseDEntries) {
    if (entry.action === 'start') {
      startEntry = entry
    } else if (entry.action === 'retry') {
      retryCount += 1
      retries.push({ index: retryCount, content: entry.content })
    } else if (entry.action === 'complete') {
      completeEntry = entry
    } else if (entry.action === 'error') {
      errorEntry = entry
    }
  }

  return { startEntry, retries, completeEntry, errorEntry }
}

export function DebugLog({ agentLog }: DebugLogProps) {
  const phaseDEntries = agentLog.filter((entry) => entry.phase === 'D')

  if (phaseDEntries.length === 0) return null

  const { startEntry, retries, completeEntry, errorEntry } = extractPhaseDData(agentLog)

  const hasSuccess = completeEntry !== null
  const hasError = errorEntry !== null

  return (
    <section aria-label="自律デバッグログ" className="rounded-lg border border-gray-700 bg-gray-900 p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-gray-400 bg-gray-800 border border-gray-600 rounded px-1.5 py-0.5">
            Phase D
          </span>
          <h2 className="text-sm font-bold text-gray-200">自律デバッグ</h2>
        </div>
        {hasSuccess && (
          <span className="text-green-400 text-xs font-medium">成功</span>
        )}
        {hasError && (
          <span className="text-red-400 text-xs font-medium">失敗</span>
        )}
      </div>

      <div className="space-y-2">
        {startEntry !== null && (
          <p className="text-xs text-gray-400 italic">{startEntry.content}</p>
        )}

        {retries.length > 0 && (
          <ul className="space-y-2">
            {retries.map((retry) => (
              <li key={retry.index} className="rounded border border-gray-700 bg-gray-800 px-3 py-2">
                <p className="text-xs font-medium text-gray-300 mb-1">
                  リトライ {retry.index}:
                </p>
                <p className="text-xs text-gray-400 font-mono break-all">
                  エラー: {retry.content}
                </p>
              </li>
            ))}
          </ul>
        )}

        {completeEntry !== null && (
          <div className="rounded border border-green-700 bg-green-950 px-3 py-2">
            <p className="text-xs text-green-400 font-medium">
              {completeEntry.content}
            </p>
          </div>
        )}

        {errorEntry !== null && (
          <div className="rounded border border-red-700 bg-red-950 px-3 py-2">
            <p className="text-xs text-red-400 font-medium">
              {errorEntry.content}
            </p>
          </div>
        )}
      </div>
    </section>
  )
}
