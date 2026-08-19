/**
 * 交付成果展示面板
 * - 展示任务绑定的交付成果
 * - 支持生成、下载、重新生成、保存为模板
 */
import React, { useState, useCallback } from 'react'
import {
  Button,
  Card,
  Space,
  Tag,
  Typography,
  List,
  Empty,
  Spin,
  Tooltip,
  Popconfirm,
  Input,
  Modal,
  Select,
  Alert,
} from 'antd'
import { message } from '../../utils/messageBridge'
import {
  DownloadOutlined,
  ReloadOutlined,
  FileTextOutlined,
  SaveOutlined,
  BuildOutlined,
  ExclamationCircleOutlined,
  ThunderboltOutlined,
  CloudDownloadOutlined,
} from '@ant-design/icons'
import type { DeliverableArtifact, Task } from '../../types'
import {
  generateAllDeliverables,
  generateTaskDeliverable,
  getDeliverables,
  getArtifactDownloadUrl,
  getAllDeliverablesDownloadUrl,
  saveAsTemplate,
} from '../../services/deliverable'

const { Text, Paragraph } = Typography

interface DeliverablePanelProps {
  runId: string
  tasks: Task[]
  selectedTask: Task | null
}

const STATUS_COLORS: Record<string, string> = {
  '已生成': 'success',
  '生成失败': 'error',
  '待生成': 'default',
  '已复核': 'blue',
}

const REUSE_SOURCE_COLORS: Record<string, string> = {
  '模板复用': 'blue',
  '新生成': 'green',
  '模板微调': 'orange',
  '已沉淀为模板': 'purple',
}

