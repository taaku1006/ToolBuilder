const ERROR_COLORS: Record<string, string> = {
  json_parse: 'bg-orange-900/50 text-orange-300',
  syntax_error: 'bg-red-900/50 text-red-300',
  runtime_error: 'bg-red-900/50 text-red-400',
  timeout: 'bg-yellow-900/50 text-yellow-300',
  api_error: 'bg-purple-900/50 text-purple-300',
  file_not_found: 'bg-blue-900/50 text-blue-300',
  unknown: 'bg-gray-700/50 text-gray-400',
}

interface ErrorBreakdownProps {
  breakdown?: Record<string, number>
}

export function ErrorBreakdown({ breakdown }: ErrorBreakdownProps) {
  if (!breakdown) return null
  const errors = Object.entries(breakdown).filter(([k]) => k !== 'none')
  if (errors.length === 0) return null
  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {errors.map(([cat, count]) => (
        <span key={cat} className={`text-xs px-1.5 py-0.5 rounded ${ERROR_COLORS[cat] ?? ERROR_COLORS.unknown}`}>
          {cat}: {count}
        </span>
      ))}
    </div>
  )
}
