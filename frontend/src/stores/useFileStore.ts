import { create } from 'zustand'
import { uploadFile } from '../api/upload'
import type { UploadResponse } from '../types'
import { useSkillsStore } from './useSkillsStore'

interface FileState {
  file: File | null
  uploadResponse: UploadResponse | null
  activeSheet: number
  loading: boolean
  error: string | null
  upload: (file: File) => Promise<void>
  setActiveSheet: (index: number) => void
  reset: () => void
}

const initialState = {
  file: null,
  uploadResponse: null,
  activeSheet: 0,
  loading: false,
  error: null,
}

export const useFileStore = create<FileState>((set) => ({
  ...initialState,

  upload: async (file: File) => {
    set({ loading: true, error: null, activeSheet: 0 })

    try {
      const uploadResponse = await uploadFile(file)
      set({ file, uploadResponse, loading: false })
      if (uploadResponse.suggested_skills != null && uploadResponse.suggested_skills.length > 0) {
        useSkillsStore.getState().setSuggestions(uploadResponse.suggested_skills)
      }
    } catch {
      set({
        loading: false,
        error: 'ファイルのアップロードに失敗しました。もう一度お試しください。',
      })
    }
  },

  setActiveSheet: (index: number) => set({ activeSheet: index }),

  reset: () => set({ ...initialState }),
}))
