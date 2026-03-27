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
