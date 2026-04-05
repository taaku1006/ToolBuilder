import { useFileStore } from '../stores/useFileStore'

const MAX_PREVIEW_ROWS = 30

const TYPE_BADGE_COLORS: Record<string, string> = {
  string: 'bg-blue-900 text-blue-300',
  integer: 'bg-green-900 text-green-300',
  float: 'bg-yellow-900 text-yellow-300',
  datetime: 'bg-purple-900 text-purple-300',
  boolean: 'bg-orange-900 text-orange-300',
}

function typeBadgeClass(type: string): string {
  return TYPE_BADGE_COLORS[type] ?? 'bg-gray-700 text-gray-300'
}

export function SheetPreview() {
  const { uploadResponse, activeSheet, setActiveSheet } = useFileStore()

  if (!uploadResponse) return null

  const { sheets } = uploadResponse
  const sheet = sheets[activeSheet] ?? sheets[0]

  if (!sheet) return null

  const rows = sheet.preview.slice(0, MAX_PREVIEW_ROWS)

  return (
    <div className="w-full space-y-2">
      <div role="tablist" className="flex gap-0.5 border-b border-gray-800 overflow-x-auto">
        {sheets.map((s, index) => (
          <button
            key={s.name}
            role="tab"
            aria-selected={activeSheet === index}
            onClick={() => setActiveSheet(index)}
            className={[
              'shrink-0 px-3 py-1 text-xs font-mono transition-colors rounded-t',
              activeSheet === index
                ? 'bg-gray-800/80 text-blue-400 border-t border-x border-gray-800 -mb-px'
                : 'text-gray-500 hover:text-gray-300',
            ].join(' ')}
          >
            {s.name}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2 px-1">
        <span className="text-[10px] text-gray-600 font-mono">
          {sheet.total_rows.toLocaleString()} rows
          {sheet.total_rows > MAX_PREVIEW_ROWS && (
            <> (showing {MAX_PREVIEW_ROWS})</>
          )}
        </span>
      </div>

      <div className="overflow-x-auto rounded border border-gray-800">
        <table className="w-full text-xs">
          <thead>
            <tr className="bg-gray-900/80 sticky top-0">
              {sheet.headers.map((header) => (
                <th
                  key={header}
                  scope="col"
                  className="px-2 py-1 text-left font-medium text-gray-400 whitespace-nowrap"
                >
                  <div className="flex items-center gap-1.5">
                    <span className="font-mono">{header}</span>
                    <span
                      className={`inline-block rounded px-1 py-px text-[10px] font-normal ${typeBadgeClass(sheet.types[header] ?? '')}`}
                    >
                      {sheet.types[header] ?? '?'}
                    </span>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr
                key={rowIndex}
                className={rowIndex % 2 === 0 ? 'bg-gray-950/50' : 'bg-gray-900/30'}
              >
                {sheet.headers.map((header) => (
                  <td
                    key={header}
                    className="px-2 py-1 text-gray-300 whitespace-nowrap font-mono"
                  >
                    {row[header] == null ? '' : String(row[header])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
