import { useRef, useState } from 'react'
import { useFileStore } from '../stores/useFileStore'

const MAX_FILE_SIZE = 50 * 1024 * 1024
const ACCEPTED_TYPES = '.xlsx,.xls,.csv'

export function FileUpload() {
  const { file, uploadResponse, loading, error, upload } = useFileStore()
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [sizeError, setSizeError] = useState<string | null>(null)

  const processFile = (selectedFile: File) => {
    if (selectedFile.size > MAX_FILE_SIZE) {
      setSizeError('ファイルサイズは50MB以下にしてください')
      return
    }
    setSizeError(null)
    upload(selectedFile)
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = e.target.files?.[0]
    if (selected) {
      processFile(selected)
    }
    e.target.value = ''
  }

  const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    if (!loading) setIsDragging(true)
  }

  const handleDragLeave = () => {
    setIsDragging(false)
  }

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault()
    setIsDragging(false)
    if (loading) return
    const dropped = e.dataTransfer.files[0]
    if (dropped) {
      processFile(dropped)
    }
  }

  const handleClick = () => {
    if (!loading) {
      inputRef.current?.click()
    }
  }

  const displayError = sizeError ?? error

  return (
    <div className="w-full">
      <div
        data-testid="drop-zone"
        onClick={handleClick}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={[
          'flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed px-4 py-6 transition-colors',
          loading
            ? 'cursor-not-allowed border-gray-800 bg-gray-950 opacity-60'
            : isDragging
              ? 'border-blue-500 bg-blue-950/20 cursor-pointer'
              : 'border-gray-700 bg-gray-900/50 hover:border-gray-600 cursor-pointer',
        ].join(' ')}
      >
        <input
          ref={inputRef}
          type="file"
          accept={ACCEPTED_TYPES}
          className="hidden"
          onChange={handleChange}
          disabled={loading}
        />

        {loading ? (
          <span
            data-testid="upload-spinner"
            className="h-8 w-8 animate-spin rounded-full border-4 border-gray-600 border-t-blue-500"
          />
        ) : uploadResponse ? (
          <>
            <svg
              className="h-8 w-8 text-green-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
            <p className="text-xs font-medium font-mono text-gray-300">{file?.name}</p>
            <p className="text-[10px] text-gray-600">Drop or click to replace</p>
          </>
        ) : (
          <>
            <svg
              className="h-8 w-8 text-gray-400"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"
              />
            </svg>
            <p className="text-xs text-gray-400">
              Drop file or click to browse
            </p>
            <p className="text-[10px] text-gray-600 font-mono">
              .xlsx .xls .csv | max 50MB
            </p>
          </>
        )}
      </div>

      {displayError && (
        <div
          role="alert"
          className="mt-1.5 rounded bg-red-950/50 border border-red-900 px-3 py-1.5 text-xs text-red-300 font-mono"
        >
          {displayError}
        </div>
      )}
    </div>
  )
}
