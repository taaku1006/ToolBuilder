import type { KeyboardEvent } from 'react'
import { useGenerateStore } from '../stores/useGenerateStore'

interface TaskInputProps {
  fileId?: string
}

export function TaskInput({ fileId }: TaskInputProps) {
  const { task, loading, setTask, generate } = useGenerateStore()

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      generate(fileId)
    }
  }

  return (
    <div className="w-full">
      <textarea
        className="w-full min-h-32 px-4 py-3 bg-gray-800 text-gray-100 border border-gray-600 rounded-lg resize-y focus:outline-none focus:border-blue-500 placeholder-gray-500 font-sans text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        placeholder="タスクを日本語で入力してください (例: 売上データを月別に集計してグラフを作成する)"
        value={task}
        onChange={(e) => setTask(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={loading}
      />
      <div className="mt-3 flex items-center justify-between">
        <span className="text-xs text-gray-500">
          Cmd+Enter でも生成できます
        </span>
        <button
          className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={() => generate(fileId)}
          disabled={loading}
        >
          {loading ? '生成中...' : '生成'}
        </button>
      </div>
    </div>
  )
}
