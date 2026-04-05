import client from './client'

export interface ModelInfo {
  id: string
  provider: string
  display_name: string
  input_per_1m: number
  output_per_1m: number
}

export interface ModelsResponse {
  models: ModelInfo[]
  default_model: string
  stage_defaults: Record<string, string>
}

export async function getModels(): Promise<ModelsResponse> {
  const res = await client.get<ModelsResponse>('/models')
  return res.data
}
