interface HeaderProps {
  page: 'builder' | 'dashboard'
  onNavigate: (page: 'builder' | 'dashboard') => void
}

export function Header({ page, onNavigate }: HeaderProps) {
  return (
    <header className="bg-gray-900 border-b border-gray-700 px-6 py-3">
      <div className="max-w-6xl mx-auto flex items-center justify-between">
        <div>
          <h1 className="text-lg font-semibold text-white tracking-tight">
            Excel x AI ツールビルダー
          </h1>
        </div>
        <nav className="flex items-center gap-1 bg-gray-800 rounded-lg p-1">
          <button
            onClick={() => onNavigate('builder')}
            className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
              page === 'builder'
                ? 'bg-gray-700 text-white font-medium'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            ツール作成
          </button>
          <button
            onClick={() => onNavigate('dashboard')}
            className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
              page === 'dashboard'
                ? 'bg-gray-700 text-white font-medium'
                : 'text-gray-400 hover:text-gray-200'
            }`}
          >
            ダッシュボード
          </button>
        </nav>
      </div>
    </header>
  )
}
