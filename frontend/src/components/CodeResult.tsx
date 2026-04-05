import { useState } from 'react'
import { useGenerateStore } from '../stores/useGenerateStore'
import { useExecuteStore } from '../stores/useExecuteStore'
import { useFileStore } from '../stores/useFileStore'
import { downloadAsZip } from '../utils/download'
import { ExecutionResultPanel } from './shared/ExecutionResultPanel'

export function CodeResult() {
  const { response } = useGenerateStore()
  const { executeResponse, executing, executeError, execute } = useExecuteStore()
  const { uploadResponse } = useFileStore()
  const [copied, setCopied] = useState(false)
  const [showCode, setShowCode] = useState(false)

  if (!response) return null

  const handleCopy = async () => {
    await navigator.clipboard.writeText(response.python_code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleExecute = () => {
    void execute(response.python_code, uploadResponse?.file_id)
  }

  const handleDownloadTool = () => {
    void downloadAsZip(response.python_code, response.summary, response.steps)
  }

  return (
    <div className="w-full space-y-3">
      <div className="border border-gray-800 rounded-lg bg-gray-900/50 p-3">
        <h2 className="text-xs uppercase tracking-wide text-gray-500 mb-1">Summary</h2>
        <p className="text-gray-200 text-xs">{response.summary}</p>
      </div>

      {response.steps.length > 0 && (
        <div className="border border-gray-800 rounded-lg bg-gray-900/50 p-3">
          <h2 className="text-xs uppercase tracking-wide text-gray-500 mb-2">Steps</h2>
          <ol className="space-y-1 list-decimal list-inside">
            {response.steps.map((step, index) => (
              <li key={index} className="text-gray-300 text-xs">
                {step}
              </li>
            ))}
          </ol>
        </div>
      )}

      <div className="border border-gray-800 rounded-lg bg-gray-950/50 overflow-hidden">
        <div className="flex items-center justify-between px-3 py-1.5 bg-gray-900/80 border-b border-gray-800">
          <button
            className="text-[10px] text-gray-500 font-mono hover:text-gray-300 transition-colors"
            onClick={() => setShowCode(!showCode)}
          >
            {showCode ? '[-]' : '[+]'} code
          </button>
          <div className="flex items-center gap-1.5">
            <button
              className="px-2 py-0.5 text-[10px] bg-gray-800 hover:bg-gray-700 text-gray-400 rounded transition-colors font-mono"
              onClick={handleCopy}
            >
              {copied ? 'copied' : 'copy'}
            </button>
            <button
              className="px-2 py-0.5 text-[10px] bg-green-900/80 hover:bg-green-800 text-green-300 rounded transition-colors font-mono disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1"
              onClick={handleExecute}
              disabled={executing}
            >
              {executing ? (
                <>
                  <span
                    data-testid="execute-spinner"
                    className="inline-block w-2.5 h-2.5 border border-green-300 border-t-transparent rounded-full animate-spin"
                  />
                  running
                </>
              ) : (
                'run'
              )}
            </button>
          </div>
        </div>
        {showCode && (
          <pre className="p-3 overflow-x-auto text-xs text-green-300/80 font-mono leading-relaxed">
            <code>{response.python_code}</code>
          </pre>
        )}
      </div>

      {executeError && (
        <div className="bg-red-950/50 border border-red-900 text-red-300 rounded-lg px-3 py-2 text-xs font-mono">
          {executeError}
        </div>
      )}

      {executeResponse && (
        <div className="border border-gray-800 rounded-lg bg-gray-900/50 p-3 space-y-2">
          <h2 className="text-xs uppercase tracking-wide text-gray-500">Result</h2>

          <ExecutionResultPanel
            success={executeResponse.success}
            elapsedMs={executeResponse.elapsed_ms}
            stdout={executeResponse.stdout || undefined}
            stderr={executeResponse.stderr || undefined}
            outputFiles={executeResponse.output_files}
          />

          {executeResponse.success && (
            <div className="space-y-1.5">
              <button
                className="px-3 py-1.5 text-xs bg-purple-900/60 hover:bg-purple-800/60 text-purple-300 rounded transition-colors font-medium"
                onClick={handleDownloadTool}
              >
                Download as Tool
              </button>
              <p className="text-[10px] text-gray-600">
                Extract zip, then double-click run.bat or drag-and-drop Excel files
              </p>
            </div>
          )}
        </div>
      )}

      {response.tips && (
        <div className="bg-yellow-950/30 border border-yellow-900/50 rounded-lg px-3 py-2">
          <h2 className="text-[10px] uppercase tracking-wide text-yellow-500 mb-0.5">Tips</h2>
          <p className="text-yellow-200/80 text-xs">{response.tips}</p>
        </div>
      )}
    </div>
  )
}
