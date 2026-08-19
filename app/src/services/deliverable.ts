/**
 * 交付成果 API
 */
import type { AxiosRequestConfig } from 'axios'
import api from './api'
import type { DeliverableArtifact, DeliverableListResponse } from '../types'

/** 复用 axios 请求配置，并允许注入 suppressErrorMessage 抑制拦截器弹错 */
type RequestOptions = AxiosRequestConfig & { suppressErrorMessage?: boolean }

/** 为全部任务生成交付成果（批量，后端使用规则/模板模式，不调用 LLM）
 * 需求7：批量生成会按 (service_module, deliverable_type) 归并同类任务
 */
export async function generateAllDeliverables(runId: string): Promise<{
  success: boolean
  run_id: string
  total: number
  new_count: number
  merged_count: number
  group_count: number
  message: string
}> {
  // 批量生成已切到规则/模板模式，理论上很快；放宽超时到 5 分钟作为兜底
  const opts: RequestOptions = {
    timeout: 300000,
    suppressErrorMessage: true,
  }
  return api.post(`/deliverables/${runId}/generate`, undefined, opts)
}

/** 为单个任务重新生成交付成果（调用 LLM 深度设计，放宽超时）
 * 需求7：重新生成时会自动切换为另一套模板（排除已用过的）
 */
export async function generateTaskDeliverable(
  runId: string,
  taskId: string
): Promise<{
  success: boolean
  run_id: string
  task_id: string
  artifact: DeliverableArtifact
  template_switched: boolean
  previous_template_count: number
  message: string
}> {
  const opts: RequestOptions = {
    timeout: 300000,
    suppressErrorMessage: true,
  }
  return api.post(`/deliverables/${runId}/tasks/${taskId}/generate`, undefined, opts)
}

/** 获取全部交付成果清单 */
export async function getDeliverables(runId: string): Promise<{
  success: boolean
  run_id: string
  total: number
  data: DeliverableListResponse
}> {
  return api.get(`/deliverables/${runId}`)
}

/** 更新交付成果 */
export async function updateArtifact(
  runId: string,
  artifactId: string,
  updates: Partial<DeliverableArtifact>
): Promise<{
  success: boolean
  run_id: string
  artifact_id: string
  message: string
}> {
  return api.patch(`/deliverables/${runId}/artifacts/${artifactId}`, updates)
}

/** 下载交付成果文件 */
export function getArtifactDownloadUrl(runId: string, artifactId: string): string {
  return `/api/deliverables/${runId}/download/${artifactId}`
}

/** 下载全部交付成果（zip 打包）的 URL */
export function getAllDeliverablesDownloadUrl(runId: string): string {
  return `/api/deliverables/${runId}/download-all`
}

/** 保存为模板 */
export async function saveAsTemplate(
  runId: string,
  artifactId: string,
  templateName: string
): Promise<{
  success: boolean
  run_id: string
  artifact_id: string
  template_key: string
  message: string
}> {
  return api.post(`/deliverables/${runId}/artifacts/${artifactId}/save-template`, {
    template_name: templateName,
  })
}
