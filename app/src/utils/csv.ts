/**
 * CSV 生成工具（前端版）
 * 用于在前端直接生成 CSV 文件，无需后端参与
 */
import { Task } from '../types'
import { TASK_FIELDS, TASK_FIELD_LABELS } from './constants'

/**
 * 将任务列表转换为 CSV 字符串
 * @param tasks 任务列表
 * @returns CSV 字符串（带 BOM 头，UTF-8 编码）
 */
export function tasksToCSV(tasks: Task[]): string {
  // 表头
  const header = ['序号', ...TASK_FIELD_LABELS]

  // 数据行
  const rows = tasks.map((task, index) => {
    const row = [String(index + 1)]
    for (const field of TASK_FIELDS) {
      const value = (task as any)[field.key] || ''
      row.push(escapeCSVCell(value))
    }
    return row.join(',')
  })

  // 组装 CSV
  const csv = [header.map(escapeCSVCell).join(','), ...rows].join('\n')

  // 添加 UTF-8 BOM 头（确保 Excel 正确识别中文）
  return '\ufeff' + csv
}

/**
 * 转义 CSV 单元格内容
 * 如果内容包含逗号、引号或换行符，则用双引号包裹并转义内部引号
 */
function escapeCSVCell(value: string): string {
  const str = String(value || '')
  if (str.includes(',') || str.includes('"') || str.includes('\n') || str.includes('\r')) {
    return `"${str.replace(/"/g, '""')}"`
  }
  return str
}

/**
 * 下载 CSV 文件
 * @param tasks 任务列表
 * @param filename 文件名（不含扩展名）
 */
export function downloadCSV(tasks: Task[], filename: string = 'task_list'): void {
  const csv = tasksToCSV(tasks)
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', `${filename}.csv`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * 将任意二维数组转换为 CSV 字符串
 * @param headers 表头数组
 * @param rows 数据行二维数组
 * @returns CSV 字符串
 */
export function arrayToCSV(headers: string[], rows: string[][]): string {
  const headerLine = headers.map(escapeCSVCell).join(',')
  const dataLines = rows.map(row => row.map(escapeCSVCell).join(','))
  return '\ufeff' + [headerLine, ...dataLines].join('\n')
}
