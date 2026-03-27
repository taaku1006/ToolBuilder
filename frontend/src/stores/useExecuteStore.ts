import { create } from 'zustand'
import { postExecute } from '../api/execute'
import type { ExecuteResponse } from '../types'

interface ExecuteState {
  executeResponse: ExecuteResponse | null
  executing: boolean
  executeError: string | null
  execute: (code: string, fileId?: string) => Promise<void>
  reset: () => void
}

const initialState = {
  executeResponse: null as ExecuteResponse | null,
  executing: false,
  executeError: null as string | null,
}

export const useExecuteStore = create<ExecuteState>((set) => ({
  ...initialState,

  execute: async (code: string, fileId?: string) => {
    if (!code.trim()) return

    set({ executing: true, executeError: null })

    try {
      const executeResponse = await postExecute(code, fileId)
      set({ executeResponse, executing: false })
    } catch {
      set({
        executing: false,
        executeError: '実行に失敗しました。',
      })
    }
  },

  reset: () => set({ ...initialState }),
}))
