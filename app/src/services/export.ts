/**
 * 导出服务 API
 */
import api from './api'

/** 导出 CSV（返回 Blob） */
export async function exportCSV(runId: string): Promise<Blob> {
  const response = await api.get(`/export/${runId}/csv`, {
    responseType: 'blob',
  })
  return response as unknown as Blob
}

/** 导出 Markdown（返回内容字符串） */
export async function exportMarkdown(runId: string): Promise<{
  success: boolean
  run_id: string
  content: string
}> {
  return api.get(`/export/${runId}/markdown`, {
    params: { download: false },
  })
}

/** 导出 Markdown 文件（返回 Blob） */
export async function exportMarkdownFile(runId: string): Promise<Blob> {
  const response = await api.get(`/export/${runId}/markdown`, {
    responseType: 'blob',
  })
  return response as unknown as Blob
}

/** 导出完整数据包 */
export async function exportFull(runId: string): Promise<{
  success: boolean
  run_id: string
  filename: string
  download_url: string
  task_count: number
  pending_count: number
  risk_count: number
  message: string
}> {
  return api.get(`/export/${runId}/full`)
}

/** 下载导出文件 */
export async function downloadFile(runId: string, filename: string): Promise<Blob> {
  const response = await api.get(`/export/${runId}/download`, {
    params: { file: filename },
    responseType: 'blob',
  })
  return response as unknown as Blob
}

/** 触发浏览器下载 Blob 文件 */
export function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
