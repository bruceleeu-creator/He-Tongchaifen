/**
 * 任务管理 API
 * 拆分、获取、更新、新增、删除、标记复核、颗粒度检查、报告校验
 */
import type { AxiosRequestConfig } from 'axios'
import api from './api'
import type { Task, TaskCreate, TaskUpdate, GranularityCheckResult, TaskListResponse, ValidationResult } from '../types'

/** 复用 axios 请求配置，并允许注入 suppressErrorMessage 抑制拦截器弹错 */
type RequestOptions = AxiosRequestConfig & { suppressErrorMessage?: boolean }

/** 执行任务拆分 */
export async function splitTasks(runId: string): Promise<{
  success: boolean
  run_id: string
  mode: string
  data: TaskListResponse
  message: string
}> {
  return api.post(`/tasks/${runId}/split`)
}

/** 获取任务列表 */
export async function getTasks(
  runId: string,
  options?: RequestOptions
): Promise<{
  success: boolean
  run_id: string
  data: TaskListResponse
}> {
  return api.get(`/tasks/${runId}`, options)
}

/** 获取单个任务 */
export async function getTask(runId: string, taskId: string): Promise<{
  success: boolean
  run_id: string
  data: Task
}> {
  return api.get(`/tasks/${runId}/${taskId}`)
}

/** 更新任务 */
export async function updateTask(
  runId: string,
  taskId: string,
  taskUpdate: TaskUpdate,
): Promise<{
  success: boolean
  run_id: string
  task_id: string
  message: string
  data: Task
}> {
  return api.put(`/tasks/${runId}/${taskId}`, taskUpdate)
}

/** 新增任务 */
export async function addTask(runId: string, task: TaskCreate): Promise<{
  success: boolean
  run_id: string
  data: Task
  message: string
}> {
  return api.post(`/tasks/${runId}`, task)
}

/** 删除任务 */
export async function deleteTask(runId: string, taskId: string): Promise<{
  success: boolean
  run_id: string
  task_id: string
  message: string
}> {
  return api.delete(`/tasks/${runId}/${taskId}`)
}

/** 标记任务复核状态 */
export async function markReview(
  runId: string,
  taskId: string,
  status: string,
): Promise<{
  success: boolean
  run_id: string
  task_id: string
  review_status: string
  message: string
}> {
  return api.patch(`/tasks/${runId}/${taskId}/review`, { status })
}

/** 批量标记任务复核状态（需求6：按服务模块同类批量复核）
 * - 按 service_module：把该模块下所有「待复核」任务批量标记为指定状态
 * - 按 task_ids：传入显式任务 id 列表，仅标记这些任务
 */
export async function batchMarkReview(
  runId: string,
  params: { status: string; service_module?: string; task_ids?: string[] },
): Promise<{
  success: boolean
  run_id: string
  scope: string
  updated_count: number
  updated_task_ids: string[]
  review_status: string
  message: string
}> {
  return api.patch(`/tasks/${runId}/batch-review`, {
    status: params.status,
    service_module: params.service_module || '',
    task_ids: params.task_ids || [],
  })
}

/** 颗粒度检查 */
export async function checkGranularity(runId: string): Promise<{
  success: boolean
  run_id: string
  mode: string
  data: GranularityCheckResult
  message: string
}> {
  return api.post(`/tasks/${runId}/granularity-check`)
}

/** 获取字段选项 */
export async function getFieldOptions(): Promise<{
  success: boolean
  field_options: Record<string, string[]>
  field_mapping: Record<string, string>
}> {
  return api.get('/upload/runs/field-options')
}

/** 报告校验 */
export async function validateReport(runId: string): Promise<ValidationResult> {
  return api.post(`/tasks/${runId}/validate`)
}

/** 获取校验结果 */
export async function getValidationResult(runId: string): Promise<ValidationResult> {
  return api.get(`/tasks/${runId}/validate`)
}
