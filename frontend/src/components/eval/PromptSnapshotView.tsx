import { useState } from 'react'
import type { RunSnapshot } from '../../api/eval'
import { PhaseTag } from './shared/PhaseTag'

interface PromptSnapshotViewProps {
  snapshot: RunSnapshot
}

export function PromptSnapshotView({ snapshot }: PromptSnapshotViewProps) {
  const [expanded, setExpanded] = useState<string | null>(null)
  const prompts = Object.entries(snapshot.prompt_contents)

  return (
    <div className="space-y-2">
      <div className="text-xs text-gray-500 font-mono">
        snapshot: {snapshot.snapshot_hash.slice(0, 16)}...
      </div>
      {prompts.map(([name, content]) => {
        const hash = snapshot.prompt_hashes[name] ?? ''
        const isOpen = expanded === name
        return (
          <div key={name} className="border border-gray-700 rounded-lg overflow-hidden">
            <button
              onClick={() => setExpanded(isOpen ? null : name)}
              className="w-full text-left px-3 py-2 flex items-center justify-between hover:bg-gray-800 transition-colors"
            >
              <div className="flex items-center gap-2">
                <PhaseTag phase={name.replace('phase_', '').toUpperCase()} />
                <span className="text-sm text-gray-300">{name}</span>
                <span className="text-xs text-gray-600 font-mono">{hash.slice(0, 12)}...</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">{content.length} chars</span>
                <span className="text-xs text-gray-600">{isOpen ? '▼' : '▶'}</span>
              </div>
            </button>
            {isOpen && (
              <pre className="px-3 py-2 bg-gray-950 text-xs text-gray-400 overflow-x-auto whitespace-pre-wrap border-t border-gray-700 max-h-64 overflow-y-auto">
                {content}
              </pre>
            )}
          </div>
        )
      })}

      {Object.keys(snapshot.architecture_configs).length > 0 && (
        <div className="border border-gray-700 rounded-lg overflow-hidden">
          <div className="px-3 py-2 text-xs text-gray-500">
            Architecture Configs: {Object.keys(snapshot.architecture_configs).join(', ')}
          </div>
        </div>
      )}
    </div>
  )
}
