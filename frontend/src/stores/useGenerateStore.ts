import { create } from 'zustand'
import { postGenerate } from '../api/generate'
import type { GenerateResponse } from '../types'

interface GenerateState {
  task: string
  response: GenerateResponse | null
  loading: boolean
  error: string | null
  setTask: (task: string) => void
  generate: () => Promise<void>
  reset: () => void
}

const initialState = {
  task: '',
  response: null,
  loading: false,
  error: null,
}

export const useGenerateStore = create<GenerateState>((set, get) => ({
  ...initialState,

  setTask: (task) => set({ task }),

  generate: async () => {
    const { task } = get()
    if (!task.trim()) return

    set({ loading: true, error: null })

    try {
      const response = await postGenerate(task)
      set({ response, loading: false })
    } catch {
      set({
        loading: false,
        error: 'コード生成に失敗しました。もう一度お試しください。',
      })
    }
  },

  reset: () => set({ ...initialState }),
}))
