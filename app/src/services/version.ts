/**
 * 版本管理 API
 */
import api from './api'
import type { VersionInfo, VersionSaveRequest } from '../types'

/** 保存版本 */
export async function saveVersion(
  runId: string,
  request: VersionSaveRequest,
): Promise<{
  success: boolean
  run_id: string
  version_id: string
  version_number: number
  task_count: number
  message: string
}> {
  return api.post(`/versions/${runId}/save`, request)
}

/** 获取版本列表 */
export async function listVersions(runId: string): Promise<{
  success: boolean
  run_id: string
  total: number
  versions: VersionInfo[]
}> {
  return api.get(`/versions/${runId}`)
}

/** 获取版本详情（含任务快照） */
export async function getVersion(runId: string, versionId: string): Promise<{
  success: boolean
  run_id: string
  data: VersionInfo
}> {
  return api.get(`/versions/${runId}/${versionId}`)
}

/** 回退到指定版本 */
export async function restoreVersion(runId: string, versionId: string): Promise<{
  success: boolean
  run_id: string
  version_id: string
  version_number: number
  task_count: number
  message: string
}> {
  return api.post(`/versions/${runId}/${versionId}/rollback`)
}

/** 删除指定版本快照 */
export async function deleteVersion(runId: string, versionId: string): Promise<{
  success: boolean
  run_id: string
  version_id: string
  remaining_total: number
  message: string
}> {
  return api.delete(`/versions/${runId}/${versionId}`)
}
