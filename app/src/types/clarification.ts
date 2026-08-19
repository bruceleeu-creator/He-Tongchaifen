/**
 * 澄清表单数据类型
 */

/** 单条待确认事项 */
export interface ClarificationItem {
  /** 事项ID */
  item_id: string;
  /** 待确认事项 */
  pending_item: string;
  /** 涉及任务 */
  related_tasks: string;
  /** 原因 */
  reason: string;
  /** 建议向谁确认 */
  suggest_confirm_to: string;
  /** 不确认的影响 */
  impact_if_not_confirmed: string;
  /** 状态: 待确认/已确认/已忽略 */
  status: string;
  /** 确认后的值 */
  confirmed_value: string;
  /** 问题类型 */
  question_type?: string; // text / choice
  /** 选项（choice 类型时） */
  options?: string[];
  /** 建议答案 */
  suggested_answer?: string;
}

/** 澄清表单 */
export interface ClarificationForm {
  /** 待确认事项列表 */
  items: ClarificationItem[];
  /** 总数 */
  total: number;
  /** 来源 */
  source?: string;
  /** 生成方式 */
  generated_by?: string;
  // 保留旧字段做兼容
  /** 表单ID */
  form_id?: string;
  /** 运行ID */
  run_id?: string;
  /** 创建时间 */
  created_at?: string;
  /** 更新时间 */
  updated_at?: string;
}

/** 提交澄清项 */
export interface ClarificationSubmitItem {
  /** 事项ID */
  item_id: string;
  /** 状态: 已确认/已忽略 */
  status: string;
  /** 确认后的值 */
  confirmed_value?: string;
}

/** 提交澄清表单请求 */
export interface ClarificationSubmitRequest {
  /** 提交的事项列表 */
  items: ClarificationSubmitItem[];
}

/** 提交响应摘要 */
export interface ClarificationSubmitSummary {
  total: number;
  confirmed: number;
  ignored: number;
  pending: number;
}

/** 提交回答请求 */
export interface SubmitAnswersRequest {
  answers: {
    item_id: string;
    pending_item: string;
    confirmed_value: string;
  }[];
}
