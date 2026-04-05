import { useEffect } from 'react'
import { useHistoryStore } from '../../stores/useHistoryStore'

function formatDate(dateStr: string): string {
  const date = new Date(dateStr)
  return date.toLocaleDateString('ja-JP', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  })
}

export function Sidebar() {
  const {
    items,
    selectedId,
    searchQuery,
    loading,
    error,
    fetchHistory,
    selectItem,
    deleteItem,
    setSearchQuery,
  } = useHistoryStore()

  useEffect(() => {
    void fetchHistory()
  }, [fetchHistory])

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value
    setSearchQuery(value)
    void fetchHistory(value || undefined)
  }

  const handleDeleteClick = (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    void deleteItem(id)
  }

  return (
    <div className="flex flex-col">
      <div className="px-3 py-2 border-b border-gray-800">
        <h2 className="text-xs uppercase tracking-wide text-gray-500 mb-2">History</h2>
        <input
          type="text"
          placeholder="Search..."
          value={searchQuery}
          onChange={handleSearchChange}
          className="w-full bg-gray-800/50 border border-gray-800 text-gray-300 text-xs rounded px-2 py-1.5 placeholder-gray-600 focus:outline-none focus:border-gray-600"
        />
      </div>

      <div className="overflow-y-auto">
        {loading && (
          <div className="px-4 py-6 text-center text-sm text-gray-500">読み込み中...</div>
        )}

        {error && !loading && (
          <div className="px-4 py-3 text-sm text-red-400">{error}</div>
        )}

        {!loading && !error && items.length === 0 && (
          <div className="px-4 py-6 text-center text-sm text-gray-500">履歴がありません</div>
        )}

        {!loading && items.length > 0 && (
          <ul className="py-2">
            {items.map((item) => {
              const isSelected = item.id === selectedId
              return (
                <li
                  key={item.id}
                  data-testid="history-item"
                  onClick={() => selectItem(item.id)}
                  className={[
                    'px-3 py-1.5 cursor-pointer border-l-2 transition-colors',
                    'hover:bg-gray-800/50',
                    isSelected
                      ? 'border-blue-500 bg-gray-800/50'
                      : 'border-transparent',
                  ].join(' ')}
                >
                  <div className="flex items-start justify-between gap-1">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-gray-300 truncate">{item.task}</p>
                      <p className="text-[10px] text-gray-600 mt-0.5 font-mono">{formatDate(item.created_at)}</p>
                    </div>
                    <button
                      onClick={(e) => handleDeleteClick(e, item.id)}
                      aria-label="削除"
                      className="shrink-0 text-gray-600 hover:text-red-400 transition-colors text-xs px-1"
                    >
                      削除
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
