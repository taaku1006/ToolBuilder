import { PHASE_DEFINITIONS } from '../../../constants/phases'

interface PhaseTagProps {
  phase: string
}

export function PhaseTag({ phase }: PhaseTagProps) {
  const info = PHASE_DEFINITIONS[phase]
  return (
    <span className={`px-1.5 py-0.5 rounded text-xs font-mono ${info?.color ?? 'bg-gray-700 text-gray-300'}`}>
      {phase}
    </span>
  )
}
