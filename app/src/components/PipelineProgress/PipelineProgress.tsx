/**
 * 全流程自动化进度面板
 * 展示文档分析的9个步骤执行进度
 *
 * 顾问账簿主题：深墨海军蓝 · 羊皮纸 · 古金 · 鼠尾草绿 · 琥珀 · 深朱
 */
import React, { useState, useEffect, useRef, useCallback } from 'react'
import {
  Drawer,
  Steps,
  Button,
  Progress,
  Tag,
  Alert,
  Space,
  Typography,
  Popconfirm,
  Divider,
  Empty,
  Spin,
  Tooltip,
} from 'antd'
import {
  PlayCircleOutlined,
  PauseCircleOutlined,
  ReloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  LoadingOutlined,
  MinusCircleOutlined,
  StepForwardOutlined,
  ThunderboltOutlined,
  SyncOutlined,
} from '@ant-design/icons'
import { message } from '../../utils/messageBridge'
import {
  runPipeline,
  getPipelineStatus,
  pausePipeline,
  resumePipeline,
  skipStep,
  retryStep,
  resetPipeline,
} from '../../services/pipeline'
import type { PipelineStatus, PipelineStep } from '../../services/pipeline'

const { Text } = Typography

/* ============================================================
   常量定义
   ============================================================ */

/** 9个步骤静态定义（与后端一致，作为兜底与字段补充） */
const PIPELINE_STEPS = [
  { key: 'contract_recognition', name: '合同识别', description: '深度读取合同原文，提取核心字段' },
  { key: 'plan_recognition', name: '计划识别', description: '识别年度服务计划' },
  { key: 'cross_check', name: '交叉核验', description: '合同与计划交叉核验' },
  { key: 'clarification', name: '动态追问', description: '根据合同摘要生成追问问题' },
  { key: 'task_split', name: '任务拆分', description: '基于合同+回答生成任务主表' },
  { key: 'granularity_check', name: '颗粒度检查', description: '检查任务拆分粒度' },
  { key: 'pending_list', name: '待确认清单', description: '生成待确认事项清单' },
  { key: 'risk_warning', name: '风险提示', description: '生成风险提示清单' },
  { key: 'validation', name: '报告校验', description: '9项校验规则检查' },
] as const

/** 流程状态 -> 中文标签 + Tag 颜色 */
const PIPELINE_STATUS_MAP: Record<string, { label: string; color: string }> = {
  idle: { label: '空闲', color: 'default' },
  running: { label: '运行中', color: 'processing' },
  paused: { label: '已暂停', color: 'warning' },
  completed: { label: '已完成', color: 'success' },
  failed: { label: '失败', color: 'error' },
}

/** Ant Design Steps 子项类型 */
interface StepItem {
  title: React.ReactNode
  description: React.ReactNode
  status: 'wait' | 'process' | 'finish' | 'error'
  icon?: React.ReactNode
}

/* ============================================================
   工具函数
   ============================================================ */

/** 步骤状态 -> Ant Design Steps status */
function mapStepStatus(status: PipelineStep['status']): StepItem['status'] {
  switch (status) {
    case 'running':
      return 'process'
    case 'completed':
      return 'finish'
    case 'failed':
      return 'error'
    default:
      // pending / skipped 均映射为 wait
      return 'wait'
  }
}

/** 步骤状态 -> 自定义图标（仅 running / skipped 需要覆盖默认图标） */
function getStepIcon(status: PipelineStep['status']): React.ReactNode | undefined {
  switch (status) {
    case 'running':
      return <LoadingOutlined style={{ color: 'var(--gold)' }} />
    case 'skipped':
      return <MinusCircleOutlined style={{ color: 'var(--slate)' }} />
    default:
      return undefined
  }
}

/* ============================================================
   组件
   ============================================================ */

interface PipelineProgressProps {
  open: boolean
  onClose: () => void
  runId: string | null
}

