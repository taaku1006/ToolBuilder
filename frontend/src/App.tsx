import { Header } from './components/layout/Header'
import { Sidebar } from './components/layout/Sidebar'
import { FileUpload } from './components/FileUpload'
import { SheetPreview } from './components/SheetPreview'
import { TaskInput } from './components/TaskInput'
import { CodeResult } from './components/CodeResult'
import { useGenerateStore } from './stores/useGenerateStore'
import { useFileStore } from './stores/useFileStore'

function App() {
  const { error } = useGenerateStore()
  const { uploadResponse } = useFileStore()
  const fileId = uploadResponse?.file_id

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100 flex flex-col">
      <Header />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
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
          </div>
        </main>
      </div>
    </div>
  )
}

export default App
