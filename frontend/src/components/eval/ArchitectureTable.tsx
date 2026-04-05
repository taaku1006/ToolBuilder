import { useState, useEffect } from 'react'
import type { Architecture } from '../../api/eval'
import { updateArchitecture } from '../../api/eval'
import { useModelStore } from '../../stores/useModelStore'
import { ArchDetailPanel } from './ArchDetailPanel'

type ArchCategory = 'Adaptive v2' | 'MagenticOne'

const CATEGORY_STYLES: Record<ArchCategory, { border: string; badge: string; bg: string }> = {
  'Adaptive v2': {
    border: 'border-l-blue-500',
    badge: 'bg-blue-900/60 text-blue-300 border-blue-700',
    bg: 'bg-blue-950/10',
  },
  MagenticOne: {
    border: 'border-l-amber-500',
    badge: 'bg-amber-900/60 text-amber-300 border-amber-700',
    bg: 'bg-amber-950/10',
  },
}

function getArchCategory(a: Architecture): ArchCategory {
  if (a.architecture_type === 'magentic_one_embed' || a.architecture_type === 'magentic_one_pkg') {
    return 'MagenticOne'
  }
  return 'Adaptive v2'
}

const CATEGORY_ORDER: readonly ArchCategory[] = ['Adaptive v2', 'MagenticOne'] as const

function groupArchitectures(archs: readonly Architecture[]): Array<{ category: ArchCategory; items: Architecture[] }> {
  const grouped = new Map<ArchCategory, Architecture[]>()
  for (const cat of CATEGORY_ORDER) {
    grouped.set(cat, [])
  }
  for (const a of archs) {
    const cat = getArchCategory(a)
    grouped.get(cat)!.push(a)
  }
  return CATEGORY_ORDER
    .filter((cat) => (grouped.get(cat)?.length ?? 0) > 0)
    .map((cat) => ({ category: cat, items: grouped.get(cat)! }))
}

function PhaseDot({ active, color }: { active: boolean; color: string }) {
  if (!active) return <span className="inline-block w-2.5 h-2.5" />
  return <span className={`inline-block w-2.5 h-2.5 rounded-full ${color}`} />
}

function getMemoryEnabled(a: Architecture): boolean {
  const v2 = (a as unknown as Record<string, unknown>).v2_config as Record<string, unknown> | null
  return (v2?.memory_enabled as boolean) ?? true
}

function getMaxReplan(a: Architecture): number {
  const v2 = (a as unknown as Record<string, unknown>).v2_config as Record<string, unknown> | null
  return (v2?.max_replan as number) ?? 2
}

function getRetryLimit(a: Architecture): number {
  return a.pipeline?.debug_retry_limit ?? a.debug_retry_limit
}

function InlineModelSelect({ value, onChange }: { value: string; onChange: (m: string) => void }) {
  const { models, loaded, fetchModels } = useModelStore()

  useEffect(() => {
    void fetchModels()
  }, [fetchModels])

  if (!loaded || models.length === 0) {
    return <span className="text-xs text-gray-500 font-mono">{value}</span>
  }

  const grouped = new Map<string, typeof models>()
  for (const m of models) {
    const list = grouped.get(m.provider) ?? []
    list.push(m)
    grouped.set(m.provider, list)
  }

  const LABELS: Record<string, string> = {
    openai: 'OpenAI', anthropic: 'Anthropic', google: 'Google', ollama: 'Ollama',
  }

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="bg-transparent border-0 text-xs text-gray-400 font-mono cursor-pointer hover:text-gray-200 focus:outline-none focus:text-gray-200 py-0 px-0"
    >
      {Array.from(grouped.entries()).map(([provider, items]) => (
        <optgroup key={provider} label={LABELS[provider] ?? provider}>
          {items.map((m) => (
            <option key={m.id} value={m.id}>{m.display_name}</option>
          ))}
        </optgroup>
      ))}
    </select>
  )
}

interface ArchTableRowProps {
  arch: Architecture
  category: ArchCategory
  isSelected: boolean
  toggleArch: (id: string) => void
  detailArchId: string | null
  setDetailArchId: (id: string | null) => void
  colSpan: number
  onModelChange?: (archId: string, model: string) => void
}

