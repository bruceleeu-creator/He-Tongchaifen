/**
 * Markdown 报告生成工具
 * 用于在前端生成 Markdown 格式的任务报告
 */
import { Task, PendingItem, RiskItem } from '../types'
import { TASK_FIELDS } from './constants'

/**
 * 生成任务列表 Markdown 表格
 */
export function tasksToMarkdownTable(tasks: Task[]): string {
  if (!tasks || tasks.length === 0) {
    return '> 暂无任务数据\n'
  }

  // 表头
  const header = `| 序号 | ${TASK_FIELDS.map(f => f.label).join(' | ')} |`
  const separator = `|---|${TASK_FIELDS.map(() => '---').join('|')}|`

  // 数据行
  const rows = tasks.map((task, index) => {
    const cells = TASK_FIELDS.map(f => {
      const val = (task as any)[f.key] || ''
      return escapeMarkdownCell(val)
    })
    return `| ${index + 1} | ${cells.join(' | ')} |`
  })

  return [header, separator, ...rows].join('\n')
}

/**
 * 转义 Markdown 表格单元格内容
 */
function escapeMarkdownCell(value: string): string {
  return String(value || '').replace(/\|/g, '\\|').replace(/\n/g, '<br>')
}

/**
 * 生成完整的任务报告 Markdown
 */
export function generateTaskReport(
  tasks: Task[],
  runId: string,
  pendingItems?: PendingItem[],
  riskItems?: RiskItem[],
): string {
  const now = new Date()
  const dateStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`

  let md = `# 年度财税顾问项目拆分任务报告\n\n`
  md += `**运行实例ID**: ${runId}\n\n`
  md += `**生成时间**: ${dateStr}\n\n`
  md += `**任务总数**: ${tasks.length}\n\n`
  md += `---\n\n`

  // 任务主表
  md += `## 一、任务主表\n\n`
  md += tasksToMarkdownTable(tasks)
  md += `\n\n`

  // 待确认清单
  if (pendingItems && pendingItems.length > 0) {
    md += `## 二、待人工确认清单\n\n`
    md += `| 序号 | 待确认事项 | 涉及任务 | 原因 | 建议向谁确认 | 不确认的影响 | 状态 |\n`
    md += `|---|---|---|---|---|---|---|\n`
    pendingItems.forEach((item, index) => {
      md += `| ${index + 1} | ${escapeMarkdownCell(item.pending_item)} | ${escapeMarkdownCell(item.related_tasks)} | ${escapeMarkdownCell(item.reason)} | ${escapeMarkdownCell(item.suggest_confirm_to)} | ${escapeMarkdownCell(item.impact_if_not_confirmed)} | ${item.status} |\n`
    })
    md += `\n`
  }

  // 风险提示
  if (riskItems && riskItems.length > 0) {
    md += `## 三、风险提示清单\n\n`
    md += `| 序号 | 风险点 | 风险来源 | 影响范围 | 建议处理方式 | 严重程度 |\n`
    md += `|---|---|---|---|---|---|\n`
    riskItems.forEach((risk, index) => {
      md += `| ${index + 1} | ${escapeMarkdownCell(risk.risk_point)} | ${escapeMarkdownCell(risk.risk_source)} | ${escapeMarkdownCell(risk.impact_scope)} | ${escapeMarkdownCell(risk.suggestion)} | ${risk.severity} |\n`
    })
    md += `\n`
  }

  // 统计摘要
  md += `---\n\n`
  md += `## 统计摘要\n\n`
  const statusCount: Record<string, number> = {}
  tasks.forEach(t => {
    statusCount[t.current_status] = (statusCount[t.current_status] || 0) + 1
  })
  md += `### 按当前状态统计\n\n`
  Object.entries(statusCount).forEach(([status, count]) => {
    md += `- **${status}**: ${count} 项\n`
  })
  md += `\n`

  const reviewCount: Record<string, number> = {}
  tasks.forEach(t => {
    reviewCount[t.review_status] = (reviewCount[t.review_status] || 0) + 1
  })
  md += `### 按复核状态统计\n\n`
  Object.entries(reviewCount).forEach(([status, count]) => {
    md += `- **${status}**: ${count} 项\n`
  })

  return md
}

/**
 * 下载 Markdown 文件
 */
export function downloadMarkdown(content: string, filename: string = 'task_report'): void {
  const blob = new Blob([content], { type: 'text/markdown;charset=utf-8;' })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.setAttribute('download', `${filename}.md`)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
