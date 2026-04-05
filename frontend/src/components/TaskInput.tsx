import type { KeyboardEvent } from 'react'
import { useGenerateStore } from '../stores/useGenerateStore'
import { ModelSelector } from './ModelSelector'

interface TaskInputProps {
  fileId?: string
}

export function TaskInput({ fileId }: TaskInputProps) {
  const { task, loading, setTask, generateSSE } = useGenerateStore()

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      generateSSE(fileId)
    }
  }

  return (
    <div className="w-full">
      <textarea
        className="w-full min-h-20 px-3 py-2 bg-gray-900/50 text-gray-200 border border-gray-800 rounded resize-y focus:outline-none focus:border-gray-600 placeholder-gray-600 text-xs disabled:opacity-50 disabled:cursor-not-allowed"
        placeholder="Describe task (e.g. aggregate monthly sales data and create a chart)"
        value={task}
        onChange={(e) => setTask(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={loading}
      />
      <div className="mt-2 flex flex-col gap-1.5">
        <ModelSelector />
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-gray-600 font-mono">
            Cmd+Enter to generate
          </span>
          <button
          className="px-4 py-1.5 bg-blue-600 hover:bg-blue-700 text-white text-xs font-medium rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={() => generateSSE(fileId)}
          disabled={loading}
        >
            {loading ? 'generating...' : 'Generate'}
          </button>
        </div>
      </div>
    </div>
  )
}
