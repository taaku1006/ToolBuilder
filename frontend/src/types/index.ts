export interface GenerateRequest {
  task: string
  file_id?: string
  max_steps?: number
  skill_id?: string
}

export interface GenerateResponse {
  id: string
  summary: string
  python_code: string
  steps: string[]
  tips: string
}

export interface SheetInfo {
  name: string
  total_rows: number
  headers: string[]
  types: Record<string, string>
  preview: Record<string, string | number | null>[]
}

export interface UploadResponse {
  file_id: string
  filename: string
  sheets: SheetInfo[]
}

export interface ExecuteRequest {
  code: string
  file_id?: string
}

export interface ExecuteResponse {
  stdout: string
  stderr: string
  elapsed_ms: number
  output_files: string[]
  success: boolean
}

export interface HistoryItem {
  id: string
  created_at: string
  task: string
  file_name: string | null
  summary: string | null
  python_code: string
  steps: string[] | null
  tips: string | null
  memo: string | null
  exec_stdout: string | null
  exec_stderr: string | null
}

export interface HistoryListResponse {
  items: HistoryItem[]
  total: number
}
