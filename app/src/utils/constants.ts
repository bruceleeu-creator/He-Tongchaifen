/**
 * 全局常量定义
 * 与后端 config.py 中的字段标准保持一致
 */

/** 服务模块选项 */
export const SERVICE_MODULES: string[] = [
  '税务合规',
  '财务规范',
  '风险排查',
  '制度建设',
  '纳税申报辅导',
  '经营分析',
  '客户资料',
  '客户确认',
  '会议沟通',
  '交付验收',
  '顶层结构设计',
  '资产架构',
  '关联交易',
  '股权架构',
  '资金架构',
  '人员架构',
  '其他待确认',
]

/** 任务类型选项 */
export const TASK_TYPES: string[] = [
  '服务执行',
  '客户资料',
  '客户确认',
  '会议沟通',
  '交付验收',
]

/** 当前状态选项 */
export const CURRENT_STATUS: string[] = [
  '未开始',
  '进行中',
  '待客户',
  '待我方',
  '待确认',
  '已完成',
  '逾期',
  '暂停',
]

/** 延期责任归属选项 */
export const DELAY_RESPONSIBILITY: string[] = [
  '无延期',
  '客户原因',
  '我方原因',
  '第三方原因',
  '共同原因',
  '待判断',
]

/** 人工复核状态选项 */
export const REVIEW_STATUS: string[] = [
  '待复核',
  '已确认',
  '需修改',
  '剔除',
]

/** 文件类型选项 */
export const FILE_TYPES = [
  { label: '合同', value: 'contract' },
  { label: '年度服务计划', value: 'plan' },
  { label: '启动会纪要', value: 'meeting_minutes' },
]

/**
 * 18字段定义 - 英文key -> 中文名映射
 * 与后端 config.py 的 FIELD_MAPPING 一致
 */
export interface TaskFieldDef {
  key: string;
  label: string;
  width?: number;
  fixed?: boolean;
  type?: 'text' | 'select' | 'date' | 'textarea';
  options?: string[];
}

/** 18字段完整配置（用于表格列定义和表单） */
export const TASK_FIELDS: TaskFieldDef[] = [
  { key: 'customer_name', label: '客户名称', width: 140 },
  { key: 'project_name', label: '项目名称', width: 160 },
  { key: 'task_name', label: '任务名称', width: 200, fixed: false },
  { key: 'service_module', label: '服务模块', width: 130, type: 'select', options: SERVICE_MODULES },
  { key: 'task_type', label: '任务类型', width: 120, type: 'select', options: TASK_TYPES },
  { key: 'plan_start_date', label: '计划开始时间', width: 130, type: 'date' },
  { key: 'plan_end_date', label: '计划完成时间', width: 130, type: 'date' },
  { key: 'our_owner', label: '我方负责人', width: 120 },
  { key: 'client_contact', label: '客户责任人', width: 120 },
  { key: 'client_requirements', label: '客户需提供的资料或配合事项', width: 260 },
  { key: 'current_status', label: '当前状态', width: 100, type: 'select', options: CURRENT_STATUS },
  { key: 'delay_responsibility', label: '延期责任归属', width: 120, type: 'select', options: DELAY_RESPONSIBILITY },
  { key: 'milestone_goal', label: '节点目标/达到效果', width: 260 },
  { key: 'next_action', label: '下一步动作及承诺完成时间', width: 260 },
  { key: 'deliverables', label: '交付成果或完成凭证', width: 220 },
  { key: 'ai_deliverable_desc', label: 'AI定制交付成果说明', width: 260 },
  { key: 'ai_extraction_basis', label: 'AI提取依据', width: 200 },
  { key: 'review_status', label: '人工复核状态', width: 110, type: 'select', options: REVIEW_STATUS },
]

/** 18字段中文名列表（按顺序，用于CSV导出表头） */
export const TASK_FIELD_LABELS: string[] = TASK_FIELDS.map(f => f.label)

/** 18字段英文名列表（按顺序） */
export const TASK_FIELD_KEYS: string[] = TASK_FIELDS.map(f => f.key)

/** 英文key -> 中文名映射 */
export const FIELD_KEY_TO_LABEL: Record<string, string> = Object.fromEntries(
  TASK_FIELDS.map(f => [f.key, f.label])
)

/** 中文名 -> 英文key映射 */
export const FIELD_LABEL_TO_KEY: Record<string, string> = Object.fromEntries(
  TASK_FIELDS.map(f => [f.label, f.key])
)

/** 步骤配置 */
export const STEPS = [
  { title: '资料上传', description: '上传合同和计划文件', path: '/upload' },
  { title: '识别结果', description: '合同摘要确认、AI识别合同和计划内容', path: '/recognition' },
  { title: '澄清追问', description: '动态追问与确认待澄清事项', path: '/clarification' },
  { title: '任务复核', description: '编辑和复核任务主表、报告校验', path: '/task-review' },
  { title: '版本记录', description: '查看和回退版本', path: '/version-history' },
  { title: '导出', description: '导出任务表', path: '/export' },
]

/** 侧边栏菜单项 */
export const MENU_ITEMS = [
  { key: '/upload', icon: 'UploadOutlined', label: '资料上传' },
  { key: '/recognition', icon: 'ScanOutlined', label: '识别结果' },
  { key: '/clarification', icon: 'FormOutlined', label: '澄清追问' },
  { key: '/task-review', icon: 'TableOutlined', label: '任务复核' },
  { key: '/version-history', icon: 'HistoryOutlined', label: '版本记录' },
  { key: '/export', icon: 'DownloadOutlined', label: '导出' },
]

/** 状态标签颜色映射 */
export const STATUS_TAG_COLORS: Record<string, string> = {
  '未开始': 'default',
  '进行中': 'processing',
  '待客户': 'warning',
  '待我方': 'purple',
  '待确认': 'gold',
  '已完成': 'success',
  '逾期': 'error',
  '暂停': 'default',
}

/** 复核状态标签颜色映射 */
export const REVIEW_TAG_COLORS: Record<string, string> = {
  '待复核': 'default',
  '已确认': 'success',
  '需修改': 'warning',
  '剔除': 'error',
}

/** 风险等级颜色映射 */
export const RISK_SEVERITY_COLORS: Record<string, string> = {
  '高': 'red',
  '中': 'orange',
  '低': 'blue',
}

/** 下拉选项生成器 */
export function getSelectOptions(values: string[]) {
  return values.map(v => ({ label: v, value: v }))
}
