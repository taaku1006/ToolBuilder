import type { AgentLogEntry } from '../types'

interface DebugLogProps {
  agentLog: AgentLogEntry[]
}

interface RetryEntry {
  index: number
  content: string
}

function extractVerifyFixData(agentLog: AgentLogEntry[]): {
  startEntry: AgentLogEntry | null
  retries: RetryEntry[]
  completeEntry: AgentLogEntry | null
  errorEntry: AgentLogEntry | null
} {
  const vfEntries = agentLog.filter((entry) => entry.phase === 'VF')

  let startEntry: AgentLogEntry | null = null
  const retries: RetryEntry[] = []
  let completeEntry: AgentLogEntry | null = null
  let errorEntry: AgentLogEntry | null = null
  let retryCount = 0

  for (const entry of vfEntries) {
    if (entry.action === 'start') {
      startEntry = entry
    } else if (entry.action === 'fix' || entry.action === 'retry') {
      retryCount += 1
      retries.push({ index: retryCount, content: entry.content })
    } else if (entry.action === 'complete') {
      completeEntry = entry
    } else if (entry.action === 'error' || entry.action === 'escalate') {
      errorEntry = entry
    }
  }

  return { startEntry, retries, completeEntry, errorEntry }
}

export function DebugLog({ agentLog }: DebugLogProps) {
  const vfEntries = agentLog.filter((entry) => entry.phase === 'VF')

  if (vfEntries.length === 0) return null

  const { startEntry, retries, completeEntry, errorEntry } = extractVerifyFixData(agentLog)

  const hasSuccess = completeEntry !== null
  const hasError = errorEntry !== null

  return (
    <section aria-label="検証・修正ログ" className="rounded border border-gray-800 bg-gray-900/50 p-3">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-gray-500 bg-gray-800/80 border border-gray-800 rounded px-1.5 py-0.5">
            VF
          </span>
          <h2 className="text-xs font-medium text-gray-300">Verify-Fix</h2>
        </div>
        {hasSuccess && (
          <span className="inline-block w-2 h-2 rounded-full bg-green-400" title="Success" />
        )}
        {hasError && (
          <span className="inline-block w-2 h-2 rounded-full bg-red-400" title="Failed" />
        )}
      </div>

      <div className="space-y-1">
        {startEntry !== null && (
          <p className="text-[10px] text-gray-500 font-mono">{startEntry.content}</p>
        )}

        {retries.length > 0 && (
          <ul className="space-y-1">
            {retries.map((retry) => (
              <li key={retry.index} className="rounded border border-gray-800 bg-gray-950/50 px-2 py-1.5">
                <p className="text-[10px] font-mono text-gray-400">
                  <span className="text-yellow-500">retry {retry.index}</span> {retry.content}
                </p>
              </li>
            ))}
          </ul>
        )}

        {completeEntry !== null && (
          <div className="rounded border border-green-900 bg-green-950/30 px-2 py-1.5">
            <p className="text-[10px] text-green-400 font-mono">
              {completeEntry.content}
            </p>
          </div>
        )}

        {errorEntry !== null && (
          <div className="rounded border border-red-900 bg-red-950/30 px-2 py-1.5">
            <p className="text-[10px] text-red-400 font-mono">
              {errorEntry.content}
            </p>
          </div>
        )}
      </div>
    </section>
  )
}
