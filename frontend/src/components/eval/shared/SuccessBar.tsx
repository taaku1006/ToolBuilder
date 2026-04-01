interface SuccessBarProps {
  rate: number
  ciLow?: number
  ciHigh?: number
}

export function SuccessBar({ rate, ciLow, ciHigh }: SuccessBarProps) {
  const pct = Math.round(rate * 100)
  const color =
    pct >= 80 ? 'bg-green-500' : pct >= 50 ? 'bg-yellow-500' : 'bg-red-500'
  return (
    <div className="flex items-center gap-2">
      <div className="w-20 h-2 bg-gray-700 rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full`} style={{ width: `${pct}%` }} />
      </div>
      <div className="text-xs">
        <span className="text-gray-400">{pct}%</span>
        {ciLow != null && ciHigh != null && (
          <span className="text-gray-600 ml-1">
            ({Math.round(ciLow * 100)}-{Math.round(ciHigh * 100)}%)
          </span>
        )}
      </div>
    </div>
  )
}
