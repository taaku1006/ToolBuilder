import { Header } from './components/layout/Header'
import { TaskInput } from './components/TaskInput'
import { CodeResult } from './components/CodeResult'
import { useGenerateStore } from './stores/useGenerateStore'

function App() {
  const { error } = useGenerateStore()

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Header />
      <main className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        <TaskInput />
        {error && (
          <div className="bg-red-950 border border-red-800 text-red-300 rounded-lg px-4 py-3 text-sm">
            {error}
          </div>
        )}
        <CodeResult />
      </main>
    </div>
  )
}

export default App
