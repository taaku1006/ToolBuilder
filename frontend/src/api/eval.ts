import client from './client'

export interface Architecture {
  id: string
  phases: string[]
  model: string
  debug_retry_limit: number
  temperature: number
  description: string
}

export interface EvalTestCase {
  id: string
  task: string
  description: string
  file_path: string | null
  expected_success: boolean
}

export interface RunStatus {
  run_id: string
  status: 'running' | 'completed' | 'failed' | 'not_found' | 'stopped' | 'stopping'
  progress: number
  total: number
  report: EvalReport | null
}

export interface EvalReport {
  summary: Record<string, ArchSummary>
  comparison_matrix: Record<string, Record<string, boolean>>
  best_architecture: string | null
  architecture_ids: string[]
  test_case_ids: string[]
}

export interface ArchSummary {
  success_rate: number
  avg_tokens: number
  avg_duration_ms: number
  avg_retries: number
  avg_cost_usd: number
  total_cost_usd: number
  total_runs: number
  ci_low?: number
  ci_high?: number
  error_breakdown?: Record<string, number>
}

export interface PastRun {
  run_id: string
  status: string
  best_architecture?: string
  summary?: Record<string, ArchSummary>
  progress?: number
  total?: number
}

export async function getArchitectures(): Promise<Architecture[]> {
  const res = await client.get<Architecture[]>('/eval/architectures')
  return res.data
}

export async function getTestCases(): Promise<EvalTestCase[]> {
  const res = await client.get<EvalTestCase[]>('/eval/test-cases')
  return res.data
}

export async function startRun(
  architectureIds?: string[],
  testCaseIds?: string[],
): Promise<RunStatus> {
  const res = await client.post<RunStatus>('/eval/run', {
    architecture_ids: architectureIds ?? null,
    test_case_ids: testCaseIds ?? null,
  })
  return res.data
}

export async function getRunStatus(runId: string): Promise<RunStatus> {
  const res = await client.get<RunStatus>(`/eval/run/${runId}`)
  return res.data
}

export async function listRuns(): Promise<PastRun[]> {
  const res = await client.get<PastRun[]>('/eval/runs')
  return res.data
}

export async function stopRun(runId: string): Promise<RunStatus> {
  const res = await client.post<RunStatus>(`/eval/run/${runId}/stop`)
  return res.data
}

export async function createTestCase(
  task: string,
  description: string,
  file?: File,
): Promise<EvalTestCase> {
  const form = new FormData()
  form.append('task', task)
  form.append('description', description)
  if (file) form.append('file', file)
  const res = await client.post<EvalTestCase>('/eval/test-cases', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return res.data
}

export async function deleteTestCase(id: string): Promise<void> {
  await client.delete(`/eval/test-cases/${id}`)
}
