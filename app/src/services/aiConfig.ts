/**
 * AI 配置 API 服务
 */
import api from './api'

export interface AIConfig {
  preset: string
  api_key: string
  api_key_masked: string
  has_api_key: boolean
  base_url: string
  model: string
  temperature: number
  timeout: number
  updated_at: string
  updated_by: string
}

export interface PresetInfo {
  label: string
  base_url: string
  model: string
  description: string
}

export interface AIConfigResponse {
  success: boolean
  config: AIConfig
  presets: Record<string, PresetInfo>
  llm_available: boolean
  mode: string
  model_source: string
}

export interface TestConnectionResponse {
  success: boolean
  message: string
  model: string
  response_preview?: string
  llm_available: boolean
}

export async function getAIConfig(): Promise<AIConfigResponse> {
  return api.get('/ai-config')
}

export async function updateAIConfig(data: {
  preset?: string
  api_key?: string
  base_url?: string
  model?: string
  temperature?: number
  timeout?: number
}): Promise<{ success: boolean; config: AIConfig; llm_available: boolean; message: string }> {
  return api.post('/ai-config/update', data)
}

export async function testConnection(): Promise<TestConnectionResponse> {
  return api.post('/ai-config/test')
}

export async function getPresets(): Promise<{
  success: boolean
  presets: Record<string, PresetInfo>
  current_preset: string
}> {
  return api.get('/ai-config/presets')
}
