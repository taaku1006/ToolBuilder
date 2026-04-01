import { useState, useCallback } from 'react'

export interface UseArchSelectionResult {
  selectedArchs: Set<string>
  toggleArch: (id: string) => void
}

export function useArchSelection(): UseArchSelectionResult {
  const [selectedArchs, setSelectedArchs] = useState<Set<string>>(new Set())

  const toggleArch = useCallback((id: string) => {
    setSelectedArchs((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  return { selectedArchs, toggleArch }
}
