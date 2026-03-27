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
