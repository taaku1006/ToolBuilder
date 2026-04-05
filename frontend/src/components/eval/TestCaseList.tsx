import type { EvalTestCase } from '../../api/eval'

interface TestCaseListProps {
  cases: EvalTestCase[]
  selectedCases: Set<string>
  onToggleCase: (id: string) => void
  onDeleteCase: (id: string) => void
}

export function TestCaseList({ cases, selectedCases, onToggleCase, onDeleteCase }: TestCaseListProps) {
  if (cases.length === 0) {
    return <div className="text-xs text-gray-600 py-2">No test cases yet. Click "+ Add" to create one.</div>
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs">
        <thead>
          <tr className="border-b border-gray-800">
            <th className="text-left py-1 px-2 text-gray-600 font-normal uppercase tracking-wide text-[10px] w-6" />
            <th className="text-left py-1 px-2 text-gray-600 font-normal uppercase tracking-wide text-[10px]">Label</th>
            <th className="text-left py-1 px-2 text-gray-600 font-normal uppercase tracking-wide text-[10px]">Task</th>
            <th className="text-center py-1 px-2 text-gray-600 font-normal uppercase tracking-wide text-[10px]">In</th>
            <th className="text-center py-1 px-2 text-gray-600 font-normal uppercase tracking-wide text-[10px]">Out</th>
            <th className="text-center py-1 px-1 text-gray-600 font-normal text-[10px] w-8" />
          </tr>
        </thead>
        <tbody>
          {cases.map((c) => {
            const isSelected = selectedCases.has(c.id) || selectedCases.size === 0
            const label = c.description || c.id.slice(0, 8) + '...'
            const taskPreview = c.task.length > 60 ? c.task.slice(0, 60) + '…' : c.task
            return (
              <tr
                key={c.id}
                className={`border-b border-gray-800/50 transition-colors cursor-pointer ${
                  isSelected ? 'bg-blue-950/15' : 'opacity-40 hover:opacity-60'
                }`}
                onClick={() => onToggleCase(c.id)}
                title={c.task}
              >
                <td className="py-1.5 px-2 text-center">
                  <span className={`inline-block w-2.5 h-2.5 rounded border ${
                    isSelected ? 'bg-blue-600 border-blue-500' : 'border-gray-700'
                  }`} />
                </td>
                <td className="py-1.5 px-2 font-mono text-gray-300 whitespace-nowrap max-w-[140px] truncate">
                  {label}
                </td>
                <td className="py-1.5 px-2 text-gray-500 max-w-[300px] truncate">{taskPreview}</td>
                <td className="py-2 px-2 text-center">
                  {c.file_path
                    ? <span className="inline-block w-2 h-2 rounded-full bg-indigo-400" title="Input file attached" />
                    : <span className="inline-block w-2 h-2 rounded-full bg-gray-700" />}
                </td>
                <td className="py-2 px-2 text-center">
                  {c.expected_file_path
                    ? <span className="inline-block w-2 h-2 rounded-full bg-green-400" title="Expected file attached" />
                    : <span className="inline-block w-2 h-2 rounded-full bg-gray-700" />}
                </td>
                <td className="py-2 px-1 text-center" onClick={(e) => e.stopPropagation()}>
                  <button
                    onClick={() => onDeleteCase(c.id)}
                    className="text-xs text-gray-600 hover:text-red-400 transition-colors px-1"
                    title="Delete test case"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
