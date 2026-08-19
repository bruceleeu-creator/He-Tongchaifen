/**
 * 复核服务 API
 * 待确认清单、风险提示
 */
import type { AxiosRequestConfig } from 'axios'
import api from './api'
import type { PendingItem, PendingListResponse, RiskListResponse } from '../types'

/** 复用 axios 请求配置，并允许注入 suppressErrorMessage 抑制拦截器弹错 */
type RequestOptions = AxiosRequestConfig & { suppressErrorMessage?: boolean }

/** 生成待确认清单 */
export async function generatePending(runId: string): Promise<{
  success: boolean
  run_id: string
  mode: string
  data: PendingListResponse
  message: string
}> {
  return api.post(`/review/${runId}/pending-list`)
}

/** 获取待确认清单 */
export async function getPending(
  runId: string,
  options?: RequestOptions
): Promise<{
  success: boolean
  run_id: string
  data: PendingListResponse
}> {
  return api.get(`/review/${runId}/pending-list`, options)
}

/** 更新待确认清单单条记录 */
export async function updatePendingItem(
  runId: string,
  itemId: string,
  updates: Partial<PendingItem>
): Promise<{
  success: boolean
  run_id: string
  item_id: string
  data: PendingItem
  message: string
}> {
  return api.patch(`/review/${runId}/pending-list/${itemId}`, updates)
}

/** 生成风险提示清单 */
export async function generateRisk(runId: string): Promise<{
  success: boolean
  run_id: string
  mode: string
  data: RiskListResponse
  message: string
}> {
  return api.post(`/review/${runId}/risk-warning`)
}

/** 获取风险提示清单 */
export async function getRisk(
  runId: string,
  options?: RequestOptions
): Promise<{
  success: boolean
  run_id: string
  data: RiskListResponse
}> {
  return api.get(`/review/${runId}/risk-warning`, options)
}
