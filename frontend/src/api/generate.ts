import client from './client'
import type { GenerateResponse } from '../types'

export async function postGenerate(task: string, fileId?: string): Promise<GenerateResponse> {
  const response = await client.post<GenerateResponse>('/generate', {
    task,
    ...(fileId != null ? { file_id: fileId } : {}),
  })
  return response.data
}
