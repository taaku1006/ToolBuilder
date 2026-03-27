import { useState } from 'react'
import { useGenerateStore } from '../stores/useGenerateStore'
import { useExecuteStore } from '../stores/useExecuteStore'

export function CodeResult() {
  const { response } = useGenerateStore()
  const { executeResponse, executing, executeError, execute } = useExecuteStore()
  const [copied, setCopied] = useState(false)

  if (!response) return null

  const handleCopy = async () => {
    await navigator.clipboard.writeText(response.python_code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleExecute = () => {
    void execute(response.python_code, undefined)
  }

  return (
    <div className="w-full space-y-4">
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-2">
          概要
        </h2>
        <p className="text-gray-100 text-sm">{response.summary}</p>
      </div>

      {response.steps.length > 0 && (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
            実行ステップ
          </h2>
          <ol className="space-y-1.5 list-decimal list-inside">
            {response.steps.map((step, index) => (
              <li key={index} className="text-gray-200 text-sm">
                {step}
              </li>
            ))}
          </ol>
        </div>
      )}

      <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
          <span className="text-xs text-gray-400 font-medium">Python</span>
          <div className="flex items-center gap-2">
            <button
              className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 rounded transition-colors"
              onClick={handleCopy}
            >
              {copied ? 'コピー済み' : 'コピー'}
            </button>
            <button
              className="px-3 py-1 text-xs bg-green-700 hover:bg-green-600 text-white rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
              onClick={handleExecute}
              disabled={executing}
            >
              {executing ? (
                <>
                  <span
                    data-testid="execute-spinner"
                    className="inline-block w-3 h-3 border border-white border-t-transparent rounded-full animate-spin"
                  />
                  実行中
                </>
              ) : (
                '実行'
              )}
            </button>
          </div>
        </div>
        <pre className="p-4 overflow-x-auto text-sm text-green-300 font-mono leading-relaxed">
          <code>{response.python_code}</code>
        </pre>
      </div>

      {executeError && (
        <div className="bg-red-950 border border-red-800 text-red-300 rounded-lg px-4 py-3 text-sm">
          {executeError}
        </div>
      )}

      {executeResponse && (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider">
              実行結果
            </h2>
            <div className="flex items-center gap-3">
              <span className="text-xs text-gray-500">{executeResponse.elapsed_ms}ms</span>
              {executeResponse.success ? (
                <span className="px-2 py-0.5 text-xs font-medium bg-green-900 text-green-300 rounded">
                  成功
                </span>
              ) : (
                <span className="px-2 py-0.5 text-xs font-medium bg-red-900 text-red-300 rounded">
                  エラー
                </span>
              )}
            </div>
          </div>

          {executeResponse.stdout && (
            <div>
              <p className="text-xs text-gray-500 mb-1">stdout</p>
              <pre data-testid="exec-stdout" className="bg-gray-900 rounded p-3 text-sm text-green-300 font-mono overflow-x-auto">
                {executeResponse.stdout}
              </pre>
            </div>
          )}

          {executeResponse.stderr && (
            <div>
              <p className="text-xs text-gray-500 mb-1">stderr</p>
              <pre className="bg-gray-900 rounded p-3 text-sm text-red-400 font-mono overflow-x-auto">
                {executeResponse.stderr}
              </pre>
            </div>
          )}

          {executeResponse.output_files.length > 0 && (
            <div>
              <p className="text-xs text-gray-500 mb-2">出力ファイル</p>
              <ul className="space-y-1">
                {executeResponse.output_files.map((filename) => (
                  <li key={filename} className="text-sm text-blue-400 font-mono">
                    {filename}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {response.tips && (
        <div className="bg-yellow-950 border border-yellow-800 rounded-lg p-4">
          <h2 className="text-sm font-semibold text-yellow-400 mb-1">ヒント</h2>
          <p className="text-yellow-200 text-sm">{response.tips}</p>
        </div>
      )}
    </div>
  )
}
