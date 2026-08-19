/**
 * 按服务模块批量复核面板（需求6）
 *
 * 功能：
 * - 自动按 service_module 分组统计任务
 * - 每个模块展示任务总数、待复核数量
 * - 提供"全部已确认"、"全部需修改"、"全部剔除"三个一键操作
 * - 只对模块下「待复核」状态的任务进行批量标记，已确认/已剔除的不会重复处理
 *
 * 调用后端：PATCH /api/tasks/{run_id}/batch-review
 */
import React, { useMemo, useState } from 'react'
import { Card, Tag, Space, Button, Tooltip, Popconfirm, Empty, Spin, Typography } from 'antd'
import { message } from '../../utils/messageBridge'
import {
  CheckCircleOutlined,
  WarningOutlined,
  DeleteOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { batchMarkReview } from '../../services/task'
import type { Task } from '../../types'

const { Text } = Typography

interface ModuleBatchReviewPanelProps {
  runId: string
  tasks: Task[]
  onReviewed?: () => void
}

interface ModuleGroup {
  module: string
  total: number
  pending: number
  confirmed: number
  needModify: number
  rejected: number
  taskIds: string[]
  pendingTaskIds: string[]
}

const ModuleBatchReviewPanel: React.FC<ModuleBatchReviewPanelProps> = ({
  runId,
  tasks,
  onReviewed,
}) => {
  const [loadingModule, setLoadingModule] = useState<string | null>(null)

  /** 按 service_module 分组统计 */
  const groups = useMemo<ModuleGroup[]>(() => {
    const map = new Map<string, ModuleGroup>()
    for (const t of tasks) {
      const mod = t.service_module || '未分类'
      if (!map.has(mod)) {
        map.set(mod, {
          module: mod,
          total: 0,
          pending: 0,
          confirmed: 0,
          needModify: 0,
          rejected: 0,
          taskIds: [],
          pendingTaskIds: [],
        })
      }
      const g = map.get(mod)!
      g.total += 1
      g.taskIds.push(t.task_id)
      const status = t.review_status || '待复核'
      if (status === '待复核') {
        g.pending += 1
        g.pendingTaskIds.push(t.task_id)
      } else if (status === '已确认') {
        g.confirmed += 1
      } else if (status === '需修改') {
        g.needModify += 1
      } else if (status === '剔除') {
        g.rejected += 1
      }
    }
    // 按"待复核数"降序，便于优先处理
    return Array.from(map.values()).sort((a, b) => b.pending - a.pending)
  }, [tasks])

  /** 批量标记 */
  const handleBatch = async (module: string, status: '已确认' | '需修改' | '剔除') => {
    if (!runId) return
    setLoadingModule(module)
    try {
      const res = await batchMarkReview(runId, {
        status,
        service_module: module,
      })
      if (res.success) {
        message.success(res.message)
        onReviewed?.()
      } else {
        message.error(res.message || '批量复核失败')
      }
    } catch (err: any) {
      message.error(err?.message || '批量复核请求失败')
    } finally {
      setLoadingModule(null)
    }
  }

  if (groups.length === 0) {
    return (
      <Card title="按服务模块批量复核" size="small" className="ledger-card" style={{ marginBottom: 12 }}>
        <Empty description="暂无任务，无法按模块批量复核" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </Card>
    )
  }

  return (
    <Card
      title={
        <Space>
          <span>按服务模块批量复核</span>
          <Tag color="gold">{groups.length} 个模块</Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>
            仅作用于「待复核」状态任务，已确认/已剔除不会被重复处理
          </Text>
        </Space>
      }
      size="small"
      className="ledger-card"
      style={{ marginBottom: 12 }}
      extra={
        onReviewed && (
          <Tooltip title="刷新模块统计">
            <Button size="small" type="link" icon={<ReloadOutlined />} onClick={onReviewed} />
          </Tooltip>
        )
      }
    >
      <Spin spinning={!!loadingModule}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
          {groups.map((g) => {
            const allDone = g.pending === 0
            return (
              <div
                key={g.module}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  padding: '6px 12px',
                  background: allDone ? 'rgba(82,196,26,0.04)' : 'rgba(184,149,74,0.04)',
                  border: `1px solid ${allDone ? 'rgba(82,196,26,0.2)' : 'rgba(184,149,74,0.2)'}`,
                  borderRadius: 6,
                }}
              >
                <Space size="middle">
                  <Text strong style={{ fontSize: 13 }}>{g.module}</Text>
                  <Tag>共 {g.total}</Tag>
                  {g.pending > 0 ? (
                    <Tag color="warning">待复核 {g.pending}</Tag>
                  ) : (
                    <Tag color="success">已完成</Tag>
                  )}
                  {g.confirmed > 0 && <Tag color="success">已确认 {g.confirmed}</Tag>}
                  {g.needModify > 0 && <Tag color="orange">需修改 {g.needModify}</Tag>}
                  {g.rejected > 0 && <Tag color="error">剔除 {g.rejected}</Tag>}
                </Space>
                <Space size="small">
                  <Popconfirm
                    title={`确认将「${g.module}」模块下 ${g.pending} 条待复核任务全部标记为「已确认」？`}
                    onConfirm={() => handleBatch(g.module, '已确认')}
                    okText="确认"
                    cancelText="取消"
                    disabled={allDone}
                  >
                    <Button
                      size="small"
                      type="primary"
                      icon={<CheckCircleOutlined />}
                      disabled={allDone}
                      loading={loadingModule === g.module}
                    >
                      全部已确认
                    </Button>
                  </Popconfirm>
                  <Popconfirm
                    title={`将「${g.module}」下 ${g.pending} 条待复核任务标记为「需修改」？`}
                    onConfirm={() => handleBatch(g.module, '需修改')}
                    okText="确认"
                    cancelText="取消"
                    disabled={allDone}
                  >
                    <Button
                      size="small"
                      icon={<WarningOutlined />}
                      disabled={allDone}
                      loading={loadingModule === g.module}
                    >
                      全部需修改
                    </Button>
                  </Popconfirm>
                  <Popconfirm
                    title={`将「${g.module}」下 ${g.pending} 条待复核任务标记为「剔除」？此操作不会删除任务，仅改状态。`}
                    onConfirm={() => handleBatch(g.module, '剔除')}
                    okText="确认"
                    cancelText="取消"
                    disabled={allDone}
                  >
                    <Button
                      size="small"
                      danger
                      icon={<DeleteOutlined />}
                      disabled={allDone}
                      loading={loadingModule === g.module}
                    >
                      全部剔除
                    </Button>
                  </Popconfirm>
                </Space>
              </div>
            )
          })}
        </div>
      </Spin>
    </Card>
  )
}

export default ModuleBatchReviewPanel
