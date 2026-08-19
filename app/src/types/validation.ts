/**
 * 校验结果数据类型
 */

/** 校验检查项 */
export interface ValidationCheck {
  rule: string;
  passed: boolean;
  message: string;
  detail?: string;
}

/** 校验结果 */
export interface ValidationResult {
  success: boolean;
  run_id: string;
  passed: boolean;
  errors: ValidationCheck[];
  warnings: ValidationCheck[];
  checks: ValidationCheck[];
  mode: string;
  mode_label: string;
  message: string;
}
