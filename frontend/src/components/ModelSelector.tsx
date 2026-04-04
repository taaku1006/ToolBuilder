import { useState, useEffect } from 'react'
import { useModelStore } from '../stores/useModelStore'
import type { ModelInfo } from '../api/models'

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  google: 'Google',
  ollama: 'Ollama (Local)',
}

const STAGE_LABELS: Record<string, string> = {
  understand: 'U (Understand)',
  strategize: 'S (Strategize)',
  generate: 'G (Generate)',
  generate_step: 'G-Step',
  verify_llm: 'VF (Verify)',
  fix: 'Fix',
}

function groupByProvider(models: ModelInfo[]): Array<{ provider: string; label: string; items: ModelInfo[] }> {
  const groups = new Map<string, ModelInfo[]>()
  for (const m of models) {
    const list = groups.get(m.provider) ?? []
    list.push(m)
    groups.set(m.provider, list)
  }
  return Array.from(groups.entries()).map(([provider, items]) => ({
    provider,
    label: PROVIDER_LABELS[provider] ?? provider,
    items,
  }))
}

interface ModelDropdownProps {
  value: string
  onChange: (model: string) => void
  models: ModelInfo[]
  className?: string
}

function ModelDropdown({ value, onChange, models, className = '' }: ModelDropdownProps) {
  const groups = groupByProvider(models)

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className={`bg-gray-800 border border-gray-600 text-gray-100 text-xs rounded px-2 py-1.5 focus:outline-none focus:border-blue-500 ${className}`}
    >
      {groups.map(({ provider, label, items }) => (
        <optgroup key={provider} label={label}>
          {items.map((m) => (
            <option key={m.id} value={m.id}>
              {m.display_name}
              {m.input_per_1m > 0 ? ` ($${m.input_per_1m}/${m.output_per_1m})` : ' (free)'}
            </option>
          ))}
        </optgroup>
      ))}
    </select>
  )
}

export function ModelSelector() {
  const {
    models, defaultModel, stageDefaults,
    selectedModel, stageOverrides,
    loaded, fetchModels,
    setSelectedModel, setStageOverride,
  } = useModelStore()

  const [showStages, setShowStages] = useState(false)

  useEffect(() => {
    void fetchModels()
  }, [fetchModels])

  if (!loaded || models.length === 0) return null

  const activeModel = selectedModel ?? defaultModel

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-2">
        <span className="text-xs text-gray-500 whitespace-nowrap">Model</span>
        <ModelDropdown
          value={activeModel}
          onChange={(m) => setSelectedModel(m === defaultModel ? null : m)}
          models={models}
          className="min-w-[180px]"
        />
        <button
          type="button"
          onClick={() => setShowStages(!showStages)}
          className="text-[10px] text-gray-500 hover:text-gray-300 transition-colors whitespace-nowrap"
        >
          {showStages ? '▼ Stage' : '▶ Stage'}
        </button>
      </div>

      {showStages && (
        <div className="grid grid-cols-2 gap-x-4 gap-y-1 pl-2 pt-1 border-l border-gray-700 ml-1">
          {Object.entries(STAGE_LABELS).map(([stage, label]) => {
            const current = stageOverrides[stage] ?? stageDefaults[stage] ?? activeModel
            return (
              <div key={stage} className="flex items-center gap-2">
                <span className="text-[10px] text-gray-500 w-20 truncate" title={label}>
                  {label}
                </span>
                <ModelDropdown
                  value={current}
                  onChange={(m) => setStageOverride(stage, m)}
                  models={models}
                  className="flex-1 min-w-[140px]"
                />
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
