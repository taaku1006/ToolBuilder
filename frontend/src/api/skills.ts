import client from './client'
import type { SkillItem, SkillsListResponse } from '../types'

export interface CreateSkillData {
  title: string
  tags: string[]
  python_code: string
  file_schema?: string | null
  task_summary?: string | null
}

export async function getSkills(): Promise<SkillsListResponse> {
  const response = await client.get<SkillsListResponse>('/skills')
  return response.data
}

export async function getSkill(id: string): Promise<SkillItem> {
  const response = await client.get<SkillItem>(`/skills/${id}`)
  return response.data
}

export async function createSkill(data: CreateSkillData): Promise<SkillItem> {
  const response = await client.post<SkillItem>('/skills', data)
  return response.data
}

export async function deleteSkill(id: string): Promise<void> {
  await client.delete(`/skills/${id}`)
}