function ArchTableRow({
  arch,
  category,
  isSelected,
  toggleArch,
  detailArchId,
  setDetailArchId,
  colSpan,
  onModelChange,
}: ArchTableRowProps) {
  const isDetailOpen = detailArchId === arch.id
  const style = CATEGORY_STYLES[category]
  const memoryEnabled = getMemoryEnabled(arch)
  const isV2 = category === 'Adaptive v2'

  return (
    <>
      <tr
        className={`border-b border-gray-800 transition-colors cursor-pointer border-l-2 ${
          isSelected
            ? `${style.bg} ${style.border}`
            : 'border-l-transparent opacity-50 hover:opacity-70'
        }`}
        onClick={() => toggleArch(arch.id)}
      >
        <td className="py-2 px-2 text-center">
          <span className={`inline-block w-3 h-3 rounded border ${
            isSelected ? 'bg-blue-600 border-blue-500' : 'border-gray-600'
          }`} />
        </td>
        <td className="py-2 px-2 font-mono text-xs text-gray-200 whitespace-nowrap">{arch.id}</td>
        <td className="py-2 px-2 text-xs text-gray-400 max-w-[240px] truncate">{arch.description}</td>
        <td className="py-2 px-2" onClick={(e) => e.stopPropagation()}>
          <InlineModelSelect
            value={arch.model}
            onChange={(m) => onModelChange?.(arch.id, m)}
          />
        </td>
        {isV2 ? (
          <>
            <td className="py-2 px-2 text-center">
              <PhaseDot active={memoryEnabled} color="bg-teal-400" />
            </td>
            <td className="py-2 px-2 text-center text-xs font-mono text-gray-400">
              {getMaxReplan(arch)}
            </td>
          </>
        ) : (
          <>
            <td className="py-2 px-2 text-center text-xs text-gray-600">-</td>
            <td className="py-2 px-2 text-center text-xs text-gray-600">-</td>
          </>
        )}
        <td className="py-2 px-1 text-center" onClick={(e) => e.stopPropagation()}>
          <button
            onClick={() => setDetailArchId(isDetailOpen ? null : arch.id)}
            className="text-xs text-gray-500 hover:text-gray-300 px-1 py-0.5 transition-colors"
            title="Show architecture detail"
          >
            {isDetailOpen ? '▼' : '▶'}
          </button>
        </td>
      </tr>
      {isDetailOpen && (
        <tr className="border-b border-gray-800">
          <td colSpan={colSpan} className="px-2 py-2">
            <ArchDetailPanel arch={arch} />
          </td>
        </tr>
      )}
    </>
  )
}

interface ArchCategoryGroupProps {
  category: ArchCategory
  items: Architecture[]
  isCollapsed: boolean
  onToggleCategory: () => void
  selectedArchs: Set<string>
  toggleArch: (id: string) => void
  detailArchId: string | null
  setDetailArchId: (id: string | null) => void
  colSpan: number
  onModelChange?: (archId: string, model: string) => void
}

function ArchCategoryGroup({
  category,
  items,
  isCollapsed,
  onToggleCategory,
  selectedArchs,
  toggleArch,
  detailArchId,
  setDetailArchId,
  colSpan,
  onModelChange,
}: ArchCategoryGroupProps) {
  const style = CATEGORY_STYLES[category]

  return (
    <>
      <tr
        className={`border-b border-gray-700 ${style.bg} cursor-pointer hover:bg-gray-800/80 transition-colors`}
        onClick={onToggleCategory}
      >
        <td colSpan={colSpan} className="py-2 px-2">
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-500">{isCollapsed ? '▶' : '▼'}</span>
            <span className={`text-[10px] font-mono px-2 py-0.5 rounded border ${style.badge}`}>
              {category}
            </span>
            <span className="text-xs text-gray-400">{items.length} architectures</span>
          </div>
        </td>
      </tr>

      {!isCollapsed && items.map((a) => {
        const isSelected = selectedArchs.has(a.id) || selectedArchs.size === 0
        return (
          <ArchTableRow
            key={a.id}
            arch={a}
            category={category}
            isSelected={isSelected}
            toggleArch={toggleArch}
            detailArchId={detailArchId}
            setDetailArchId={setDetailArchId}
            colSpan={colSpan}
            onModelChange={onModelChange}
          />
        )
      })}
    </>
  )
}

export interface ArchitectureTableProps {
  archs: Architecture[]
  selectedArchs: Set<string>
  toggleArch: (id: string) => void
  detailArchId: string | null
  setDetailArchId: (id: string | null) => void
  onModelChange?: (archId: string, model: string) => void
}

export function ArchitectureTable({
  archs,
  selectedArchs,
  toggleArch,
  detailArchId,
  setDetailArchId,
  onModelChange,
}: ArchitectureTableProps) {
  const [collapsedCategories, setCollapsedCategories] = useState<Set<ArchCategory>>(new Set())

  const toggleCategory = (cat: ArchCategory) => {
    setCollapsedCategories((prev) => {
      const next = new Set(prev)
      if (next.has(cat)) next.delete(cat)
      else next.add(cat)
      return next
    })
  }

  const groups = groupArchitectures(archs)
  const colSpan = 7 // checkbox + ID + Desc + Model + Memory + Replan + Detail

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 z-10 bg-gray-900">
          <tr className="border-b border-gray-700">
            <th className="text-left py-2 px-2 text-gray-500 text-xs w-8" />
            <th className="text-left py-2 px-2 text-gray-500 text-xs">ID</th>
            <th className="text-left py-2 px-2 text-gray-500 text-xs">Description</th>
            <th className="text-left py-2 px-2 text-gray-500 text-xs">Model</th>
            <th className="text-center py-2 px-2 text-gray-500 text-xs">Memory</th>
            <th className="text-center py-2 px-2 text-gray-500 text-xs">Replan</th>
            <th className="text-center py-2 px-1 text-gray-500 text-xs w-12" />
          </tr>
        </thead>
        <tbody>
          {groups.map(({ category, items }) => {
            const isCollapsed = collapsedCategories.has(category)
            return (
              <ArchCategoryGroup
                key={category}
                category={category}
                items={items}
                isCollapsed={isCollapsed}
                onToggleCategory={() => toggleCategory(category)}
                selectedArchs={selectedArchs}
                toggleArch={toggleArch}
                detailArchId={detailArchId}
                setDetailArchId={setDetailArchId}
                colSpan={colSpan}
                onModelChange={onModelChange}
              />
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
