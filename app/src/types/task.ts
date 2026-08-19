/**
 * 任务数据模型 - 18字段定义
 * 字段名与后端 API 一致
 */

/** 任务基础接口 - 18字段 */
export interface Task {
  /** 任务ID（系统字段） */
  task_id: string;
  /** 1. 客户名称 */
  customer_name: string;
  /** 2. 项目名称 */
  project_name: string;
  /** 3. 任务名称 */
  task_name: string;
  /** 4. 服务模块 */
  service_module: string;
  /** 5. 任务类型 */
  task_type: string;
  /** 6. 计划开始时间 */
  plan_start_date: string;
  /** 7. 计划完成时间 */
  plan_end_date: string;
  /** 8. 我方负责人 */
  our_owner: string;
  /** 9. 客户责任人 */
  client_contact: string;
  /** 10. 客户需提供的资料或配合事项 */
  client_requirements: string;
  /** 11. 当前状态 */
  current_status: string;
  /** 12. 延期责任归属 */
  delay_responsibility: string;
  /** 13. 节点目标/达到效果 */
  milestone_goal: string;
  /** 14. 下一步动作及承诺完成时间 */
  next_action: string;
  /** 15. 交付成果或完成凭证 */
  deliverables: string;
  /** 16. AI定制交付成果说明 */
  ai_deliverable_desc: string;
  /** 17. AI提取依据 */
  ai_extraction_basis: string;
  /** 18. 人工复核状态 */
  review_status: string;
  /** 创建时间（系统字段） */
  created_at?: string;
  /** 更新时间（系统字段） */
  updated_at?: string;
}

/** 任务列表响应 */
export interface TaskListResponse {
  total: number;
  tasks: Task[];
}

/** 任务更新请求（所有字段可选） */
export type TaskUpdate = Partial<Omit<Task, 'task_id' | 'created_at' | 'updated_at'>>;

/** 任务创建请求 */
export type TaskCreate = Omit<Task, 'task_id' | 'created_at' | 'updated_at'>;

/** 颗粒度检查结果 */
export interface GranularityCheckResult {
  /** 需要继续拆分的任务 */
  need_split: Array<{
    原任务名称: string;
    问题: string;
    建议拆分为哪些任务: string;
  }>;
  /** 缺少关键字段的任务 */
  missing_fields: Array<Record<string, string>>;
  /** 客户资料未独立成行 */
  client_data_issues: Array<Record<string, string>>;
  /** 交付成果不明确 */
  deliverable_issues: Array<Record<string, string>>;
  /** 检查总结 */
  summary: string;
}

/** 通用API响应 */
export interface ApiResponse<T = any> {
  success: boolean;
  message?: string;
  data?: T;
  [key: string]: any;
}
