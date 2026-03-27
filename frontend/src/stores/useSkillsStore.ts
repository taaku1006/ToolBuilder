import { create } from 'zustand'
import { getSkills, createSkill, deleteSkill } from '../api/skills'
import type { CreateSkillData } from '../api/skills'
import type { SkillItem, SkillSuggestion } from '../types'

interface SkillsState {
  skills: SkillItem[]
  suggestions: SkillSuggestion[]
  selectedSkillId: string | null
  loading: boolean
  error: string | null
  total: number
  fetchSkills: () => Promise<void>
  setSuggestions: (suggestions: SkillSuggestion[]) => void
  selectSkill: (id: string | null) => void
  saveSkill: (data: CreateSkillData) => Promise<void>
  removeSkill: (id: string) => Promise<void>
  reset: () => void
}

const initialState = {
  skills: [] as SkillItem[],
  suggestions: [] as SkillSuggestion[],
  selectedSkillId: null as string | null,
  loading: false,
  error: null as string | null,
  total: 0,
}

export const useSkillsStore = create<SkillsState>((set, get) => ({
  ...initialState,

  fetchSkills: async () => {
    set({ loading: true, error: null })

    try {
      const result = await getSkills()
      set({ skills: result.items, total: result.total, loading: false })
    } catch {
      set({ loading: false, error: 'スキルの取得に失敗しました。' })
    }
  },

  setSuggestions: (suggestions: SkillSuggestion[]) => {
    set({ suggestions: [...suggestions] })
  },

  selectSkill: (id: string | null) => {
    set({ selectedSkillId: id })
  },

  saveSkill: async (data: CreateSkillData) => {
    try {
      await createSkill(data)
      const result = await getSkills()
      set({ skills: result.items, total: result.total })
    } catch {
      set({ error: 'スキルの保存に失敗しました。' })
    }
  },

  removeSkill: async (id: string) => {
    try {
      await deleteSkill(id)
      const { skills, selectedSkillId } = get()
      const updatedSkills = skills.filter((skill) => skill.id !== id)
      set({
        skills: updatedSkills,
        total: updatedSkills.length,
        selectedSkillId: selectedSkillId === id ? null : selectedSkillId,
      })
    } catch {
      set({ error: 'スキルの削除に失敗しました。' })
    }
  },

  reset: () => set({ ...initialState }),
}))
