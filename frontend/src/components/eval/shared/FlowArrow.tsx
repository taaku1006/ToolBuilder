interface FlowArrowProps {
  label?: string
}

export function FlowArrow({ label }: FlowArrowProps) {
  return (
    <div className="flex flex-col items-center py-0.5">
      <div className="w-px h-3 bg-gray-600" />
      <div className="text-gray-600 text-[10px]">▼{label ? ` ${label}` : ''}</div>
    </div>
  )
}
