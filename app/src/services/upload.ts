/**
 * 上传、解析、运行实例管理 API
 */
import api from './api'
import type { RunInfo } from '../types'

/** 上传 Word 文档并解析 */
export async function uploadFile(file: File, fileType: string, runId?: string | null): Promise<any> {
  const formData = new FormData()
  formData.append('file', file)
  formData.append('file_type', fileType)
  if (runId) {
    formData.append('run_id', runId)
  }
  return api.post('/upload/docx', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

/** 获取解析结果 */
export async function getParseResult(runId: string, fileType: string): Promise<any> {
  return api.get(`/upload/runs/${runId}`)
}

/** 获取文件列表（通过运行实例信息） */
export async function getFiles(runId: string): Promise<RunInfo> {
  const res: any = await api.get(`/upload/runs/${runId}`)
  return res.run
}

/** 创建运行实例 */
export async function createRun(runName?: string, useMock: boolean = true): Promise<any> {
  const formData = new FormData()
  formData.append('run_name', runName || '')
  formData.append('use_mock', String(useMock))
  return api.post('/upload/create-run', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
}

/** 列出所有运行实例 */
export async function listRuns(): Promise<any> {
  return api.get('/upload/runs')
}

/** 获取运行实例详情 */
export async function getRun(runId: string): Promise<any> {
  return api.get(`/upload/runs/${runId}`)
}

/** 删除已上传文件
 * 同步清理后端 meta.json / parsed_files.json / *_parsed.json 与下游旧结果
 * file_type、parsed_at 可选，用于区分同名文件或同类型多文件
 */
export async function deleteUploadedFile(
  runId: string,
  filename: string,
  fileType?: string,
  parsedAt?: string,
): Promise<any> {
  return api.delete(`/upload/runs/${runId}/files`, {
    data: {
      filename,
      file_type: fileType || undefined,
      parsed_at: parsedAt || undefined,
    },
  })
}
