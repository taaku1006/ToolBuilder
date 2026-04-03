import { PHASE_DEFINITIONS, MAGENTIC_ONE_PHASE_DEFINITIONS } from '../../../constants/phases'

interface FlowBlockProps {
  label: string
  phase?: string
  active: boolean
  children?: React.ReactNode
}

export function FlowBlock({ label, phase, active, children }: FlowBlockProps) {
  const info = phase
    ? (PHASE_DEFINITIONS[phase] ?? MAGENTIC_ONE_PHASE_DEFINITIONS[phase] ?? null)
    : null
  return (
    <div
      className={`border rounded-lg px-3 py-2 text-xs ${
        active
          ? `${info?.color ?? 'bg-gray-700 text-gray-300'} border-gray-600`
          : 'bg-gray-800/30 text-gray-600 border-gray-700/50 opacity-50'
      }`}
    >
      <div className="font-mono font-medium">{label}</div>
      {children && <div className="mt-1 font-sans">{children}</div>}
    </div>
  )
}
