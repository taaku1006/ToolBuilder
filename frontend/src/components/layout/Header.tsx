interface HeaderProps {
  page: 'builder' | 'dashboard' | 'eval'
  onNavigate: (page: 'builder' | 'dashboard' | 'eval') => void
}

export function Header({ page, onNavigate }: HeaderProps) {
  return (
    <header className="bg-gray-950 border-b border-gray-800 px-4 py-1.5">
      <div className="flex items-center justify-between">
        <h1 className="text-sm font-semibold text-gray-200 tracking-tight font-mono">
          ToolBuilder
        </h1>
        <nav className="flex items-center gap-0.5 bg-gray-900 rounded-md p-0.5">
          <button
            onClick={() => onNavigate('builder')}
            className={`px-3 py-1 text-xs rounded transition-colors ${
              page === 'builder'
                ? 'bg-gray-800 text-white font-medium'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            Build
          </button>
          <button
            onClick={() => onNavigate('dashboard')}
            className={`px-3 py-1 text-xs rounded transition-colors ${
              page === 'dashboard'
                ? 'bg-gray-800 text-white font-medium'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            Dashboard
          </button>
          <button
            onClick={() => onNavigate('eval')}
            className={`px-3 py-1 text-xs rounded transition-colors ${
              page === 'eval'
                ? 'bg-gray-800 text-white font-medium'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            Eval
          </button>
        </nav>
      </div>
    </header>
  )
}
