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
    <div className="w-full space-y-3">
      <div role="tablist" className="flex gap-1 border-b border-gray-700 overflow-x-auto">
        {sheets.map((s, index) => (
          <button
            key={s.name}
            role="tab"
            aria-selected={activeSheet === index}
            onClick={() => setActiveSheet(index)}
            className={[
              'shrink-0 px-4 py-2 text-sm font-medium transition-colors rounded-t-md',
              activeSheet === index
                ? 'bg-gray-800 text-blue-400 border-t border-x border-gray-700 -mb-px'
                : 'text-gray-400 hover:text-gray-200',
            ].join(' ')}
          >
            {s.name}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-3 px-1">
        <span className="text-xs text-gray-500">
          合計 <span className="font-semibold text-gray-300">{sheet.total_rows.toLocaleString()}</span> 行
          {sheet.total_rows > MAX_PREVIEW_ROWS && (
            <> &nbsp;(先頭 {MAX_PREVIEW_ROWS} 行を表示)</>
          )}
        </span>
      </div>

      <div className="overflow-x-auto rounded-lg border border-gray-700">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-gray-800 sticky top-0">
              {sheet.headers.map((header) => (
                <th
                  key={header}
                  scope="col"
                  className="px-3 py-2 text-left font-medium text-gray-300 whitespace-nowrap"
                >
                  <div className="flex flex-col gap-1">
                    <span>{header}</span>
                    <span
                      className={`inline-block self-start rounded px-1.5 py-0.5 text-xs font-normal ${typeBadgeClass(sheet.types[header] ?? '')}`}
                    >
                      {sheet.types[header] ?? 'unknown'}
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
                className={rowIndex % 2 === 0 ? 'bg-gray-950' : 'bg-gray-900'}
              >
                {sheet.headers.map((header) => (
                  <td
                    key={header}
                    className="px-3 py-1.5 text-gray-200 whitespace-nowrap"
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
