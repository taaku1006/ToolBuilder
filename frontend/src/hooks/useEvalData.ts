import { useState, useCallback, useEffect, type Dispatch, type SetStateAction } from 'react'
import {
  type Architecture,
  type EvalTestCase,
  type PastRun,
  getArchitectures,
  getTestCases,
  listRuns,
} from '../api/eval'

export interface UseEvalDataResult {
  archs: Architecture[]
  cases: EvalTestCase[]
  pastRuns: PastRun[]
  loading: boolean
  error: string | null
  reload: () => Promise<void>
  reloadCases: () => Promise<void>
  setPastRuns: Dispatch<SetStateAction<PastRun[]>>
}

export function useEvalData(): UseEvalDataResult {
  const [archs, setArchs] = useState<Architecture[]>([])
  const [cases, setCases] = useState<EvalTestCase[]>([])
  const [pastRuns, setPastRuns] = useState<PastRun[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const reload = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [a, c, r] = await Promise.all([getArchitectures(), getTestCases(), listRuns()])
      setArchs(a)
      setCases(c)
      setPastRuns(r)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }, [])

  const reloadCases = useCallback(async () => {
    try {
      const c = await getTestCases()
      setCases(c)
    } catch {
      // Silently ignore reload failures
    }
  }, [])

  useEffect(() => {
    reload()
  }, [reload])

  return { archs, cases, pastRuns, loading, error, reload, reloadCases, setPastRuns }
}
