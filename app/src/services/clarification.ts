/**
 * 澄清表单 API
 * 动态追问交互
 */
import api from './api'
import type { ClarificationForm } from '../types'

/** 生成动态澄清表单 */
export async function generateForm(runId: string): Promise<{
  success: boolean
  run_id: string
  mode: string
  mode_label?: string
  data_source?: string
  data: ClarificationForm
  message: string
}> {
  return api.post(`/clarification/${runId}/form`)
}

/** 获取澄清表单 */
export async function getForm(runId: string): Promise<{
  success: boolean
  run_id: string
  mode?: string
  mode_label?: string
  data_source?: string
  data: ClarificationForm
  message?: string
}> {
  return api.get(`/clarification/${runId}/form`)
}

/** 提交澄清问题回答 */
export async function submitAnswers(runId: string, answers: {
  item_id: string
  pending_item: string
  confirmed_value: string
}[]): Promise<{
  success: boolean
  run_id: string
  message: string
  data?: { tasks: any[] }
}> {
  return api.post(`/clarification/${runId}/submit-answers`, { answers })
}

/** 二次任务拆分 */
export async function secondSplit(runId: string): Promise<{
  success: boolean
  run_id: string
  message: string
  data?: { tasks: any[] }
}> {
  return api.post(`/clarification/${runId}/second-split`)
}
