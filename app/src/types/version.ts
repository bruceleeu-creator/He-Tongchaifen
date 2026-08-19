/**
 * 版本记录数据类型
 */

/** 版本信息 */
export interface VersionInfo {
  /** 版本ID */
  version_id: string;
  /** 运行ID */
  run_id: string;
  /** 版本号 */
  version_number: number;
  /** 版本描述 */
  description: string;
  /** 任务数量 */
  task_count: number;
  /** 创建时间 */
  created_at: string;
  /** 创建者 */
  created_by: string;
  /** 任务快照（仅版本详情接口返回） */
  snapshot?: {
    total: number;
    tasks: any[];
  };
}

/** 版本列表响应 */
export interface VersionListResponse {
  total: number;
  versions: VersionInfo[];
}

/** 保存版本请求 */
export interface VersionSaveRequest {
  description: string;
}

/** 保存版本响应 */
export interface VersionSaveResponse {
  success: boolean;
  run_id: string;
  version_id: string;
  version_number: number;
  task_count: number;
  message: string;
}

/** 回退版本响应 */
export interface VersionRollbackResponse {
  success: boolean;
  run_id: string;
  version_id: string;
  version_number: number;
  task_count: number;
  message: string;
}

/** 删除版本响应 */
export interface VersionDeleteResponse {
  success: boolean;
  run_id: string;
  version_id: string;
  remaining_total: number;
  message: string;
}

/** 文件信息 */
export interface FileInfo {
  filename: string;
  file_type: string;
  parsed_at: string;
  filepath?: string;
  paragraph_count?: number;
  table_count?: number;
  char_count?: number;
}

/** 运行实例信息 */
export interface RunInfo {
  run_id: string;
  run_name?: string;
  status: string;
  mode?: string;
  uploaded_files?: string[];
  file_types?: string[];
  created_at?: string;
}

/** 待确认清单项 */
export interface PendingItem {
  item_id: string;
  pending_item: string;
  related_tasks: string;
  reason: string;
  suggest_confirm_to: string;
  impact_if_not_confirmed: string;
  confirmed_value: string;
  status: string;
}

/** 待确认清单 */
export interface PendingListResponse {
  total: number;
  items: PendingItem[];
}

/** 风险项 */
export interface RiskItem {
  risk_id: string;
  risk_point: string;
  risk_source: string;
  impact_scope: string;
  suggestion: string;
  severity: string;
}

/** 风险清单 */
export interface RiskListResponse {
  total: number;
  risks: RiskItem[];
}

/** 导出文件信息 */
export interface ExportFileInfo {
  filename: string;
  download_url: string;
  task_count: number;
  pending_count: number;
  risk_count: number;
}
