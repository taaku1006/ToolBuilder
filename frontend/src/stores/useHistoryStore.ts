import { create } from 'zustand'
import { getHistory, deleteHistory } from '../api/history'
import type { HistoryItem } from '../types'

interface HistoryState {
  items: HistoryItem[]
  total: number
  selectedId: string | null
  searchQuery: string
  loading: boolean
  error: string | null
  fetchHistory: (query?: string) => Promise<void>
  selectItem: (id: string) => void
  deleteItem: (id: string) => Promise<void>
  setSearchQuery: (query: string) => void
  reset: () => void
}

const initialState = {
  items: [] as HistoryItem[],
  total: 0,
  selectedId: null as string | null,
  searchQuery: '',
  loading: false,
  error: null as string | null,
}

export const useHistoryStore = create<HistoryState>((set, get) => ({
  ...initialState,

  fetchHistory: async (query?: string) => {
    set({ loading: true, error: null })

    try {
      const result = await getHistory(query)
      set({ items: result.items, total: result.total, loading: false })
    } catch {
      set({ loading: false, error: '履歴の取得に失敗しました。' })
    }
  },

  selectItem: (id: string) => set({ selectedId: id }),

  deleteItem: async (id: string) => {
    try {
      await deleteHistory(id)
      const { items, selectedId } = get()
      const updatedItems = items.filter((item) => item.id !== id)
      set({
        items: updatedItems,
        total: updatedItems.length,
        selectedId: selectedId === id ? null : selectedId,
      })
    } catch {
      set({ error: '履歴の削除に失敗しました。' })
    }
  },

  setSearchQuery: (query: string) => set({ searchQuery: query }),

  reset: () => set({ ...initialState }),
}))
