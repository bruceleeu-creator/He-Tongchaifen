/**
 * 全流程自动化 API 服务
 */
import api from './api'

export interface PipelineStep {
  step: number
  key: string
  name: string
  description: string
  status: 'pending' | 'running' | 'completed' | 'skipped' | 'failed'
  mode: string
  mode_label: string
  started_at: string
  completed_at: string
  message: string
  error: string
}

export interface PipelineProgress {
  total: number
  completed: number
  skipped: number
  failed: number
  percentage: number
}

export interface PipelineStatus {
  success: boolean
  run_id: string
  status: 'idle' | 'running' | 'paused' | 'completed' | 'failed'
  progress: PipelineProgress
  current_step: number
  steps: PipelineStep[]
  llm_available: boolean
  llm_model: string
  started_at: string
  completed_at: string
}

export interface PipelineRunResult {
  success: boolean
  run_id: string
  status: string
  message: string
  state?: any
}

export async function runPipeline(runId: string): Promise<PipelineRunResult> {
  // 需求2修复：pipeline 在 LLM 模式下可能跑 5-10 分钟（9 个步骤 × LLM 调用），
  // 默认 axios 120s 会超时但后端仍在执行，导致前端误判失败。
  // 这里设置 10 分钟超时，覆盖完整 pipeline 执行时间。
  return api.post(`/pipeline/${runId}/run`, undefined, { timeout: 600000 })
}

export async function getPipelineStatus(runId: string): Promise<PipelineStatus> {
  return api.get(`/pipeline/${runId}/status`)
}

export async function pausePipeline(runId: string): Promise<PipelineRunResult> {
  return api.post(`/pipeline/${runId}/pause`)
}

export async function resumePipeline(runId: string): Promise<PipelineRunResult> {
  return api.post(`/pipeline/${runId}/resume`)
}

export async function skipStep(runId: string, stepKey: string): Promise<{ success: boolean; message: string }> {
  return api.post(`/pipeline/${runId}/skip/${stepKey}`)
}

export async function retryStep(runId: string, stepKey: string): Promise<{ success: boolean; message: string }> {
  return api.post(`/pipeline/${runId}/retry/${stepKey}`)
}

export async function resetPipeline(runId: string): Promise<{ success: boolean; message: string; state: any }> {
  return api.post(`/pipeline/${runId}/reset`)
}

export async function getPipelineSteps(): Promise<{
  success: boolean
  steps: Array<{ step: number; key: string; name: string; description: string }>
  total: number
}> {
  return api.get('/pipeline/steps')
}
