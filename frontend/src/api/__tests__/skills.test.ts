import { describe, it, expect, vi, beforeEach } from 'vitest'
import { getSkills, getSkill, createSkill, deleteSkill } from '../skills'
import client from '../client'
import type { SkillItem, SkillsListResponse } from '../../types'

vi.mock('../client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

const mockSkillItem: SkillItem = {
  id: 'skill-001',
  created_at: '2026-03-27T10:00:00Z',
  title: 'Excel集計スキル',
  tags: ['excel', 'pandas'],
  python_code: 'import pandas as pd\ndf = pd.read_excel("data.xlsx")',
  file_schema: '{"columns": ["A", "B"]}',
  task_summary: 'Excelファイルを読み込んで集計します',
  use_count: 5,
  success_rate: 0.9,
}

const mockSkillItem2: SkillItem = {
  id: 'skill-002',
  created_at: '2026-03-27T11:00:00Z',
  title: 'CSV変換スキル',
  tags: ['csv'],
  python_code: 'import csv',
  file_schema: null,
  task_summary: null,
  use_count: 2,
  success_rate: 1.0,
}

const mockListResponse: SkillsListResponse = {
  items: [mockSkillItem, mockSkillItem2],
  total: 2,
}

describe('getSkills', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls GET /skills', async () => {
    vi.mocked(client.get).mockResolvedValueOnce({ data: mockListResponse })

    await getSkills()

    expect(client.get).toHaveBeenCalledWith('/skills')
  })

  it('returns SkillsListResponse from the API', async () => {
    vi.mocked(client.get).mockResolvedValueOnce({ data: mockListResponse })

    const result = await getSkills()

    expect(result).toEqual(mockListResponse)
  })

  it('returns empty list when no skills exist', async () => {
    const emptyResponse: SkillsListResponse = { items: [], total: 0 }
    vi.mocked(client.get).mockResolvedValueOnce({ data: emptyResponse })

    const result = await getSkills()

    expect(result.items).toHaveLength(0)
    expect(result.total).toBe(0)
  })

  it('propagates errors from the API client', async () => {
    vi.mocked(client.get).mockRejectedValueOnce(new Error('Network Error'))

    await expect(getSkills()).rejects.toThrow('Network Error')
  })
})

describe('getSkill', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls GET /skills/:id with the correct id', async () => {
    vi.mocked(client.get).mockResolvedValueOnce({ data: mockSkillItem })

    await getSkill('skill-001')

    expect(client.get).toHaveBeenCalledWith('/skills/skill-001')
  })

  it('returns a SkillItem from the API', async () => {
    vi.mocked(client.get).mockResolvedValueOnce({ data: mockSkillItem })

    const result = await getSkill('skill-001')

    expect(result).toEqual(mockSkillItem)
  })

  it('propagates 404 errors', async () => {
    vi.mocked(client.get).mockRejectedValueOnce(new Error('Not Found'))

    await expect(getSkill('nonexistent')).rejects.toThrow('Not Found')
  })
})

describe('createSkill', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls POST /skills with the provided data', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockSkillItem })

    const data = {
      title: 'Excel集計スキル',
      tags: ['excel', 'pandas'],
      python_code: 'import pandas as pd',
      file_schema: '{"columns": ["A"]}',
      task_summary: '集計処理',
    }

    await createSkill(data)

    expect(client.post).toHaveBeenCalledWith('/skills', data)
  })

  it('returns the created SkillItem', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockSkillItem })

    const result = await createSkill({
      title: 'Excel集計スキル',
      tags: ['excel'],
      python_code: 'import pandas as pd',
    })

    expect(result).toEqual(mockSkillItem)
  })

  it('handles minimal required fields (no file_schema, no task_summary)', async () => {
    vi.mocked(client.post).mockResolvedValueOnce({ data: mockSkillItem })

    const data = { title: 'Simple', tags: [], python_code: 'pass' }
    await createSkill(data)

    expect(client.post).toHaveBeenCalledWith('/skills', data)
  })

  it('propagates errors from the API client', async () => {
    vi.mocked(client.post).mockRejectedValueOnce(new Error('Validation Error'))

    await expect(
      createSkill({ title: 'x', tags: [], python_code: 'pass' }),
    ).rejects.toThrow('Validation Error')
  })
})

describe('deleteSkill', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('calls DELETE /skills/:id with the correct id', async () => {
    vi.mocked(client.delete).mockResolvedValueOnce({ data: null })

    await deleteSkill('skill-001')

    expect(client.delete).toHaveBeenCalledWith('/skills/skill-001')
  })

  it('resolves without a value on success', async () => {
    vi.mocked(client.delete).mockResolvedValueOnce({ data: null })

    const result = await deleteSkill('skill-001')

    expect(result).toBeUndefined()
  })

  it('propagates errors from the API client', async () => {
    vi.mocked(client.delete).mockRejectedValueOnce(new Error('Forbidden'))

    await expect(deleteSkill('skill-001')).rejects.toThrow('Forbidden')
  })
})
