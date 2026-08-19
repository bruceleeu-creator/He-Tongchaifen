/**
 * 识别结果数据类型
 */

/** 识别依据明细条目（兼容新旧字段名） */
export interface RecognitionBasisItem {
  /** 字段名称（新）或 字段（旧） */
  字段?: string;
  字段名称?: string;
  /** 提取结果 */
  提取结果?: string;
  /** 依据原文摘录（新）/ 原文摘录 / 依据摘要（旧） */
  依据摘要?: string;
  依据原文摘录?: string;
  原文摘录?: string;
  /** 来源文件 */
  来源文件?: string;
  /** 是否待确认（是/否） */
  是否待确认?: string;
  /** 置信度（高/低） */
  置信度?: string;
  /** 兼容旧字段 */
  [key: string]: string | undefined;
}

/** 合同识别摘要 */
export interface ContractSummary {
  甲方: string;
  乙方: string;
  项目名称: string;
  服务期限: string;
  合同签署日期: string;
  '服务费用（总计）': string;
  首期款: string;
  尾期款: string;
  服务方式: string;
  驻场安排: string;
  响应时效: string;
  服务模块: string[];
  交付成果数量: number;
  待确认事项数量: number;
  识别模式: string;
  数据来源: string;
  是否使用样例任务: boolean;
}

/** 合同识别结果 */
export interface ContractRecognitionResult {
  /** 项目基础信息（识别依据明细） */
  basic_info: RecognitionBasisItem[];
  /** 合同约定的服务范围 */
  service_scope: Array<Record<string, string>>;
  /** 客户责任和配合事项 */
  client_responsibilities: Array<Record<string, string>>;
  /** 我方责任和交付义务 */
  our_responsibilities: Array<Record<string, string>>;
  /** 暂停、延期和顺延规则 */
  delay_rules: Array<Record<string, string>>;
  /** 待人工确认事项 */
  pending_items: Array<Record<string, string>>;
  /** 原始识别文本 */
  raw_text: string;
  /** 来源文件名 */
  source_file: string;
  /** 合同识别摘要 */
  contract_summary?: ContractSummary;
}

/** 计划总体摘要 */
export interface PlanSummary {
  项目周期?: string;
  总体服务频次?: string;
  驻场安排?: string;
}

/** 年度服务计划识别结果 */
export interface PlanRecognitionResult {
  /** 计划总体摘要 */
  plan_summary?: PlanSummary;
  /** 年度服务模块 */
  service_modules: Array<Record<string, string>>;
  /** 阶段节点 */
  milestones: Array<Record<string, string>>;
  /** 客户资料和配合事项 */
  client_data: Array<Record<string, string>>;
  /** 会议和确认事项 */
  meetings: Array<Record<string, string>>;
  /** 交付物清单 */
  deliverables?: Array<Record<string, string>>;
  /** 责任人安排 */
  responsible_parties?: Array<Record<string, string>>;
  /** 待人工确认事项 */
  pending_items: Array<Record<string, string>>;
  /** 原始识别文本 */
  raw_text: string;
  /** 来源文件名 */
  source_file: string;
}

/** 交叉核验结果 */
export interface CrossValidationResult {
  /** 一致事项 */
  consistent_items: Array<Record<string, string>>;
  /** 冲突事项 */
  conflict_items: Array<Record<string, string>>;
  /** 缺失事项 */
  missing_items: Array<Record<string, string>>;
  /** 核验总结 */
  summary: string;
}

/** 识别响应 */
export interface RecognitionResponse {
  success: boolean;
  run_id: string;
  mode: string;
  mode_label?: string;
  data_source?: string;
  data: ContractRecognitionResult | PlanRecognitionResult | CrossValidationResult;
  message: string;
}

/** 合同摘要响应 */
export interface ContractSummaryResponse {
  success: boolean;
  run_id: string;
  mode: string;
  mode_label: string;
  data_source: string;
  summary: ContractSummary;
  basic_info: RecognitionBasisItem[];
  service_scope: Array<Record<string, string>>;
  pending_items: Array<Record<string, string>>;
  confirm_required: boolean;
  message: string;
}
