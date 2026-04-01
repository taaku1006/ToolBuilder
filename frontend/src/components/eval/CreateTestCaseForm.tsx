import { useState, useRef } from 'react'
import { createTestCase } from '../../api/eval'

interface CreateTestCaseFormProps {
  onCreated: () => void
  onClose: () => void
}

export function CreateTestCaseForm({ onCreated, onClose }: CreateTestCaseFormProps) {
  const [task, setTask] = useState('')
  const [description, setDescription] = useState('')
  const [file, setFile] = useState<File | null>(null)
  const [expectedFile, setExpectedFile] = useState<File | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)
  const fileRef = useRef<HTMLInputElement>(null)
  const expectedFileRef = useRef<HTMLInputElement>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!task.trim()) return
    setSubmitting(true)
    setFormError(null)
    try {
      await createTestCase(task.trim(), description.trim(), file ?? undefined, expectedFile ?? undefined)
      setTask('')
      setDescription('')
      setFile(null)
      setExpectedFile(null)
      if (fileRef.current) fileRef.current.value = ''
      if (expectedFileRef.current) expectedFileRef.current.value = ''
      onCreated()
      onClose()
    } catch (err: unknown) {
      setFormError(err instanceof Error ? err.message : 'Failed to create')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-3 border border-gray-700 rounded-lg p-4 bg-gray-800/50">
      <div className="flex items-center justify-between">
        <div className="text-xs font-medium text-gray-400 uppercase tracking-wide">New Test Case</div>
        <button type="button" onClick={onClose} className="text-xs text-gray-600 hover:text-gray-400 transition-colors">✕</button>
      </div>

      <textarea
        placeholder="タスク指示文 (e.g. 月次品質報告書を全自動生成するコードを作ってください...)"
        value={task}
        onChange={(e) => setTask(e.target.value)}
        rows={4}
        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-600 resize-y"
      />

      <input
        type="text"
        placeholder="Description (optional, short label for this test case)"
        value={description}
        onChange={(e) => setDescription(e.target.value)}
        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-sm text-gray-200 placeholder-gray-600 focus:outline-none focus:border-blue-600"
      />

      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className="space-y-1">
          <div className="text-xs text-gray-500">Input Excel (processing target)</div>
          <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-400 hover:text-gray-200 transition-colors">
            <input
              ref={fileRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
              className="hidden"
            />
            <span className="px-3 py-1.5 bg-gray-700 rounded-lg text-xs w-full text-center">
              {file ? file.name : 'Upload Input File (.xlsx/.csv)'}
            </span>
          </label>
          {file && (
            <button
              type="button"
              onClick={() => { setFile(null); if (fileRef.current) fileRef.current.value = '' }}
              className="text-xs text-red-400 hover:text-red-300"
            >
              Clear
            </button>
          )}
        </div>

        <div className="space-y-1">
          <div className="text-xs text-gray-500">Expected Output Excel (correct answer)</div>
          <label className="flex items-center gap-2 cursor-pointer text-sm text-gray-400 hover:text-gray-200 transition-colors">
            <input
              ref={expectedFileRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={(e) => setExpectedFile(e.target.files?.[0] ?? null)}
              className="hidden"
            />
            <span className="px-3 py-1.5 bg-green-900/50 border border-green-800/50 rounded-lg text-xs w-full text-center">
              {expectedFile ? expectedFile.name : 'Upload Expected Output (.xlsx/.csv)'}
            </span>
          </label>
          {expectedFile && (
            <button
              type="button"
              onClick={() => { setExpectedFile(null); if (expectedFileRef.current) expectedFileRef.current.value = '' }}
              className="text-xs text-red-400 hover:text-red-300"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex-1" />
        <button
          type="submit"
          disabled={!task.trim() || submitting}
          className="px-4 py-1.5 bg-green-700 hover:bg-green-600 disabled:bg-gray-700 disabled:text-gray-500 text-white rounded-lg text-xs font-medium transition-colors"
        >
          {submitting ? 'Creating...' : 'Add Test Case'}
        </button>
      </div>

      {formError && (
        <div className="text-xs text-red-400">{formError}</div>
      )}
    </form>
  )
}
