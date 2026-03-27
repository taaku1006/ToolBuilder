import { useEffect, useRef, useState } from 'react'
import { useSkillsStore } from '../stores/useSkillsStore'
import type { SkillItem } from '../types'

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString('ja-JP', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

function ToolCard({
  skill,
  onRun,
  running,
  runningSkillId,
}: {
  skill: SkillItem
  onRun: (skill: SkillItem) => void
  running: boolean
  runningSkillId: string | null
}) {
  const isRunning = running && runningSkillId === skill.id
  const successPct = Math.round(skill.success_rate * 100)

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-5 flex flex-col justify-between hover:border-gray-600 transition-colors">
      <div>
        <h3 className="text-sm font-semibold text-gray-100 leading-snug line-clamp-2">
          {skill.title}
        </h3>
        {skill.task_summary && skill.task_summary !== skill.title && (
          <p className="text-xs text-gray-400 mt-1.5 line-clamp-2">{skill.task_summary}</p>
        )}
        {skill.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-2">
            {skill.tags.map((tag) => (
              <span
                key={tag}
                className="inline-block bg-blue-900/60 text-blue-300 text-xs px-1.5 py-0.5 rounded"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="mt-4 space-y-3">
        <div className="flex items-center justify-between text-xs text-gray-500">
          <span>{formatDate(skill.created_at)}</span>
          <div className="flex items-center gap-3">
            <span>{skill.use_count}回使用</span>
            <span
              className={
                successPct >= 80
                  ? 'text-green-400'
                  : successPct >= 50
                    ? 'text-yellow-400'
                    : 'text-red-400'
              }
            >
              {successPct}%成功
            </span>
          </div>
        </div>

        <button
          className="w-full px-4 py-2.5 text-sm font-medium bg-green-700 hover:bg-green-600 text-white rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={() => onRun(skill)}
          disabled={isRunning}
        >
          {isRunning ? '実行中...' : 'Excelを選んで実行'}
        </button>
      </div>
    </div>
  )
}

function RunResultPanel() {
  const { runResult, clearRunResult } = useSkillsStore()

  if (!runResult) return null

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-xl p-5 space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-gray-300">実行結果</h3>
        <div className="flex items-center gap-3">
          <span className="text-xs text-gray-500">{runResult.elapsed_ms}ms</span>
          {runResult.success ? (
            <span className="px-2 py-0.5 text-xs font-medium bg-green-900 text-green-300 rounded">
              成功
            </span>
          ) : (
            <span className="px-2 py-0.5 text-xs font-medium bg-red-900 text-red-300 rounded">
              エラー
            </span>
          )}
        </div>
      </div>

      {runResult.stdout && (
        <pre className="text-xs text-gray-400 bg-gray-900 rounded-lg p-3 overflow-x-auto max-h-40 overflow-y-auto">
          {runResult.stdout}
        </pre>
      )}

      {runResult.stderr && (
        <pre className="text-xs text-red-400 bg-gray-900 rounded-lg p-3 overflow-x-auto max-h-40 overflow-y-auto">
          {runResult.stderr}
        </pre>
      )}

      {runResult.output_files.length > 0 && (
        <div className="space-y-2">
          <p className="text-xs text-gray-500">出力ファイル</p>
          <div className="flex flex-wrap gap-2">
            {runResult.output_files.map((filePath) => {
              const fileName = filePath.split('/').pop() || filePath
              return (
                <a
                  key={filePath}
                  href={`/api/download/${filePath}`}
                  download={fileName}
                  className="inline-flex items-center gap-2 px-4 py-2 text-sm bg-blue-700 hover:bg-blue-600 text-white rounded-lg transition-colors"
                >
                  &#8595; {fileName}
                </a>
              )
            })}
          </div>
        </div>
      )}

      <button
        onClick={clearRunResult}
        className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
      >
        閉じる
      </button>
    </div>
  )
}

interface ToolDashboardProps {
  onBack: () => void
}

export function ToolDashboard({ onBack }: ToolDashboardProps) {
  const { skills, loading, error, fetchSkills, executeSkill, running, removeSkill } =
    useSkillsStore()
  const [search, setSearch] = useState('')
  const [runningSkillId, setRunningSkillId] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const pendingSkillRef = useRef<SkillItem | null>(null)

  useEffect(() => {
    void fetchSkills()
  }, [fetchSkills])

  const filtered = skills.filter((s) => {
    if (!search.trim()) return true
    const q = search.toLowerCase()
    return (
      s.title.toLowerCase().includes(q) ||
      (s.task_summary || '').toLowerCase().includes(q) ||
      s.tags.some((t) => t.toLowerCase().includes(q))
    )
  })

  const handleRun = (skill: SkillItem) => {
    pendingSkillRef.current = skill
    setRunningSkillId(skill.id)
    fileInputRef.current?.click()
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    const skill = pendingSkillRef.current
    if (file && skill) {
      void executeSkill(skill.id, file)
    }
    pendingSkillRef.current = null
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleDelete = (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    if (confirm('このツールを削除しますか？')) {
      void removeSkill(id)
    }
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto">
      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-lg font-semibold text-white">ツールダッシュボード</h2>
            <p className="text-sm text-gray-400 mt-0.5">
              保存済みツールの一覧 — Excelを選ぶだけで即実行
            </p>
          </div>
          <button
            onClick={onBack}
            className="px-4 py-2 text-sm bg-gray-800 hover:bg-gray-700 text-gray-300 rounded-lg transition-colors border border-gray-700"
          >
            &#8592; ツール作成に戻る
          </button>
        </div>

        {/* Search */}
        <div className="mb-6">
          <input
            type="text"
            placeholder="ツールを検索..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full max-w-md px-4 py-2.5 bg-gray-800 text-gray-100 border border-gray-700 rounded-lg text-sm focus:outline-none focus:border-blue-500 placeholder-gray-500"
          />
        </div>

        {/* Run result */}
        <div className="mb-6">
          <RunResultPanel />
        </div>

        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".xlsx,.xls,.csv"
          onChange={handleFileSelect}
          className="hidden"
        />

        {/* Loading */}
        {loading && (
          <div className="py-12 text-center text-gray-500">読み込み中...</div>
        )}

        {/* Error */}
        {error && !loading && (
          <div className="bg-red-950 border border-red-800 text-red-300 rounded-lg px-4 py-3 text-sm mb-6">
            {error}
          </div>
        )}

        {/* Empty */}
        {!loading && !error && skills.length === 0 && (
          <div className="py-16 text-center">
            <p className="text-gray-400 text-lg mb-2">ツールがまだありません</p>
            <p className="text-gray-500 text-sm mb-6">
              「ツール作成」でタスクを実行すると、成功したコードが自動的にツールとして保存されます
            </p>
            <button
              onClick={onBack}
              className="px-6 py-2.5 text-sm bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
            >
              ツールを作成する
            </button>
          </div>
        )}

        {/* No results */}
        {!loading && filtered.length === 0 && skills.length > 0 && (
          <div className="py-12 text-center text-gray-500">
            「{search}」に一致するツールが見つかりません
          </div>
        )}

        {/* Grid */}
        {!loading && filtered.length > 0 && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((skill) => (
              <div key={skill.id} className="relative group">
                <ToolCard
                  skill={skill}
                  onRun={handleRun}
                  running={running}
                  runningSkillId={runningSkillId}
                />
                <button
                  onClick={(e) => handleDelete(e, skill.id)}
                  className="absolute top-3 right-3 text-gray-600 hover:text-red-400 transition-colors opacity-0 group-hover:opacity-100 text-xs"
                  title="削除"
                >
                  &#10005;
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
