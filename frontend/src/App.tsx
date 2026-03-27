import { Header } from './components/layout/Header'
import { Sidebar } from './components/layout/Sidebar'
import { SkillsPanel } from './components/SkillsPanel'
import { FileUpload } from './components/FileUpload'
import { SheetPreview } from './components/SheetPreview'
import { TaskInput } from './components/TaskInput'
import { AgentLog } from './components/AgentLog'
import { DebugLog } from './components/DebugLog'
import { CodeResult } from './components/CodeResult'
import { useGenerateStore } from './stores/useGenerateStore'
import { useFileStore } from './stores/useFileStore'

function App() {
  const { error, agentLog } = useGenerateStore()
  const { uploadResponse } = useFileStore()
  const fileId = uploadResponse?.file_id

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <div className="w-72 bg-gray-900 border-r border-gray-800 flex flex-col h-full overflow-y-auto">
          <Sidebar />
          <SkillsPanel />
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
            <AgentLog agentLog={agentLog} />
            <DebugLog agentLog={agentLog} />
            <CodeResult />
          </div>
        </main>
      </div>
    </div>
  )
}

export default App