const DeliverablePanel: React.FC<DeliverablePanelProps> = ({ runId, tasks, selectedTask }) => {
  const [artifacts, setArtifacts] = useState<DeliverableArtifact[]>([])
  const [loading, setLoading] = useState(false)
  const [generatingAll, setGeneratingAll] = useState(false)
  const [generatingTaskId, setGeneratingTaskId] = useState<string | null>(null)
  const [saveTemplateOpen, setSaveTemplateOpen] = useState(false)
  const [saveTemplateArtifactId, setSaveTemplateArtifactId] = useState('')
  const [templateName, setTemplateName] = useState('')
  const [savingTemplate, setSavingTemplate] = useState(false)
  // 任务选择：用于按任务生成 LLM 深度设计成果
  const [selectedTaskId, setSelectedTaskId] = useState<string | undefined>(undefined)

  /** 任务下拉选项：序号 + 任务名称 */
  const taskOptions = tasks.map((t, idx) => ({
    label: `${idx + 1}. ${t.task_name || t.task_id}`,
    value: t.task_id,
  }))

  /** 加载交付成果 */
  const loadArtifacts = useCallback(async () => {
    if (!runId) return
    setLoading(true)
    try {
      const res = await getDeliverables(runId)
      if (res.success && res.data) {
        setArtifacts(res.data.items || [])
      }
    } catch (err: any) {
      // 静默处理，首次可能没有数据
    } finally {
      setLoading(false)
    }
  }, [runId])

  /** 生成全部交付成果（批量，规则/模板模式，不调用 LLM） */
  const handleGenerateAll = async () => {
    if (!runId) return
    setGeneratingAll(true)
    try {
      const res = await generateAllDeliverables(runId)
      if (res.success) {
        message.success(res.message)
        await loadArtifacts()
      } else {
        message.error(res.message || '生成失败')
      }
    } catch (err: any) {
      // suppressErrorMessage 已开启，这里给一个友好兜底提示
      message.error('生成失败，请稍后重试或改为按单个任务生成')
    } finally {
      setGeneratingAll(false)
    }
  }

  /** 为单个任务生成（LLM 深度设计）：供任务选择按钮调用 */
  const handleGenerateSelectedTask = async () => {
    if (!runId || !selectedTaskId) {
      message.warning('请先选择一个任务')
      return
    }
    setGeneratingTaskId(selectedTaskId)
    try {
      const res = await generateTaskDeliverable(runId, selectedTaskId)
      if (res.success) {
        message.success('已为该任务生成 LLM 交付成果')
        await loadArtifacts()
      } else {
        message.error(res.message || '生成失败')
      }
    } catch (err: any) {
      message.error('生成失败，请稍后重试')
    } finally {
      setGeneratingTaskId(null)
    }
  }

  /** 为单个任务重新生成（已有成果条目上的重新生成按钮）
   * 需求7：后端会自动切换为另一套未用过的模板
   */
  const handleGenerateTask = async (taskId: string) => {
    if (!runId) return
    setGeneratingTaskId(taskId)
    try {
      const res = await generateTaskDeliverable(runId, taskId)
      if (res.success) {
        // 需求7：根据 template_switched 给出不同提示
        if (res.template_switched) {
          message.success(`已切换为「${res.artifact?.template_name || '新模板'}」重新生成`)
        } else {
          message.success(res.message || '已重新生成')
        }
        await loadArtifacts()
      } else {
        message.error(res.message || '重新生成失败')
      }
    } catch (err: any) {
      message.error('生成失败，请稍后重试')
    } finally {
      setGeneratingTaskId(null)
    }
  }

  /** 下载文件 */
  const handleDownload = (artifactId: string) => {
    const url = getArtifactDownloadUrl(runId, artifactId)
    window.open(url, '_blank')
  }

  /** 打开保存模板弹窗 */
  const openSaveTemplate = (artifact: DeliverableArtifact) => {
    setSaveTemplateArtifactId(artifact.artifact_id)
    setTemplateName(artifact.template_name || artifact.deliverable_name.replace(/《|》/g, ''))
    setSaveTemplateOpen(true)
  }

  /** 保存为模板 */
  const handleSaveTemplate = async () => {
    if (!templateName.trim()) {
      message.warning('请输入模板名称')
      return
    }
    setSavingTemplate(true)
    try {
      const res = await saveAsTemplate(runId, saveTemplateArtifactId, templateName.trim())
      if (res.success) {
        message.success(res.message)
        setSaveTemplateOpen(false)
        await loadArtifacts()
      } else {
        message.error(res.message || '保存失败')
      }
    } catch (err: any) {
      message.error(err?.message || '请求失败')
    } finally {
      setSavingTemplate(false)
    }
  }

  /** 过滤显示的成果
   * 优先级：父级 selectedTask > 本面板任务选择 selectedTaskId > 全部
   * 选中任务生成后自动只展示该任务的成果，便于查看与下载
   */
  const focusTaskId = selectedTask?.task_id || selectedTaskId
  const displayArtifacts = focusTaskId
    ? artifacts.filter((a) => a.task_id === focusTaskId)
    : artifacts

  return (
    <div style={{ padding: '8px 0' }}>
      {/* 操作栏 */}
      <Space wrap style={{ marginBottom: 12 }}>
        <Button
          type="primary"
          icon={<BuildOutlined />}
          onClick={handleGenerateAll}
          loading={generatingAll}
          size="small"
        >
          生成全部（规则/模板）
        </Button>
        <Button
          icon={<ReloadOutlined />}
          onClick={loadArtifacts}
          loading={loading}
          size="small"
        >
          刷新
        </Button>
        <Tooltip title={artifacts.length > 0 ? '下载全部已生成的 docx 交付成果（zip 打包）' : '请先生成交付成果'}>
          <Button
            icon={<CloudDownloadOutlined />}
            onClick={() => {
              if (!runId || artifacts.length === 0) {
                message.warning('请先生成交付成果')
                return
              }
              window.open(getAllDeliverablesDownloadUrl(runId), '_blank')
            }}
            disabled={artifacts.length === 0}
            size="small"
            type="default"
          >
            下载全部交付成果
          </Button>
        </Tooltip>
        {selectedTask && (
          <Text type="secondary" style={{ fontSize: 12 }}>
            当前任务: {selectedTask.task_name}
          </Text>
        )}
      </Space>

      {/* 按任务生成（LLM 深度设计） */}
      <div style={{ marginBottom: 12, padding: 8, background: 'rgba(22,119,255,0.04)', borderRadius: 6 }}>
        <Space wrap>
          <Text type="secondary" style={{ fontSize: 12 }}>选择任务：</Text>
          <Select
            showSearch
            placeholder="选择一个任务（序号 + 任务名称）"
            value={selectedTaskId}
            onChange={(val) => setSelectedTaskId(val)}
            options={taskOptions}
            style={{ minWidth: 280 }}
            size="small"
            optionFilterProp="label"
          />
          <Button
            type="primary"
            ghost
            icon={<ThunderboltOutlined />}
            size="small"
            loading={!!generatingTaskId && generatingTaskId === selectedTaskId}
            disabled={!selectedTaskId}
            onClick={handleGenerateSelectedTask}
          >
            为选中任务生成
          </Button>
        </Space>
      </div>

      {/* 进度提示 */}
      {(generatingAll || generatingTaskId) && (
        <Alert
          type="info"
          showIcon
          message={generatingAll ? '正在批量生成交付成果（规则/模板模式），请稍候…' : '正在为单个任务调用 LLM 深度设计，可能需要数十秒，请勿关闭…'}
          style={{ marginBottom: 12 }}
        />
      )}

      {/* 成果列表 */}
      {displayArtifacts.length > 0 ? (
        <List
          dataSource={displayArtifacts}
          renderItem={(artifact) => (
            <List.Item style={{ padding: '8px 0' }}>
              <Card
                size="small"
                style={{ width: '100%' }}
                className="ledger-card"
                title={
                  <Space wrap>
                    <FileTextOutlined style={{ color: 'var(--gold)' }} />
                    <Text strong style={{ fontSize: 13 }}>{artifact.deliverable_name}</Text>
                    <Tag color={STATUS_COLORS[artifact.status] || 'default'}>{artifact.status}</Tag>
                    <Tag color={REUSE_SOURCE_COLORS[artifact.reuse_source] || 'default'}>{artifact.reuse_source}</Tag>
                    {/* 需求7：归并成果标识 */}
                    {artifact.is_merged && (
                      <Tag color="purple">
                        归并 · 覆盖 {artifact.covered_task_count || 0} 项任务
                      </Tag>
                    )}
                  </Space>
                }
                extra={
                  <Space>
                    {artifact.status === '已生成' && (
                      <Button
                        size="small"
                        icon={<DownloadOutlined />}
                        onClick={() => handleDownload(artifact.artifact_id)}
                      >
                        下载
                      </Button>
                    )}
                    {/* 需求7：重新生成会切换模板 */}
                    <Tooltip title="重新生成（将自动切换为另一套模板）">
                      <Button
                        size="small"
                        icon={<ReloadOutlined />}
                        loading={generatingTaskId === artifact.task_id}
                        onClick={() => handleGenerateTask(artifact.task_id)}
                      />
                    </Tooltip>
                    <Tooltip title="保存为模板">
                      <Button
                        size="small"
                        icon={<SaveOutlined />}
                        onClick={() => openSaveTemplate(artifact)}
                      />
                    </Tooltip>
                  </Space>
                }
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                  <Space wrap size="small">
                    <Text type="secondary" style={{ fontSize: 12 }}>模块: {artifact.service_module || '-'}</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>类型: {artifact.deliverable_type}</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>模板: {artifact.template_name || artifact.template_key}</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>复核: {artifact.review_status}</Text>
                  </Space>

                  {/* 需求7：归并模式下展示覆盖任务清单 */}
                  {artifact.is_merged && artifact.covered_task_names && artifact.covered_task_names.length > 0 && (
                    <div style={{ padding: '6px 8px', background: 'rgba(114,46,209,0.04)', border: '1px solid rgba(114,46,209,0.15)', borderRadius: 4 }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>本成果覆盖任务清单：</Text>
                      <ul style={{ margin: '2px 0 0 16px', paddingLeft: 16, fontSize: 12, color: '#555' }}>
                        {artifact.covered_task_names.slice(0, 6).map((name, idx) => (
                          <li key={idx}>{name}</li>
                        ))}
                        {artifact.covered_task_names.length > 6 && (
                          <li style={{ listStyle: 'none' }}>
                            <Text type="secondary">…… 共 {artifact.covered_task_names.length} 项</Text>
                          </li>
                        )}
                      </ul>
                    </div>
                  )}

                  {artifact.ai_design_reason && (
                    <Paragraph type="secondary" style={{ fontSize: 12, margin: 0 }}>
                      <ExclamationCircleOutlined style={{ marginRight: 4, color: 'var(--gold)' }} />
                      {artifact.ai_design_reason}
                    </Paragraph>
                  )}
                  {artifact.content_outline && artifact.content_outline.length > 0 && (
                    <div style={{ fontSize: 12, color: '#666' }}>
                      <Text type="secondary" style={{ fontSize: 11 }}>内容大纲:</Text>
                      <ol style={{ margin: '4px 0', paddingLeft: 16 }}>
                        {artifact.content_outline.map((line, idx) => (
                          <li key={idx}>{line}</li>
                        ))}
                      </ol>
                    </div>
                  )}
                </div>
              </Card>
            </List.Item>
          )}
        />
      ) : (
        <Empty
          description={
            <div>
              <p>暂无交付成果</p>
              <Button size="small" type="primary" onClick={handleGenerateAll} loading={generatingAll}>
                生成全部交付成果
              </Button>
            </div>
          }
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      )}

      {/* 保存模板弹窗 */}
      <Modal
        title="保存为模板"
        open={saveTemplateOpen}
        onCancel={() => setSaveTemplateOpen(false)}
        onOk={handleSaveTemplate}
        confirmLoading={savingTemplate}
        okText="保存"
        cancelText="取消"
      >
        <div style={{ marginBottom: 8 }}>
          <Text type="secondary">模板名称</Text>
        </div>
        <Input
          value={templateName}
          onChange={(e) => setTemplateName(e.target.value)}
          placeholder="请输入模板名称"
        />
      </Modal>
    </div>
  )
}

export default DeliverablePanel
