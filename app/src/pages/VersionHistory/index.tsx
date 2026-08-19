/**
 * 页面5: 版本记录
 * - 版本时间线
 * - 每个版本：版本号、保存时间、修改说明、任务数
 * - 查看版本详情（展开显示任务主表快照）
 * - 回退按钮
 */
import React, { useState, useEffect, useCallback } from 'react'
import {
  Card,
  Timeline,
  Button,
  Tag,
  Typography,
  Space,
  Empty,
  Spin,
  Modal,
  Table,
  Popconfirm,
  Alert,
} from 'antd'
import { message } from '../../utils/messageBridge'
import { RollbackOutlined, EyeOutlined, ReloadOutlined, RightOutlined, ClockCircleOutlined, DeleteOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { listVersions, getVersion, restoreVersion, deleteVersion } from '../../services/version'
import { useProjectStore } from '../../stores/projectStore'
import { useTaskStore } from '../../stores/taskStore'
import { useStepStore } from '../../stores/stepStore'
import type { VersionInfo, Task } from '../../types'
import { TASK_FIELDS, STATUS_TAG_COLORS, REVIEW_TAG_COLORS } from '../../utils/constants'
import dayjs from 'dayjs'

const { Title, Text } = Typography

const VersionHistoryPage: React.FC = () => {
  const navigate = useNavigate()
  const { runId } = useProjectStore()
  const { setTasks } = useTaskStore()
  const { setCurrentStep, completeStep } = useStepStore()
  const [loading, setLoading] = useState(false)
  const [versions, setVersions] = useState<VersionInfo[]>([])
  const [detailOpen, setDetailOpen] = useState(false)
  const [detailVersion, setDetailVersion] = useState<VersionInfo | null>(null)
  const [detailTasks, setDetailTasks] = useState<Task[]>([])
  const [detailLoading, setDetailLoading] = useState(false)
  const [rollingBack, setRollingBack] = useState<string | null>(null)
  const [deleting, setDeleting] = useState<string | null>(null)

  /** 加载版本列表 */
  const loadVersions = useCallback(async () => {
    if (!runId) return
    setLoading(true)
    try {
      const res = await listVersions(runId)
      if (res.success) {
        setVersions(res.versions || [])
      }
    } catch {
      // 忽略
    } finally {
      setLoading(false)
    }
  }, [runId])

  useEffect(() => {
    loadVersions()
  }, [runId])

  /** 查看版本详情 */
  const handleViewDetail = async (version: VersionInfo) => {
    if (!runId) return
    setDetailOpen(true)
    setDetailVersion(version)
    setDetailLoading(true)
    try {
      const res = await getVersion(runId, version.version_id)
      if (res.success && res.data?.snapshot) {
        setDetailTasks(res.data.snapshot.tasks || [])
      }
    } catch {
      // 忽略
    } finally {
      setDetailLoading(false)
    }
  }

  /** 回退到指定版本 */
  const handleRollback = async (version: VersionInfo) => {
    if (!runId) return
    setRollingBack(version.version_id)
    try {
      const res = await restoreVersion(runId, version.version_id)
      if (res.success) {
        message.success(res.message)
        // 更新当前任务列表
        const detailRes = await getVersion(runId, version.version_id)
        if (detailRes.success && detailRes.data?.snapshot) {
          setTasks(detailRes.data.snapshot.tasks || [])
        }
      }
    } catch {
      // 忽略
    } finally {
      setRollingBack(null)
    }
  }

  /** 删除指定版本 */
  const handleDelete = async (version: VersionInfo) => {
    if (!runId) return
    setDeleting(version.version_id)
    try {
      const res = await deleteVersion(runId, version.version_id)
      if (res.success) {
        message.success(res.message)
        // 如果当前打开的详情就是被删除版本，关闭详情弹窗并清空详情状态
        if (detailVersion?.version_id === version.version_id) {
          setDetailOpen(false)
          setDetailVersion(null)
          setDetailTasks([])
        }
        // 刷新版本列表
        await loadVersions()
      }
    } catch {
      // 忽略（错误提示由响应拦截器统一处理）
    } finally {
      setDeleting(null)
    }
  }

  /** 进入下一步 */
  const handleNext = () => {
    completeStep(4)
    setCurrentStep(5)
    navigate('/export')
  }

  /** 详情表格列 */
  const detailColumns = [
    { title: '序号', key: '_index', width: 60, render: (_: any, __: any, index: number) => index + 1 },
    { title: '任务名称', dataIndex: 'task_name', key: 'task_name', width: 200, ellipsis: true },
    { title: '服务模块', dataIndex: 'service_module', key: 'service_module', width: 120 },
    { title: '任务类型', dataIndex: 'task_type', key: 'task_type', width: 100 },
    {
      title: '当前状态',
      dataIndex: 'current_status',
      key: 'current_status',
      width: 100,
      render: (val: string) => <Tag color={STATUS_TAG_COLORS[val] || 'default'}>{val}</Tag>,
    },
    {
      title: '复核状态',
      dataIndex: 'review_status',
      key: 'review_status',
      width: 100,
      render: (val: string) => <Tag color={REVIEW_TAG_COLORS[val] || 'default'}>{val}</Tag>,
    },
    { title: '计划完成时间', dataIndex: 'plan_end_date', key: 'plan_end_date', width: 120 },
  ]

  if (!runId) {
    return (
      <div className="page-container">
        <Alert
          message="请先上传文件"
          description="请先在资料上传页面上传文件或加载 Mock 数据"
          type="warning"
          showIcon
          action={<Button type="primary" onClick={() => navigate('/upload')}>去上传</Button>}
        />
      </div>
    )
  }

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <Title level={4} style={{ marginBottom: 4 }}>版本记录</Title>
          <Text type="secondary">查看历史版本，可回退到任意版本</Text>
        </div>
        <Button icon={<ReloadOutlined />} onClick={loadVersions} loading={loading}>
          刷新
        </Button>
      </div>

      <Spin spinning={loading}>
        {versions.length > 0 ? (
          <Card>
            <Timeline
              items={versions.map((version, index) => ({
                key: version.version_id,
                dot: <ClockCircleOutlined style={{ fontSize: 16, color: '#1677ff' }} />,
                children: (
                  <Card
                    size="small"
                    style={{ marginBottom: 0 }}
                    actions={[
                      <Button
                        key="view"
                        type="link"
                        size="small"
                        icon={<EyeOutlined />}
                        onClick={() => handleViewDetail(version)}
                      >
                        查看详情
                      </Button>,
                      <Popconfirm
                        key="rollback"
                        title="确定回退到此版本吗？"
                        description="回退后当前任务列表将被覆盖"
                        onConfirm={() => handleRollback(version)}
                        okText="确定回退"
                        cancelText="取消"
                      >
                        <Button
                          type="link"
                          size="small"
                          danger
                          icon={<RollbackOutlined />}
                          loading={rollingBack === version.version_id}
                        >
                          回退到此版本
                        </Button>
                      </Popconfirm>,
                      <Popconfirm
                        key="delete"
                        title="确认删除该版本？"
                        description="删除后该版本快照不可恢复，不影响当前任务列表。"
                        onConfirm={() => handleDelete(version)}
                        okText="确定删除"
                        cancelText="取消"
                        okButtonProps={{ danger: true }}
                      >
                        <Button
                          type="link"
                          size="small"
                          danger
                          icon={<DeleteOutlined />}
                          loading={deleting === version.version_id}
                        >
                          删除
                        </Button>
                      </Popconfirm>,
                    ].map((btn, idx) => <span key={idx}>{btn}</span>)}
                  >
                    <Space direction="vertical" style={{ width: '100%' }}>
                      <Space>
                        <Tag color="blue">版本 {version.version_number}</Tag>
                        <Text strong>{version.description}</Text>
                      </Space>
                      <Space>
                        <Text type="secondary">保存时间：{version.created_at ? dayjs(version.created_at).format('YYYY-MM-DD HH:mm:ss') : '-'}</Text>
                        <Text type="secondary">任务数：{version.task_count} 条</Text>
                      </Space>
                    </Space>
                  </Card>
                ),
              }))}
            />
          </Card>
        ) : (
          <Empty description="暂无版本记录，请在任务复核页面保存版本" style={{ marginTop: 60 }} />
        )}
      </Spin>

      {/* 版本详情 Modal */}
      <Modal
        title={detailVersion ? `版本 ${detailVersion.version_number} 详情` : '版本详情'}
        open={detailOpen}
        onCancel={() => setDetailOpen(false)}
        footer={[
          <Button key="close" onClick={() => setDetailOpen(false)}>关闭</Button>,
        ]}
        width={1000}
      >
        <Spin spinning={detailLoading}>
          {detailVersion && (
            <div>
              <Space style={{ marginBottom: 16 }}>
                <Tag color="blue">版本 {detailVersion.version_number}</Tag>
                <Text strong>{detailVersion.description}</Text>
                <Text type="secondary">|</Text>
                <Text type="secondary">任务数：{detailVersion.task_count} 条</Text>
                <Text type="secondary">|</Text>
                <Text type="secondary">保存时间：{detailVersion.created_at ? dayjs(detailVersion.created_at).format('YYYY-MM-DD HH:mm:ss') : '-'}</Text>
              </Space>
              <Table<Task>
                columns={detailColumns}
                dataSource={detailTasks}
                rowKey="task_id"
                size="small"
                pagination={{ pageSize: 10 }}
                scroll={{ x: 800 }}
                bordered
              />
            </div>
          )}
        </Spin>
      </Modal>

      <div style={{ textAlign: 'right', marginTop: 16 }}>
        <Button
          type="primary"
          icon={<RightOutlined />}
          onClick={handleNext}
          size="large"
        >
          进入下一步
        </Button>
      </div>
    </div>
  )
}

export default VersionHistoryPage
