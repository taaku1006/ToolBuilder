import { useState } from 'react'
import { useGenerateStore } from '../stores/useGenerateStore'

export function CodeResult() {
  const { response } = useGenerateStore()
  const [copied, setCopied] = useState(false)

  if (!response) return null

  const handleCopy = async () => {
    await navigator.clipboard.writeText(response.python_code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
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
          <button
            className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 rounded transition-colors"
            onClick={handleCopy}
          >
            {copied ? 'コピー済み' : 'コピー'}
          </button>
        </div>
        <pre className="p-4 overflow-x-auto text-sm text-green-300 font-mono leading-relaxed">
          <code>{response.python_code}</code>
        </pre>
      </div>

      {response.tips && (
        <div className="bg-yellow-950 border border-yellow-800 rounded-lg p-4">
          <h2 className="text-sm font-semibold text-yellow-400 mb-1">ヒント</h2>
          <p className="text-yellow-200 text-sm">{response.tips}</p>
        </div>
      )}
    </div>
  )
}
