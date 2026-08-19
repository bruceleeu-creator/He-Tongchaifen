/**
 * 交付成果数据类型
 */

/** 交付成果项 */
export interface DeliverableArtifact {
  /** 成果ID */
  artifact_id: string;
  /** 关联任务ID */
  task_id: string;
  /** 关联任务名称 */
  task_name: string;
  /** 服务模块 */
  service_module: string;
  /** 任务类型 */
  task_type: string;
  /** 成果名称 */
  deliverable_name: string;
  /** 成果类型 */
  deliverable_type: string;
  /** 文件格式 */
  file_format: string;
  /** 模板键 */
  template_key: string;
  /** 模板名称 */
  template_name: string;
  /** 复用来源 */
  reuse_source: string;
  /** AI设计理由 */
  ai_design_reason: string;
  /** 内容大纲 */
  content_outline: string[];
  /** 可变量字段 */
  variables: Record<string, string>;
  /** 状态 */
  status: string;
  /** 复核状态 */
  review_status: string;
  /** 文件路径 */
  file_path: string;
  /** 下载链接 */
  download_url: string;
  /** 版本 */
  version: string;
  /** 创建时间 */
  created_at: string;
  /** 更新时间 */
  updated_at: string;

  // 需求7：归并相关字段（多任务合并为 1 份成果时使用）
  /** 是否为归并成果 */
  is_merged?: boolean;
  /** 覆盖的任务数量 */
  covered_task_count?: number;
  /** 覆盖的任务 ID 列表 */
  covered_task_ids?: string[];
  /** 覆盖的任务名称列表 */
  covered_task_names?: string[];
  /** 归并提示文本 */
  merge_hint?: string;
  /** 内容章节（结构化） */
  content_sections?: Array<{ title: string; bullets: string[] }>;
  /** 验收标准 */
  acceptance_criteria?: string[];
  /** 客户需提供的资料 */
  client_inputs?: string[];
  /** 风险提示 */
  risk_notes?: string[];
  /** 下一步动作 */
  next_actions?: string[];
}

/** 交付成果列表响应 */
export interface DeliverableListResponse {
  total: number;
  items: DeliverableArtifact[];
}
