/**
 * 识别服务 API
 * 合同识别、计划识别、交叉核验
 */
import api from './api'
import type {
  ContractRecognitionResult,
  PlanRecognitionResult,
  CrossValidationResult,
  ContractSummaryResponse,
} from '../types'

interface RequestOptions {
  silent?: boolean
}

const requestConfig = (options?: RequestOptions) => (
  options?.silent ? { suppressErrorMessage: true } as any : undefined
)

/** 合同识别 */
export async function recognizeContract(runId: string): Promise<{
  success: boolean
  run_id: string
  mode: string
  data: ContractRecognitionResult
  message: string
}> {
  return api.post(`/recognition/${runId}/contract`)
}

/** 计划识别 */
export async function recognizePlan(runId: string): Promise<{
  success: boolean
  run_id: string
  mode: string
  skipped?: boolean
  data: PlanRecognitionResult
  message: string
}> {
  return api.post(`/recognition/${runId}/plan`)
}

/** 交叉核验 */
export async function crossCheck(runId: string): Promise<{
  success: boolean
  run_id: string
  mode: string
  data: CrossValidationResult
  message: string
}> {
  return api.post(`/recognition/${runId}/cross-check`)
}

/** 一次性执行所有识别（合同+计划+交叉核验） */
export async function recognizeAll(runId: string): Promise<{
  contract: any
  plan: any
  crossCheck: any
}> {
  const contract = await recognizeContract(runId)
  const plan = await recognizePlan(runId)
  const crossCheckRes = await crossCheck(runId)
  return { contract, plan, crossCheck: crossCheckRes }
}

/** 获取合同识别结果 */
export async function getContractResult(runId: string, options?: RequestOptions): Promise<{
  success: boolean
  run_id: string
  data: ContractRecognitionResult
}> {
  return api.get(`/recognition/${runId}/contract`, requestConfig(options))
}

/** 获取计划识别结果 */
export async function getPlanResult(runId: string, options?: RequestOptions): Promise<{
  success: boolean
  run_id: string
  skipped?: boolean
  data: PlanRecognitionResult
}> {
  return api.get(`/recognition/${runId}/plan`, requestConfig(options))
}

/** 获取交叉核验结果 */
export async function getCrossCheckResult(runId: string, options?: RequestOptions): Promise<{
  success: boolean
  run_id: string
  data: CrossValidationResult
}> {
  return api.get(`/recognition/${runId}/cross-check`, requestConfig(options))
}

/** 获取识别结果（所有类型） */
export async function getRecognitionResults(runId: string): Promise<{
  contract?: ContractRecognitionResult
  plan?: PlanRecognitionResult
  crossCheck?: CrossValidationResult
}> {
  const results: any = {}
  try {
    const contractRes = await getContractResult(runId, { silent: true })
    results.contract = contractRes.data
  } catch {
    // 合同识别结果可能不存在
  }
  try {
    const planRes = await getPlanResult(runId, { silent: true })
    results.plan = planRes.data
  } catch {
    // 计划识别结果可能不存在
  }
  try {
    const crossRes = await getCrossCheckResult(runId, { silent: true })
    results.crossCheck = crossRes.data
  } catch {
    // 交叉核验结果可能不存在
  }
  return results
}

/** 获取合同识别摘要 */
export async function getContractSummary(runId: string, options?: RequestOptions): Promise<ContractSummaryResponse> {
  return api.get(`/recognition/${runId}/summary`, requestConfig(options))
}

/** 确认合同识别摘要 */
export async function confirmContractSummary(runId: string): Promise<{
  success: boolean
  run_id: string
  message: string
}> {
  return api.post(`/recognition/${runId}/summary/confirm`)
}
