import { useEffect, useRef } from 'react'
import { useSkillsStore } from '../stores/useSkillsStore'
import type { SkillItem, SkillSuggestion } from '../types'

function TagBadge({ tag }: { tag: string }) {
  return (
    <span className="inline-block bg-blue-900 text-blue-300 text-xs px-1.5 py-0.5 rounded">
      {tag}
    </span>
  )
}

function SkillCard({
  skill,
  isSelected,
  onSelect,
  onDelete,
}: {
  skill: SkillItem
  isSelected: boolean
  onSelect: () => void
  onDelete: (e: React.MouseEvent) => void
}) {
  return (
    <li
      data-testid={`skill-item-${skill.id}`}
      onClick={onSelect}
      className={[
        'px-3 py-2 cursor-pointer border rounded transition-colors hover:bg-gray-800',
        isSelected ? 'border-blue-500 bg-gray-800' : 'border-transparent',
      ].join(' ')}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm text-gray-200 truncate">{skill.title}</p>
          {skill.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {skill.tags.map((tag) => (
                <TagBadge key={tag} tag={tag} />
              ))}
            </div>
          )}
          <p className="text-xs text-gray-500 mt-1">
            {skill.use_count}回 / {Math.round(skill.success_rate * 100)}%成功
          </p>
        </div>
        <button
          onClick={onDelete}
          aria-label="削除"
          className="shrink-0 text-gray-600 hover:text-red-400 transition-colors text-xs px-1"
        >
          削除
        </button>
      </div>
    </li>
  )
}

function SuggestionCard({ suggestion }: { suggestion: SkillSuggestion }) {
  return (
    <li className="px-3 py-2 border border-transparent rounded">
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <p className="text-sm text-gray-300 truncate">{suggestion.title}</p>
          {suggestion.tags.length > 0 && (
            <div className="flex flex-wrap gap-1 mt-1">
              {suggestion.tags.map((tag) => (
                <TagBadge key={tag} tag={tag} />
              ))}
            </div>
          )}
        </div>
        <span className="shrink-0 bg-green-900 text-green-300 text-xs px-1.5 py-0.5 rounded">
          {Math.round(suggestion.similarity * 100)}%
        </span>
      </div>
    </li>
  )
}

function SkillRunner({ skillId, skillTitle }: { skillId: string; skillTitle: string }) {
  const { executeSkill, runResult, running, clearRunResult } = useSkillsStore()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      void executeSkill(skillId, file)
    }
    // Reset so the same file can be selected again
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  return (
    <div className="mt-2 space-y-2">
      <input
        ref={fileInputRef}
        type="file"
        accept=".xlsx,.xls,.csv"
        onChange={handleFileSelect}
        className="hidden"
      />
      <button
        className="w-full px-3 py-2 text-sm bg-green-700 hover:bg-green-600 text-white rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        onClick={() => fileInputRef.current?.click()}
        disabled={running}
      >
        {running ? '実行中...' : `▶ ${skillTitle} を実行`}
      </button>
      <p className="text-xs text-gray-500">Excelファイルを選択すると即実行されます</p>

      {runResult && (
        <div className="bg-gray-800 rounded p-3 space-y-2">
          <div className="flex items-center gap-2">
            {runResult.success ? (
              <span className="text-xs font-medium bg-green-900 text-green-300 px-2 py-0.5 rounded">成功</span>
            ) : (
              <span className="text-xs font-medium bg-red-900 text-red-300 px-2 py-0.5 rounded">エラー</span>
            )}
            <span className="text-xs text-gray-500">{runResult.elapsed_ms}ms</span>
          </div>

          {runResult.stdout && (
            <pre className="text-xs text-gray-400 bg-gray-900 rounded p-2 overflow-x-auto max-h-32 overflow-y-auto">
              {runResult.stdout}
            </pre>
          )}

          {runResult.output_files.length > 0 && (
            <div className="space-y-1">
              {runResult.output_files.map((filePath) => {
                const fileName = filePath.split('/').pop() || filePath
                return (
                  <a
                    key={filePath}
                    href={`/api/download/${filePath}`}
                    download={fileName}
                    className="flex items-center gap-2 px-2 py-1.5 text-xs bg-blue-900 hover:bg-blue-800 text-blue-200 rounded transition-colors"
                  >
                    &#8595; {fileName}
                  </a>
                )
              })}
            </div>
          )}

          <button
            onClick={clearRunResult}
            className="text-xs text-gray-500 hover:text-gray-300"
          >
            結果をクリア
          </button>
        </div>
      )}
    </div>
  )
}

export function SkillsPanel() {
  const {
    skills,
    suggestions,
    selectedSkillId,
    loading,
    error,
    fetchSkills,
    selectSkill,
    removeSkill,
  } = useSkillsStore()

  useEffect(() => {
    void fetchSkills()
  }, [fetchSkills])

  const handleDeleteClick = (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    void removeSkill(id)
  }

  const isEmpty = skills.length === 0 && suggestions.length === 0
  const selectedSkill = skills.find((s) => s.id === selectedSkillId)

  return (
    <div className="border-t border-gray-800 px-4 py-4">
      <h2 className="text-sm font-semibold text-gray-300 mb-3">ツール</h2>

      {loading && (
        <div className="py-4 text-center text-sm text-gray-500">読み込み中...</div>
      )}

      {error && !loading && (
        <div className="text-sm text-red-400">{error}</div>
      )}

      {!loading && !error && isEmpty && (
        <div className="py-4 text-center text-sm text-gray-500">
          ツールがありません。
          <br />
          <span className="text-xs">タスクを実行してスキルを保存するとここに表示されます</span>
        </div>
      )}

      {!loading && skills.length > 0 && (
        <ul className="space-y-1 mb-3">
          {skills.map((skill) => (
            <SkillCard
              key={skill.id}
              skill={skill}
              isSelected={skill.id === selectedSkillId}
              onSelect={() => selectSkill(skill.id === selectedSkillId ? null : skill.id)}
              onDelete={(e) => handleDeleteClick(e, skill.id)}
            />
          ))}
        </ul>
      )}

      {selectedSkill && (
        <SkillRunner skillId={selectedSkill.id} skillTitle={selectedSkill.title} />
      )}

      {!loading && suggestions.length > 0 && (
        <div data-testid="suggestions-section">
          <h3 className="text-xs font-semibold text-gray-400 mb-2">提案スキル</h3>
          <ul className="space-y-1">
            {suggestions.map((suggestion) => (
              <SuggestionCard key={suggestion.id} suggestion={suggestion} />
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
