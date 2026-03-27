import client from './client'
import type { ExecuteResponse } from '../types'

export async function postExecute(code: string, fileId?: string): Promise<ExecuteResponse> {
  const response = await client.post<ExecuteResponse>('/execute', {
    code,
    ...(fileId != null ? { file_id: fileId } : {}),
  })
  return response.data
}
