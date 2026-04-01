import { useState } from 'react'
import type { Architecture } from '../../api/eval'
import { ArchDetailPanel } from './ArchDetailPanel'

type ArchCategory = 'Baseline' | 'Planner' | 'Mini' | 'Other'

function getArchCategory(id: string): ArchCategory {
  const lower = id.toLowerCase()
  if (lower.includes('mini') || lower.startsWith('v8') || lower.startsWith('v9')) return 'Mini'
  if (lower.includes('planner') || lower.startsWith('v4') || lower.startsWith('v5') || lower.startsWith('v7')) return 'Planner'
  if (lower.startsWith('v1') || lower.startsWith('v2') || lower.startsWith('v3') || lower.startsWith('v6')) return 'Baseline'
  return 'Other'
}

const CATEGORY_ORDER: readonly ArchCategory[] = ['Baseline', 'Planner', 'Mini', 'Other'] as const

function groupArchitectures(archs: readonly Architecture[]): Array<{ category: ArchCategory; items: Architecture[] }> {
  const grouped = new Map<ArchCategory, Architecture[]>()
  for (const cat of CATEGORY_ORDER) {
    grouped.set(cat, [])
  }
  for (const a of archs) {
    const cat = getArchCategory(a.id)
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

const PHASE_DOT_COLORS: Record<string, string> = {
  A: 'bg-blue-400',
  B: 'bg-purple-400',
  P: 'bg-yellow-400',
  C: 'bg-green-400',
  D: 'bg-yellow-400',
  F: 'bg-pink-400',
  G: 'bg-violet-400',
}

const TABLE_PHASES = ['A', 'B', 'P', 'C', 'D', 'G'] as const

function hasPhase(a: Architecture, phase: string): boolean {
  if (!a.pipeline) return a.phases.includes(phase)
  const p = a.pipeline as unknown as Record<string, unknown>
  switch (phase) {
    case 'A': return a.pipeline.explore
    case 'B': return a.pipeline.reflect
    case 'P': return a.pipeline.decompose
    case 'C': return true
    case 'D': return true
    case 'F': return a.pipeline.eval_debug
    case 'G': return p.llm_eval_debug === true
    default: return false
  }
}

function getFStrategy(a: Architecture): string {
  if (!a.pipeline) return a.phases.includes('F') ? 'on' : '-'
  if (!a.pipeline.eval_debug) return '-'
  if (a.pipeline.eval_retry_strategy === 'none') return 'none'
  return a.pipeline.eval_retry_strategy
}

function getRetryLimit(a: Architecture): number {
  return a.pipeline?.debug_retry_limit ?? a.debug_retry_limit
}

interface ArchTableRowProps {
  arch: Architecture
  isSelected: boolean
  toggleArch: (id: string) => void
  detailArchId: string | null
  setDetailArchId: (id: string | null) => void
  colSpan: number
}

function ArchTableRow({
  arch,
  isSelected,
  toggleArch,
  detailArchId,
  setDetailArchId,
  colSpan,
}: ArchTableRowProps) {
  const isDetailOpen = detailArchId === arch.id
  const fStrategy = getFStrategy(arch)

  return (
    <>
      <tr
        className={`border-b border-gray-800 transition-colors cursor-pointer ${
          isSelected
            ? 'bg-blue-950/30 border-l-2 border-l-blue-600'
            : 'opacity-50 hover:opacity-70'
        }`}
        onClick={() => toggleArch(arch.id)}
      >
        <td className="py-2 px-2 text-center">
          <span className={`inline-block w-3 h-3 rounded border ${
            isSelected ? 'bg-blue-600 border-blue-500' : 'border-gray-600'
          }`} />
        </td>
        <td className="py-2 px-2 font-mono text-xs text-gray-200 whitespace-nowrap">{arch.id}</td>
        <td className="py-2 px-2 text-xs text-gray-400 max-w-[200px] truncate">{arch.description}</td>
        <td className="py-2 px-2 text-xs text-gray-500 font-mono whitespace-nowrap">{arch.model}</td>
        {TABLE_PHASES.map((p) => (
          <td key={p} className="py-2 px-1 text-center">
            <PhaseDot active={hasPhase(arch, p)} color={PHASE_DOT_COLORS[p] ?? 'bg-gray-400'} />
          </td>
        ))}
        <td className="py-2 px-2 text-center text-xs font-mono">
          {fStrategy === '-' ? (
            <span className="text-gray-700">-</span>
          ) : (
            <span className="text-pink-400">{fStrategy}</span>
          )}
        </td>
        <td className="py-2 px-2 text-center text-xs font-mono text-gray-400">{getRetryLimit(arch)}</td>
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
}: ArchCategoryGroupProps) {
  return (
    <>
      <tr
        className="border-b border-gray-700 bg-gray-800/60 cursor-pointer hover:bg-gray-800 transition-colors"
        onClick={onToggleCategory}
      >
        <td colSpan={colSpan} className="py-1.5 px-2">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-500">{isCollapsed ? '▶' : '▼'}</span>
            <span className="text-xs font-medium text-gray-300">{category}</span>
            <span className="text-xs text-gray-600">({items.length})</span>
          </div>
        </td>
      </tr>

      {!isCollapsed && items.map((a) => {
        const isSelected = selectedArchs.has(a.id) || selectedArchs.size === 0
        return (
          <ArchTableRow
            key={a.id}
            arch={a}
            isSelected={isSelected}
            toggleArch={toggleArch}
            detailArchId={detailArchId}
            setDetailArchId={setDetailArchId}
            colSpan={colSpan}
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
}

export function ArchitectureTable({
  archs,
  selectedArchs,
  toggleArch,
  detailArchId,
  setDetailArchId,
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
  // Total columns: checkbox + ID + Desc + Model + 6 phases + F strategy + Retry + Detail = 13
  const colSpan = 13

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="sticky top-0 z-10 bg-gray-900">
          <tr className="border-b border-gray-700">
            <th className="text-left py-2 px-2 text-gray-500 text-xs w-8" />
            <th className="text-left py-2 px-2 text-gray-500 text-xs">ID</th>
            <th className="text-left py-2 px-2 text-gray-500 text-xs">Description</th>
            <th className="text-left py-2 px-2 text-gray-500 text-xs">Model</th>
            {TABLE_PHASES.map((p) => (
              <th key={p} className="text-center py-2 px-1 text-gray-500 text-xs w-8">{p}</th>
            ))}
            <th className="text-center py-2 px-2 text-gray-500 text-xs">F strategy</th>
            <th className="text-center py-2 px-2 text-gray-500 text-xs">Retry</th>
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
              />
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