const PipelineProgress: React.FC<PipelineProgressProps> = ({ open, onClose, runId }) => {
  const [status, setStatus] = useState<PipelineStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const [actionLoading, setActionLoading] = useState<Record<string, boolean>>({})
  const pollingRef = useRef<ReturnType<typeof setInterval> | null>(null)

  /* ---- 获取流程状态 ---- */
  const fetchStatus = useCallback(async () => {
    if (!runId) return
    try {
      const res = await getPipelineStatus(runId)
      setStatus(res)
    } catch {
      // 错误已由 axios 拦截器统一提示
    }
  }, [runId])

  /* ---- 停止轮询 ---- */
  const stopPolling = useCallback(() => {
    if (pollingRef.current) {
      clearInterval(pollingRef.current)
      pollingRef.current = null
    }
  }, [])

  /* ---- 启动轮询（每2秒） ---- */
  const startPolling = useCallback(() => {
    if (pollingRef.current) return
    pollingRef.current = setInterval(fetchStatus, 2000)
  }, [fetchStatus])

  /* ---- 打开时自动获取进度 ---- */
  useEffect(() => {
    if (open && runId) {
      setLoading(true)
      fetchStatus().finally(() => setLoading(false))
    } else if (!open) {
      setStatus(null)
      stopPolling()
    }
  }, [open, runId, fetchStatus, stopPolling])

  /* ---- 流程运行中时轮询，完成/失败时停止 ---- */
  useEffect(() => {
    if (!open) return
    if (status?.status === 'running') {
      startPolling()
    } else {
      stopPolling()
    }
    return () => {
      stopPolling()
    }
  }, [status?.status, open, startPolling, stopPolling])

  /* ---- 组件卸载时清理定时器 ---- */
  useEffect(() => {
    return () => stopPolling()
  }, [stopPolling])

  /* ============================================================
     操作处理
     ============================================================ */

  const handleStart = async () => {
    if (!runId) return
    setActionLoading((prev) => ({ ...prev, start: true }))
    try {
      await runPipeline(runId)
      message.success('全流程已启动')
      await fetchStatus()
    } catch {
      // 错误已由拦截器处理
    } finally {
      setActionLoading((prev) => ({ ...prev, start: false }))
    }
  }

  const handleResume = async () => {
    if (!runId) return
    setActionLoading((prev) => ({ ...prev, resume: true }))
    try {
      await resumePipeline(runId)
      message.success('全流程已恢复')
      await fetchStatus()
    } catch {
      // 错误已由拦截器处理
    } finally {
      setActionLoading((prev) => ({ ...prev, resume: false }))
    }
  }

  const handlePause = async () => {
    if (!runId) return
    setActionLoading((prev) => ({ ...prev, pause: true }))
    try {
      await pausePipeline(runId)
      message.success('全流程已暂停')
      await fetchStatus()
    } catch {
      // 错误已由拦截器处理
    } finally {
      setActionLoading((prev) => ({ ...prev, pause: false }))
    }
  }

  const handleReset = async () => {
    if (!runId) return
    setActionLoading((prev) => ({ ...prev, reset: true }))
    try {
      await resetPipeline(runId)
      message.success('全流程已重置')
      await fetchStatus()
    } catch {
      // 错误已由拦截器处理
    } finally {
      setActionLoading((prev) => ({ ...prev, reset: false }))
    }
  }

  const handleSkip = async (stepKey: string, stepName: string) => {
    if (!runId) return
    setActionLoading((prev) => ({ ...prev, [`skip_${stepKey}`]: true }))
    try {
      await skipStep(runId, stepKey)
      message.success(`步骤「${stepName}」已跳过`)
      await fetchStatus()
    } catch {
      // 错误已由拦截器处理
    } finally {
      setActionLoading((prev) => ({ ...prev, [`skip_${stepKey}`]: false }))
    }
  }

  const handleRetry = async (stepKey: string, stepName: string) => {
    if (!runId) return
    setActionLoading((prev) => ({ ...prev, [`retry_${stepKey}`]: true }))
    try {
      await retryStep(runId, stepKey)
      message.success(`步骤「${stepName}」重试中`)
      await fetchStatus()
    } catch {
      // 错误已由拦截器处理
    } finally {
      setActionLoading((prev) => ({ ...prev, [`retry_${stepKey}`]: false }))
    }
  }

  /* ============================================================
     渲染数据准备
     ============================================================ */

  const pipelineStatus = status?.status ?? 'idle'
  const statusInfo = PIPELINE_STATUS_MAP[pipelineStatus] ?? PIPELINE_STATUS_MAP.idle
  const progress = status?.progress

  /** 合并本地步骤定义与 API 返回数据（API 数据优先） */
  const displaySteps = PIPELINE_STEPS.map((localStep) => {
    const apiStep = status?.steps.find((s) => s.key === localStep.key)
    return {
      key: localStep.key,
      name: localStep.name,
      description: localStep.description,
      status: (apiStep?.status ?? 'pending') as PipelineStep['status'],
      mode: apiStep?.mode ?? '',
      mode_label: apiStep?.mode_label ?? '',
      error: apiStep?.error ?? '',
      message: apiStep?.message ?? '',
    }
  })

  /** 构建 Steps items */
  const stepsItems: StepItem[] = displaySteps.map((step) => {
    const antdStatus = mapStepStatus(step.status)
    const icon = getStepIcon(step.status)
    const isFinished = step.status === 'completed'
    const isSkipped = step.status === 'skipped'
    const canSkip = step.status === 'pending' || step.status === 'running'
    const canRetry = step.status === 'failed'

    const item: StepItem = {
      title: (
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
          <span
            style={{
              fontFamily: 'var(--font-serif)',
              fontWeight: 600,
              color: 'var(--ink)',
              fontSize: 14,
            }}
          >
            {step.name}
          </span>
          {/* 完成后显示模式标签 */}
          {isFinished && step.mode_label && (
            <Tag
              style={{
                fontSize: 11,
                margin: 0,
                lineHeight: '20px',
                background: 'rgba(91, 117, 83, 0.08)',
                color: 'var(--sage)',
                border: '1px solid rgba(91, 117, 83, 0.25)',
                borderRadius: 3,
              }}
            >
              {step.mode_label}
            </Tag>
          )}
          {/* 跳过标识 */}
          {isSkipped && (
            <Tag
              style={{
                fontSize: 11,
                margin: 0,
                lineHeight: '20px',
                background: 'rgba(90, 107, 127, 0.08)',
                color: 'var(--slate)',
                border: '1px solid rgba(90, 107, 127, 0.2)',
                borderRadius: 3,
              }}
            >
              已跳过
            </Tag>
          )}
        </div>
      ),
      description: (
        <div>
          {/* 步骤描述 */}
          <div style={{ fontSize: 12, color: 'var(--slate)', marginBottom: 6, lineHeight: 1.6 }}>
            {step.description}
          </div>

          {/* 失败时显示错误信息 */}
          {step.status === 'failed' && step.error && (
            <Alert
              type="error"
              showIcon
              message={step.error}
              style={{
                marginTop: 4,
                marginBottom: 8,
                fontSize: 12,
                borderRadius: 3,
                padding: '4px 12px',
              }}
            />
          )}

          {/* 未完成步骤的操作按钮 */}
          {!isFinished && !isSkipped && (canSkip || canRetry) && (
            <Space size="small" style={{ marginTop: 2 }}>
              {canSkip && (
                <Button
                  size="small"
                  type="text"
                  icon={<StepForwardOutlined />}
                  loading={!!actionLoading[`skip_${step.key}`]}
                  onClick={() => handleSkip(step.key, step.name)}
                  style={{
                    fontSize: 12,
                    color: 'var(--slate)',
                    padding: '0 6px',
                    height: 24,
                  }}
                >
                  跳过
                </Button>
              )}
              {canRetry && (
                <Button
                  size="small"
                  type="text"
                  icon={<ReloadOutlined />}
                  loading={!!actionLoading[`retry_${step.key}`]}
                  onClick={() => handleRetry(step.key, step.name)}
                  style={{
                    fontSize: 12,
                    color: 'var(--amber)',
                    padding: '0 6px',
                    height: 24,
                  }}
                >
                  重试
                </Button>
              )}
            </Space>
          )}
        </div>
      ),
      status: antdStatus,
    }

    if (icon) {
      item.icon = icon
    }

    return item
  })

  /* ============================================================
     Drawer 标题
     ============================================================ */

  const drawerTitle = (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <ThunderboltOutlined style={{ color: 'var(--gold)', fontSize: 18 }} />
      <span
        style={{
          fontFamily: 'var(--font-serif)',
          fontWeight: 600,
          color: 'var(--ink)',
          fontSize: 16,
        }}
      >
        全流程自动化
      </span>
      {status && (
        <Tag
          color={statusInfo.color}
          style={{ marginLeft: 4, borderRadius: 3, fontWeight: 500 }}
        >
          {statusInfo.label}
        </Tag>
      )}
      {runId && (
        <Tooltip title="手动刷新">
          <Button
            size="small"
            type="text"
            icon={<SyncOutlined spin={loading} />}
            onClick={() => {
              setLoading(true)
              fetchStatus().finally(() => setLoading(false))
            }}
            style={{ color: 'var(--slate)', marginLeft: 'auto' }}
          />
        </Tooltip>
      )}
    </div>
  )

  /* ============================================================
     渲染
     ============================================================ */

  return (
    <Drawer
      title={drawerTitle}
      open={open}
      onClose={onClose}
      width={580}
      placement="right"
      styles={{
        header: {
          borderBottom: '2px solid var(--gold)',
          padding: '16px 24px',
        },
        body: {
          padding: '20px 24px',
          background: 'var(--parchment)',
          overflowY: 'auto',
        },
        footer: {
          borderTop: '1px solid #E0D9C8',
          padding: '12px 24px',
          background: 'var(--porcelain)',
        },
      }}
      footer={
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            gap: 12,
          }}
        >
          <Text
            style={{
              fontSize: 12,
              color: 'var(--slate)',
              fontFamily: 'var(--font-mono)',
            }}
          >
            {runId ? `RUN · ${runId.substring(0, 12)}` : '无运行实例'}
          </Text>
          <Space>
            {/* 开始 / 恢复按钮（根据状态自动切换） */}
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={pipelineStatus === 'paused' ? handleResume : handleStart}
              loading={!!actionLoading.start || !!actionLoading.resume}
              disabled={
                pipelineStatus === 'running' ||
                pipelineStatus === 'completed' ||
                !runId
              }
            >
              {pipelineStatus === 'paused' ? '恢复' : '开始'}
            </Button>
            {/* 暂停按钮 */}
            <Button
              icon={<PauseCircleOutlined />}
              onClick={handlePause}
              loading={!!actionLoading.pause}
              disabled={pipelineStatus !== 'running'}
            >
              暂停
            </Button>
            {/* 重置按钮（需确认） */}
            <Popconfirm
              title="确定重置流程？"
              description="重置后所有步骤状态将清空，不可恢复。"
              onConfirm={handleReset}
              okText="确定"
              cancelText="取消"
              okButtonProps={{ danger: true }}
            >
              <Button
                icon={<ReloadOutlined />}
                loading={!!actionLoading.reset}
                disabled={!runId}
              >
                重置
              </Button>
            </Popconfirm>
          </Space>
        </div>
      }
    >
      {/* ---- 无 runId ---- */}
      {!runId && (
        <Empty
          description="请先上传文件并创建运行实例"
          style={{ marginTop: 100 }}
        />
      )}

      {/* ---- 加载中 ---- */}
      {runId && loading && !status && (
        <div style={{ textAlign: 'center', padding: '100px 0' }}>
          <Spin size="large" />
          <div
            style={{
              marginTop: 16,
              color: 'var(--slate)',
              fontSize: 13,
            }}
          >
            加载进度中...
          </div>
        </div>
      )}

      {/* ---- 进度内容 ---- */}
      {runId && status && (
        <>
          {/* ===== 进度概览区 ===== */}
          <div
            style={{
              background: 'var(--porcelain)',
              borderRadius: 6,
              padding: '16px 20px',
              border: '1px solid #E0D9C8',
              marginBottom: 20,
            }}
          >
            {/* 百分比标题行 */}
            <div
              style={{
                display: 'flex',
                justifyContent: 'space-between',
                alignItems: 'baseline',
                marginBottom: 10,
              }}
            >
              <span
                style={{
                  fontFamily: 'var(--font-serif)',
                  fontSize: 14,
                  fontWeight: 600,
                  color: 'var(--ink)',
                }}
              >
                执行进度
              </span>
              <span
                style={{
                  fontFamily: 'var(--font-mono)',
                  fontSize: 24,
                  fontWeight: 700,
                  color: 'var(--gold)',
                }}
              >
                {progress?.percentage ?? 0}%
              </span>
            </div>

            {/* 进度条 */}
            <Progress
              percent={progress?.percentage ?? 0}
              strokeColor={{ from: '#B8954A', to: '#5B7553' }}
              trailColor="#EDE8DC"
              showInfo={false}
              strokeWidth={10}
            />

            {/* 统计行 */}
            <div
              style={{
                display: 'flex',
                gap: 20,
                marginTop: 10,
                fontSize: 12,
              }}
            >
              <span style={{ color: 'var(--sage)' }}>
                <CheckCircleOutlined style={{ marginRight: 4 }} />
                完成 {progress?.completed ?? 0}/{progress?.total ?? 9}
              </span>
              <span style={{ color: 'var(--slate)' }}>
                <MinusCircleOutlined style={{ marginRight: 4 }} />
                跳过 {progress?.skipped ?? 0}
              </span>
              <span style={{ color: 'var(--crimson)' }}>
                <CloseCircleOutlined style={{ marginRight: 4 }} />
                失败 {progress?.failed ?? 0}
              </span>
            </div>

            {/* LLM 信息 */}
            {status.llm_model && (
              <>
                <Divider style={{ margin: '12px 0 8px', borderColor: '#E8E2D4' }} />
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    fontSize: 11,
                  }}
                >
                  <span style={{ color: 'var(--slate)' }}>
                    LLM 状态：
                    {status.llm_available ? (
                      <Tag
                        color="success"
                        style={{ fontSize: 10, marginLeft: 4, padding: '0 6px' }}
                      >
                        可用
                      </Tag>
                    ) : (
                      <Tag
                        color="error"
                        style={{ fontSize: 10, marginLeft: 4, padding: '0 6px' }}
                      >
                        不可用
                      </Tag>
                    )}
                  </span>
                  <span
                    style={{
                      color: 'var(--slate-light)',
                      fontFamily: 'var(--font-mono)',
                    }}
                  >
                    {status.llm_model}
                  </span>
                </div>
              </>
            )}
          </div>

          {/* ===== 步骤列表 ===== */}
          <Steps
            current={status.current_step ?? 0}
            direction="vertical"
            size="small"
            items={stepsItems}
          />
        </>
      )}
    </Drawer>
  )
}

export default PipelineProgress
