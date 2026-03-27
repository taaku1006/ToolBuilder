import client from './client'
import type { HistoryItem, HistoryListResponse } from '../types'

export interface CreateHistoryData {
  task: string
  python_code: string
  file_name?: string | null
  summary?: string | null
  steps?: string[] | null
  tips?: string | null
  memo?: string | null
  exec_stdout?: string | null
  exec_stderr?: string | null
}

export async function getHistory(query?: string): Promise<HistoryListResponse> {
  const response = await client.get<HistoryListResponse>('/history', {
    params: query != null ? { q: query } : {},
  })
  return response.data
}

export async function getHistoryItem(id: string): Promise<HistoryItem> {
  const response = await client.get<HistoryItem>(`/history/${id}`)
  return response.data
}

export async function deleteHistory(id: string): Promise<void> {
  await client.delete(`/history/${id}`)
}

export async function createHistory(data: CreateHistoryData): Promise<HistoryItem> {
  const response = await client.post<HistoryItem>('/history', data)
  return response.data
}
