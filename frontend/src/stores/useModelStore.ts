import { create } from 'zustand'
import { getModels } from '../api/models'
import type { ModelInfo } from '../api/models'

interface ModelState {
  models: ModelInfo[]
  defaultModel: string
  stageDefaults: Record<string, string>
  selectedModel: string | null
  stageOverrides: Record<string, string>
  loaded: boolean
  loading: boolean
  fetchModels: () => Promise<void>
  setSelectedModel: (model: string | null) => void
  setStageOverride: (stage: string, model: string) => void
  clearOverrides: () => void
}

export const useModelStore = create<ModelState>((set, get) => ({
  models: [],
  defaultModel: '',
  stageDefaults: {},
  selectedModel: null,
  stageOverrides: {},
  loaded: false,
  loading: false,

  fetchModels: async () => {
    if (get().loaded || get().loading) return
    set({ loading: true })
    try {
      const res = await getModels()
      set({
        models: res.models,
        defaultModel: res.default_model,
        stageDefaults: res.stage_defaults,
        loaded: true,
        loading: false,
      })
    } catch {
      set({ loading: false })
    }
  },

  setSelectedModel: (model) => set({ selectedModel: model }),

  setStageOverride: (stage, model) =>
    set((state) => ({
      stageOverrides: { ...state.stageOverrides, [stage]: model },
    })),

  clearOverrides: () => set({ selectedModel: null, stageOverrides: {} }),
}))
