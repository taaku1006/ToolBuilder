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
          'flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed px-6 py-10 transition-colors',
          loading
            ? 'cursor-not-allowed border-gray-700 bg-gray-900 opacity-60'
            : isDragging
              ? 'border-blue-500 bg-blue-950/30 cursor-pointer'
              : 'border-gray-600 bg-gray-900 hover:border-gray-400 cursor-pointer',
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
            <p className="text-sm font-medium text-gray-200">{file?.name}</p>
            <p className="text-xs text-gray-500">クリックまたはドロップで差し替え</p>
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
            <p className="text-sm text-gray-300">
              クリックまたはドロップしてファイルを選択
            </p>
            <p className="text-xs text-gray-500">
              対応形式: xlsx / xls / csv &nbsp;|&nbsp; 最大 50MB
            </p>
          </>
        )}
      </div>

      {displayError && (
        <div
          role="alert"
          className="mt-2 rounded-md bg-red-950 border border-red-800 px-4 py-2 text-sm text-red-300"
        >
          {displayError}
        </div>
      )}
    </div>
  )
}
