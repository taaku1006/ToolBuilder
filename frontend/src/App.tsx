import { useState } from 'react'
import { Header } from './components/layout/Header'
import { Sidebar } from './components/layout/Sidebar'
import { FileUpload } from './components/FileUpload'
import { SheetPreview } from './components/SheetPreview'
import { TaskInput } from './components/TaskInput'
import { AgentLog } from './components/AgentLog'
import { DebugLog } from './components/DebugLog'
import { CodeResult } from './components/CodeResult'
import { ToolDashboard } from './components/ToolDashboard'
import { EvalDashboard } from './components/EvalDashboard'
import { useGenerateStore } from './stores/useGenerateStore'
import { useFileStore } from './stores/useFileStore'

function BuilderPage() {
  const { error, agentLog } = useGenerateStore()
  const { uploadResponse } = useFileStore()
  const fileId = uploadResponse?.file_id
  const [showDetails, setShowDetails] = useState(false)

  return (
    <div className="flex flex-1 overflow-hidden">
      <div className="w-72 bg-gray-900 border-r border-gray-800 flex flex-col h-full overflow-y-auto">
        <Sidebar />
      </div>
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-4xl mx-auto px-6 py-8 space-y-6">
          <FileUpload />
          <SheetPreview />
          <TaskInput fileId={fileId} />
          {error && (
            <div className="bg-red-950 border border-red-800 text-red-300 rounded-lg px-4 py-3 text-sm">
              {error}
            </div>
          )}
          <CodeResult />
          {agentLog.length > 0 && (
            <div className="border-t border-gray-800 pt-4">
              <button
                className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
                onClick={() => setShowDetails(!showDetails)}
              >
                {showDetails ? '▼' : '▶'} 技術的な詳細を{showDetails ? '隠す' : '表示'}
              </button>
              {showDetails && (
                <div className="mt-3 space-y-4">
                  <AgentLog agentLog={agentLog} />
                  <DebugLog agentLog={agentLog} />
                </div>
              )}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}

function App() {
  const [page, setPage] = useState<'builder' | 'dashboard' | 'eval'>('builder')

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      <Header page={page} onNavigate={setPage} />
      {page === 'builder' ? (
        <BuilderPage />
      ) : page === 'dashboard' ? (
        <ToolDashboard onBack={() => setPage('builder')} />
      ) : (
        <EvalDashboard />
      )}
    </div>
  )
}

export default App
