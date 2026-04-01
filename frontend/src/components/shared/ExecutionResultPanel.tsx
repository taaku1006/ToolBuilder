interface ExecutionResultPanelProps {
  stdout?: string
  stderr?: string
  outputFiles?: string[]
  success: boolean
  elapsedMs: number
}

export function ExecutionResultPanel({
  stdout,
  stderr,
  outputFiles,
  success,
  elapsedMs,
}: ExecutionResultPanelProps) {
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3">
        {success ? (
          <span className="px-2 py-0.5 text-xs font-medium bg-green-900 text-green-300 rounded">
            成功
          </span>
        ) : (
          <span className="px-2 py-0.5 text-xs font-medium bg-red-900 text-red-300 rounded">
            エラー
          </span>
        )}
        <span className="text-xs text-gray-500">{`${elapsedMs}ms`}</span>
      </div>

      {stdout && (
        <div>
          <p className="text-xs text-gray-500 mb-1">stdout</p>
          <pre data-testid="exec-stdout" className="bg-gray-900 rounded p-3 text-sm text-green-300 font-mono overflow-x-auto max-h-40 overflow-y-auto">
            {stdout}
          </pre>
        </div>
      )}

      {stderr && (
        <div>
          <p className="text-xs text-gray-500 mb-1">stderr</p>
          <pre className="bg-gray-900 rounded p-3 text-sm text-red-400 font-mono overflow-x-auto max-h-40 overflow-y-auto">
            {stderr}
          </pre>
        </div>
      )}

      {outputFiles && outputFiles.length > 0 && (
        <div>
          <p className="text-xs text-gray-500 mb-2">出力ファイル</p>
          <div className="flex flex-wrap gap-2">
            {outputFiles.map((filePath) => {
              const fileName = filePath.split('/').pop() ?? filePath
              return (
                <a
                  key={filePath}
                  href={`/api/download/${filePath}`}
                  download={fileName}
                  className="inline-flex items-center gap-2 px-3 py-1.5 text-sm bg-blue-900 hover:bg-blue-800 text-blue-200 rounded transition-colors"
                >
                  <span aria-hidden="true">&#8595;</span>
                  <span>{fileName}</span>
                </a>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}
