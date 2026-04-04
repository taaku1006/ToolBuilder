import { create } from 'zustand'
import { postGenerate } from '../api/generate'
import { createHistory } from '../api/history'
import { createSkill } from '../api/skills'
import { useHistoryStore } from './useHistoryStore'
import { useSkillsStore } from './useSkillsStore'
import type { GenerateResponse, AgentLogEntry } from '../types'

interface GenerateState {
  task: string
  response: GenerateResponse | null
  loading: boolean
  error: string | null
  agentLog: AgentLogEntry[]
  isStreaming: boolean
  setTask: (task: string) => void
  generate: (fileId?: string) => Promise<void>
  generateSSE: (fileId?: string) => Promise<void>
  reset: () => void
  addLogEntry: (entry: AgentLogEntry) => void
  setStreaming: (streaming: boolean) => void
}

const initialState = {
  task: '',
  response: null,
  loading: false,
  error: null,
  agentLog: [] as AgentLogEntry[],
  isStreaming: false,
}

export const useGenerateStore = create<GenerateState>((set, get) => ({
  ...initialState,

  setTask: (task) => set({ task }),

  addLogEntry: (entry) =>
    set((state) => ({ agentLog: [...state.agentLog, entry] })),

  setStreaming: (streaming) => set({ isStreaming: streaming }),

  generate: async (fileId?: string) => {
    const { task } = get()
    if (!task.trim()) return

    set({ loading: true, error: null })

    try {
      const response = await postGenerate(task, fileId)
      set({ response, loading: false })
    } catch {
      set({
        loading: false,
        error: 'コード生成に失敗しました。もう一度お試しください。',
      })
    }
  },

  generateSSE: async (fileId?: string) => {
    const { task } = get()
    if (!task.trim()) return

    set({ loading: true, error: null, agentLog: [], isStreaming: true })

    const body: Record<string, string> = { task }
    if (fileId != null) {
      body['file_id'] = fileId
    }

    try {
      const fetchResponse = await fetch('/api/generate', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Accept': 'text/event-stream',
        },
        body: JSON.stringify(body),
      })

      if (!fetchResponse.ok) {
        set({
          loading: false,
          isStreaming: false,
          error: 'コード生成に失敗しました。もう一度お試しください。',
        })
        return
      }

      if (fetchResponse.body == null) {
        set({
          loading: false,
          isStreaming: false,
          error: 'コード生成に失敗しました。もう一度お試しください。',
        })
        return
      }

      const reader = fetchResponse.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        let boundary: number
        while ((boundary = buffer.indexOf('\n\n')) !== -1) {
          const message = buffer.slice(0, boundary)
          buffer = buffer.slice(boundary + 2)

          for (const line of message.split('\n')) {
            if (!line.startsWith('data:')) continue

            const json = line.slice(5).trim()
            let parsed: AgentLogEntry
            try {
              parsed = JSON.parse(json) as AgentLogEntry
            } catch {
              continue
            }

            // Phase C complete carries the final generated code
            if (parsed.phase === 'C' && parsed.action === 'complete') {
              const data = parsed as unknown as Record<string, unknown>
              const result: GenerateResponse = {
                id: (data.id as string) || '',
                summary: (data.summary as string) || '',
                python_code: (data.python_code as string) || '',
                steps: (data.steps as string[]) || [],
                tips: (data.tips as string) || '',
              }
              set({ response: result })

              // Auto-save history
              try {
                await createHistory({
                  task,
                  python_code: result.python_code,
                  summary: result.summary || null,
                  steps: result.steps.length > 0 ? result.steps : null,
                  tips: result.tips || null,
                })
                void useHistoryStore.getState().fetchHistory()
              } catch {
                // History save failure is non-critical
              }
            } else if (parsed.phase === 'L' && parsed.action === 'complete') {
              // Learn phase complete — no action needed, logged for SSE display
              try {
                // Skill save failure is non-critical
              }
              set((state) => ({ agentLog: [...state.agentLog, parsed] }))
            } else if (parsed.action === 'error') {
              set((state) => ({ agentLog: [...state.agentLog, parsed] }))
            } else {
              set((state) => ({ agentLog: [...state.agentLog, parsed] }))
            }
          }
        }
      }
    } catch {
      set({ error: 'コード生成に失敗しました。もう一度お試しください。' })
    } finally {
      set({ loading: false, isStreaming: false })
    }
  },

  reset: () => set({ ...initialState, agentLog: [], isStreaming: false }),
}))
