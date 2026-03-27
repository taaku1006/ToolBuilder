import client from './client'
import type { GenerateResponse } from '../types'

export async function postGenerate(task: string): Promise<GenerateResponse> {
  const response = await client.post<GenerateResponse>('/generate', { task })
  return response.data
}
