/**
 * 页面4: 任务表复核（核心页面）
 * - 顶部操作栏：保存版本、运行颗粒度检查、查看待确认清单、查看风险提示
 * - 18字段可编辑表格
 * - 新增任务按钮
 * - 任务详情抽屉
 * - 颗粒度检查结果Modal
 * - 待确认清单Drawer
 * - 风险提示Drawer
 */
import React, { useState, useEffect, useCallback } from 'react'
import {
  Button,
  Space,
  Modal,
  Drawer,
  Input,
  Select,
  Form,
  Typography,
  Alert,
  Tag,
  List,
  Empty,
  Spin,
  Card,
  Row,
  Col,
} from 'antd'
import { message } from '../../utils/messageBridge'
import {
  SaveOutlined,
  CheckCircleOutlined,
  WarningOutlined,
  AlertOutlined,
  PlusOutlined,
  ReloadOutlined,
  HistoryOutlined,
  ExclamationCircleOutlined,
  SafetyCertificateOutlined,
  BuildOutlined,
} from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import TaskEditableTable from '../../components/EditableTable/TaskEditableTable'
import TaskDetailDrawer from '../../components/EditableTable/TaskDetailDrawer'
import AddTaskModal from '../../components/EditableTable/AddTaskModal'
import DeliverablePanel from '../../components/Deliverables/DeliverablePanel'
import ModuleBatchReviewPanel from '../../components/BatchReview/ModuleBatchReviewPanel'
import { getTasks, updateTask, addTask, deleteTask, markReview, checkGranularity, validateReport } from '../../services/task'
import { generatePending, getPending, updatePendingItem, generateRisk, getRisk } from '../../services/review'
import { saveVersion } from '../../services/version'
import { useProjectStore } from '../../stores/projectStore'
import { useTaskStore } from '../../stores/taskStore'
import { useStepStore } from '../../stores/stepStore'
import type { Task, GranularityCheckResult, PendingItem, RiskItem, ValidationResult } from '../../types'
import { REVIEW_STATUS, RISK_SEVERITY_COLORS, STATUS_TAG_COLORS } from '../../utils/constants'

const { Title, Text, Paragraph } = Typography

const TaskReviewPage: React.FC = () => {
  const navigate = useNavigate()
  const { runId } = useProjectStore()
  const { tasks, setTasks, updateTaskInStore, addTaskToStore, removeTaskFromStore, pendingItems, setPendingItems, riskItems, setRiskItems, granularityResult, setGranularityResult } = useTaskStore()
  const { setCurrentStep, completeStep } = useStepStore()

  const [loading, setLoading] = useState(false)
  const [detailOpen, setDetailOpen] = useState(false)
  const [addModalOpen, setAddModalOpen] = useState(false)
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [granularityModalOpen, setGranularityModalOpen] = useState(false)
  const [pendingDrawerOpen, setPendingDrawerOpen] = useState(false)
  const [riskDrawerOpen, setRiskDrawerOpen] = useState(false)
  const [saveVersionModalOpen, setSaveVersionModalOpen] = useState(false)
  const [checking, setChecking] = useState(false)
  const [generatingPending, setGeneratingPending] = useState(false)
  const [generatingRisk, setGeneratingRisk] = useState(false)
  const [savingVersion, setSavingVersion] = useState(false)
  const [deliverableDrawerOpen, setDeliverableDrawerOpen] = useState(false)
  const [versionForm] = Form.useForm()
  // 校验相关状态
  const [validating, setValidating] = useState(false)
  const [validationResult, setValidationResult] = useState<ValidationResult | null>(null)
  const [validationModalOpen, setValidationModalOpen] = useState(false)
  const [validationPassed, setValidationPassed] = useState(false)
  // 待确认清单编辑状态
  const [editingPendingId, setEditingPendingId] = useState<string | null>(null)
  const [pendingEditValues, setPendingEditValues] = useState<Record<string, any>>({})
  const [savingPendingId, setSavingPendingId] = useState<string | null>(null)

  /** 加载任务列表 */
  const loadTasks = useCallback(async () => {
    if (!runId) return
    setLoading(true)
    try {
      const res = await getTasks(runId, { suppressErrorMessage: true })
      if (res.success && res.data) {
        setTasks(res.data.tasks || [])
      }
    } catch {
      // 忽略
    } finally {
      setLoading(false)
    }
  }, [runId, setTasks])

  /** 加载待确认清单 */
  const loadPending = useCallback(async () => {
    if (!runId) return
    try {
      const res = await getPending(runId, { suppressErrorMessage: true })
      if (res.success && res.data) {
        const items = (res.data.items || []).map((item: any, idx: number) => ({
          ...item,
          item_id: item.item_id || `pending_${idx}_${Math.random().toString(36).slice(2, 8)}`,
          status: item.status || '待确认',
          confirmed_value: item.confirmed_value || '',
        }))
        setPendingItems(items)
      }
    } catch {
      // 忽略
    }
  }, [runId, setPendingItems])

  /** 进入待确认事项编辑 */
  const startPendingEdit = (item: PendingItem) => {
    setEditingPendingId(item.item_id)
    setPendingEditValues({
      pending_item: item.pending_item,
      related_tasks: item.related_tasks,
      reason: item.reason,
      suggest_confirm_to: item.suggest_confirm_to,
      impact_if_not_confirmed: item.impact_if_not_confirmed,
      confirmed_value: item.confirmed_value,
      status: item.status,
    })
  }

  /** 取消待确认事项编辑 */
  const cancelPendingEdit = () => {
    setEditingPendingId(null)
    setPendingEditValues({})
  }

  /** 保存待确认事项 */
  const savePendingEdit = async (itemId: string) => {
    if (!runId) return
    setSavingPendingId(itemId)
    try {
      const res = await updatePendingItem(runId, itemId, pendingEditValues)
      if (res.success) {
        // 更新本地状态
        const updatedItems = pendingItems.map((item) =>
          item.item_id === itemId ? { ...item, ...pendingEditValues } : item
        )
        setPendingItems(updatedItems)
        setEditingPendingId(null)
        setPendingEditValues({})
        message.success('已保存')
      } else {
        message.error(res.message || '保存失败')
      }
    } catch (err: any) {
      message.error(err?.message || '保存请求失败')
    } finally {
      setSavingPendingId(null)
    }
  }

  /** 加载风险提示 */
  const loadRisk = useCallback(async () => {
    if (!runId) return
    try {
      const res = await getRisk(runId, { suppressErrorMessage: true })
      if (res.success && res.data) {
        setRiskItems(res.data.risks || [])
      }
    } catch {
      // 忽略
    }
  }, [runId, setRiskItems])

  useEffect(() => {
    loadTasks()
    loadPending()
    loadRisk()
  }, [runId])

  /** 更新任务 */
  const handleUpdateTask = async (taskId: string, updates: Partial<Task>) => {
    if (!runId) return
    try {
      const res = await updateTask(runId, taskId, updates)
      if (res.success) {
        updateTaskInStore(taskId, updates)
        // 同步更新当前选中任务，避免详情抽屉显示旧值
        if (selectedTask && selectedTask.task_id === taskId) {
          setSelectedTask({ ...selectedTask, ...updates })
        }
      }
    } catch {
      // 忽略
    }
  }

  /** 删除任务 */
  const handleDeleteTask = async (taskId: string) => {
    if (!runId) return
    try {
      const res = await deleteTask(runId, taskId)
      if (res.success) {
        removeTaskFromStore(taskId)
        message.success('任务已删除')
      }
    } catch {
      // 忽略
    }
  }

  /** 添加任务 */
  const handleAddTask = async (taskData: Omit<Task, 'task_id' | 'created_at' | 'updated_at'>) => {
    if (!runId) return
    try {
      const res = await addTask(runId, taskData)
      if (res.success && res.data) {
        addTaskToStore(res.data)
        setAddModalOpen(false)
      }
    } catch {
      // 忽略
    }
  }

  /** 标记复核状态 */
  const handleMarkReview = async (taskId: string, status: string) => {
    if (!runId) return
    try {
      const res = await markReview(runId, taskId, status)
      if (res.success) {
        updateTaskInStore(taskId, { review_status: status })
        message.success(`已标记为: ${status}`)
      }
    } catch {
      // 忽略
    }
  }

  /** 查看详情 */
  const handleViewDetail = (task: Task) => {
    setSelectedTask(task)
    setDetailOpen(true)
  }

  /** 归一化颗粒度检查结果
   * 保证返回标准字段：summary（中文）/ need_split / missing_fields / client_data_issues / deliverable_issues
   * 绝不在 summary 中展示原始 JSON（dict 或 JSON 字符串均视为无效，回退到中文兜底文案）
   * 兼容 LLM 返回 {passed, issue_count} 的非标准格式
   */
  const normalizeGranularityResult = (raw: any): GranularityCheckResult => {
    if (!raw || typeof raw !== 'object') {
      return {
        need_split: [],
        missing_fields: [],
        client_data_issues: [],
        deliverable_issues: [],
        summary: '检查结果为空',
      }
    }
    const ensureArray = (val: any): any[] => {
      if (Array.isArray(val)) return val
      // 兼容 dict 包裹的数组
      if (val && typeof val === 'object') {
        for (const k of ['items', 'list', 'data']) {
          if (Array.isArray((val as any)[k])) return (val as any)[k]
        }
      }
      return []
    }
    const isValidSummary = (val: any): boolean => {
      if (typeof val !== 'string') return false
      const stripped = val.trim()
      if (!stripped) return false
      // JSON 字符串一律视为无效，避免弹窗显示原始 JSON
      if (stripped.startsWith('{') || stripped.startsWith('[')) return false
      return true
    }

    const needSplit = ensureArray(raw.need_split)
    const missingFields = ensureArray(raw.missing_fields)
    const clientDataIssues = ensureArray(raw.client_data_issues ?? raw.client_data_not_separated)
    const deliverableIssues = ensureArray(raw.deliverable_issues ?? raw.unclear_deliverables)

    let summary = isValidSummary(raw.summary) ? String(raw.summary) : ''
    if (!summary) {
      const passed = raw.passed
      const issueCount = raw.issue_count
      const total = needSplit.length + missingFields.length + clientDataIssues.length + deliverableIssues.length
      if (passed === true || issueCount === 0) {
        summary = '颗粒度检查通过，未发现明显问题。'
      } else if (passed === false || (typeof issueCount === 'number' && issueCount > 0)) {
        const cnt = typeof issueCount === 'number' ? issueCount : total
        summary = `颗粒度检查未通过，发现 ${cnt} 个待改进项。`
      } else if (total > 0) {
        summary = `颗粒度检查完成，发现 ${total} 个待改进项。`
      } else {
        summary = '颗粒度检查完成。'
      }
    }

    return {
      need_split: needSplit,
      missing_fields: missingFields,
      client_data_issues: clientDataIssues,
      deliverable_issues: deliverableIssues,
      summary,
    }
  }

  /** 颗粒度检查 */
  const handleGranularityCheck = async () => {
    if (!runId) return
    setChecking(true)
    try {
      const res = await checkGranularity(runId)
      if (res.success && res.data) {
        const normalized = normalizeGranularityResult(res.data)
        setGranularityResult(normalized)
        setGranularityModalOpen(true)
        message.success('颗粒度检查完成')
      } else {
        message.error(res.message || '颗粒度检查失败')
      }
    } catch (err: any) {
      message.error(err?.message || '颗粒度检查请求失败')
    } finally {
      setChecking(false)
    }
  }

  /** 生成待确认清单 */
  const handleGeneratePending = async () => {
    if (!runId) return
    setGeneratingPending(true)
    try {
      const res = await generatePending(runId)
      if (res.success && res.data) {
        setPendingItems(res.data.items || [])
        setPendingDrawerOpen(true)
        message.success('待确认清单生成完成')
      }
    } catch {
      // 忽略
    } finally {
      setGeneratingPending(false)
    }
  }

  /** 生成风险提示 */
  const handleGenerateRisk = async () => {
    if (!runId) return
    setGeneratingRisk(true)
    try {
      const res = await generateRisk(runId)
      if (res.success && res.data) {
        setRiskItems(res.data.risks || [])
        setRiskDrawerOpen(true)
        message.success('风险提示生成完成')
      }
    } catch {
      // 忽略
    } finally {
      setGeneratingRisk(false)
    }
  }

  /** 保存版本 */
  const handleSaveVersion = async () => {
    if (!runId) return
    try {
      const values = await versionForm.validateFields()
      setSavingVersion(true)
      const res = await saveVersion(runId, { description: values.description || '' })
      if (res.success) {
        message.success(res.message)
        setSaveVersionModalOpen(false)
        versionForm.resetFields()
      }
    } catch {
      // 忽略
    } finally {
      setSavingVersion(false)
    }
  }

  /** 进入下一步 */
  const handleNext = () => {
    completeStep(3)
    setCurrentStep(4)
    navigate('/version-history')
  }

  /** 报告校验 */
  const handleValidate = async () => {
    if (!runId) return
    setValidating(true)
    try {
      const res = await validateReport(runId)
      if (res.success) {
        setValidationResult(res)
        setValidationPassed(res.passed)
        setValidationModalOpen(true)
        if (res.passed) {
          message.success('校验通过，可以导出报告')
        } else {
          message.warning('校验未通过，请查看阻断性错误')
        }
      }
    } catch {
      // 忽略
    } finally {
      setValidating(false)
    }
  }

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
      {/* 顶部操作栏 */}
      <div className="ledger-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8 }}>
          <div>
            <h4>
              任务表复核
              {tasks.length > 0 && <Tag style={{ marginLeft: 8, color: 'var(--gold)', borderColor: 'var(--gold)', background: 'rgba(184,149,74,0.06)' }}>{tasks.length} 条</Tag>}
            </h4>
            <div className="ledger-subtitle">编辑和复核任务主表 · 报告校验 · 导出前确认</div>
          </div>
          <Space wrap>
          <Button icon={<ReloadOutlined />} onClick={loadTasks} loading={loading}>
            刷新
          </Button>
          <Button
            icon={<PlusOutlined />}
            onClick={() => setAddModalOpen(true)}
            type="primary"
            ghost
          >
            新增任务
          </Button>
          <Button
            icon={<CheckCircleOutlined />}
            onClick={handleGranularityCheck}
            loading={checking}
          >
            颗粒度检查
          </Button>
          <Button
            icon={<WarningOutlined />}
            onClick={handleGeneratePending}
            loading={generatingPending}
          >
            待确认清单
            {pendingItems.length > 0 && <Tag style={{ marginLeft: 4 }}>{pendingItems.length}</Tag>}
          </Button>
          <Button
            icon={<AlertOutlined />}
            onClick={handleGenerateRisk}
            loading={generatingRisk}
            danger
          >
            风险提示
            {riskItems.length > 0 && <Tag style={{ marginLeft: 4 }}>{riskItems.length}</Tag>}
          </Button>
          <Button
            icon={<SaveOutlined />}
            onClick={() => setSaveVersionModalOpen(true)}
            type="primary"
          >
            保存版本
          </Button>
          <Button
            icon={<SafetyCertificateOutlined />}
            onClick={handleValidate}
            loading={validating}
            type={validationPassed ? 'primary' : 'default'}
            ghost={validationPassed}
          >
            报告校验
            {validationPassed && <Tag color="success" style={{ marginLeft: 4 }}>已通过</Tag>}
          </Button>
          <Button
            icon={<BuildOutlined />}
            onClick={() => setDeliverableDrawerOpen(true)}
            type="primary"
            ghost
            style={{ color: 'var(--gold)', borderColor: 'var(--gold)' }}
          >
            AI交付成果
          </Button>
        </Space>
        </div>
      </div>

      {/* 颗粒度检查结果摘要 */}
      {granularityResult && (
        <Alert
          message={granularityResult.summary}
          type={granularityResult.need_split.length > 0 ? 'warning' : 'success'}
          showIcon
          style={{ marginBottom: 12 }}
          action={
            <Button size="small" onClick={() => setGranularityModalOpen(true)}>
              查看详情
            </Button>
          }
        />
      )}

      {/* 需求6：按服务模块批量复核面板 */}
      {tasks.length > 0 && (
        <ModuleBatchReviewPanel
          runId={runId || ''}
          tasks={tasks}
          onReviewed={loadTasks}
        />
      )}

      {/* 18字段可编辑表格 */}
      <TaskEditableTable
        tasks={tasks}
        onUpdateTask={handleUpdateTask}
        onDeleteTask={handleDeleteTask}
        onViewDetail={handleViewDetail}
        onMarkReview={handleMarkReview}
        loading={loading}
      />

      {/* 详情抽屉 */}
      <TaskDetailDrawer
        open={detailOpen}
        task={selectedTask}
        onClose={() => setDetailOpen(false)}
        onUpdateTask={handleUpdateTask}
      />

      {/* 新增任务弹窗 */}
      <AddTaskModal
        open={addModalOpen}
        onClose={() => setAddModalOpen(false)}
        onAdd={handleAddTask}
        defaultValues={tasks[0] ? {
          customer_name: tasks[0].customer_name,
          project_name: tasks[0].project_name,
        } : undefined}
      />

      {/* 颗粒度检查结果 Modal */}
      <Modal
        title="颗粒度检查结果"
        open={granularityModalOpen}
        onCancel={() => setGranularityModalOpen(false)}
        footer={[
          <Button key="close" onClick={() => setGranularityModalOpen(false)}>关闭</Button>,
        ]}
        width={800}
      >
        {granularityResult ? (
          <div>
            <Alert message={granularityResult.summary} type="info" showIcon style={{ marginBottom: 16 }} />

            {granularityResult.need_split.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <Title level={5}>需要继续拆分的任务 ({granularityResult.need_split.length})</Title>
                {granularityResult.need_split.map((item, idx) => (
                  <Card key={idx} size="small" style={{ marginBottom: 8 }} className="ledger-card">
                    <p><Text strong>任务名称：</Text>{item['原任务名称']}</p>
                    <p><Text strong>问题：</Text>{item['问题']}</p>
                    <p><Text strong>建议：</Text>{item['建议拆分为哪些任务']}</p>
                  </Card>
                ))}
              </div>
            )}

            {granularityResult.missing_fields.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <Title level={5}>缺少关键字段的任务 ({granularityResult.missing_fields.length})</Title>
                <List
                  size="small"
                  bordered
                  dataSource={granularityResult.missing_fields}
                  renderItem={(item, idx) => (
                    <List.Item key={idx}>
                      {Object.entries(item).map(([k, v]) => <span key={k}>{k}: {v} </span>)}
                    </List.Item>
                  )}
                />
              </div>
            )}

            {granularityResult.client_data_issues.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <Title level={5}>客户资料未独立成行 ({granularityResult.client_data_issues.length})</Title>
                <List
                  size="small"
                  bordered
                  dataSource={granularityResult.client_data_issues}
                  renderItem={(item, idx) => (
                    <List.Item key={idx}>
                      {Object.entries(item).map(([k, v]) => <span key={k}>{k}: {v} </span>)}
                    </List.Item>
                  )}
                />
              </div>
            )}

            {granularityResult.deliverable_issues.length > 0 && (
              <div>
                <Title level={5}>交付成果不明确 ({granularityResult.deliverable_issues.length})</Title>
                <List
                  size="small"
                  bordered
                  dataSource={granularityResult.deliverable_issues}
                  renderItem={(item, idx) => (
                    <List.Item key={idx}>
                      {Object.entries(item).map(([k, v]) => <span key={k}>{k}: {v} </span>)}
                    </List.Item>
                  )}
                />
              </div>
            )}

            {granularityResult.need_split.length === 0 &&
              granularityResult.missing_fields.length === 0 &&
              granularityResult.client_data_issues.length === 0 &&
              granularityResult.deliverable_issues.length === 0 && (
                <Empty description="所有任务均通过检查" />
              )}
          </div>
        ) : (
          <Empty description="暂无检查结果" />
        )}
      </Modal>

      {/* 待确认清单 Drawer */}
      <Drawer
        title="待确认清单"
        open={pendingDrawerOpen}
        onClose={() => setPendingDrawerOpen(false)}
        width={720}
      >
        {pendingItems.length > 0 ? (
          <List
            dataSource={pendingItems}
            renderItem={(item, index) => {
              const isEditing = editingPendingId === item.item_id
              return (
                <List.Item>
                  <Card
                    size="small"
                    style={{ width: '100%' }}
                    className="ledger-card"
                    title={
                      <Space>
                        <Tag style={{ color: 'var(--gold)', borderColor: 'var(--gold)', background: 'rgba(184,149,74,0.06)' }}>{index + 1}</Tag>
                        <Text strong>{isEditing ? (
                          <Input
                            size="small"
                            value={pendingEditValues.pending_item}
                            onChange={(e) => setPendingEditValues((prev: any) => ({ ...prev, pending_item: e.target.value }))}
                            style={{ width: 280 }}
                          />
                        ) : item.pending_item}</Text>
                      </Space>
                    }
                    extra={
                      isEditing ? (
                        <Space>
                          <Button size="small" type="primary" loading={savingPendingId === item.item_id} onClick={() => savePendingEdit(item.item_id)}>保存</Button>
                          <Button size="small" onClick={cancelPendingEdit}>取消</Button>
                        </Space>
                      ) : (
                        <Button size="small" type="link" onClick={() => startPendingEdit(item)}>编辑</Button>
                      )
                    }
                  >
                    {isEditing ? (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                        <Row gutter={8}>
                          <Col span={12}>
                            <Text type="secondary" style={{ fontSize: 12 }}>涉及任务</Text>
                            <Input.TextArea
                              size="small"
                              rows={2}
                              value={pendingEditValues.related_tasks}
                              onChange={(e) => setPendingEditValues((prev: any) => ({ ...prev, related_tasks: e.target.value }))}
                            />
                          </Col>
                          <Col span={12}>
                            <Text type="secondary" style={{ fontSize: 12 }}>建议向谁确认</Text>
                            <Input
                              size="small"
                              value={pendingEditValues.suggest_confirm_to}
                              onChange={(e) => setPendingEditValues((prev: any) => ({ ...prev, suggest_confirm_to: e.target.value }))}
                            />
                          </Col>
                        </Row>
                        <div>
                          <Text type="secondary" style={{ fontSize: 12 }}>原因</Text>
                          <Input.TextArea
                            size="small"
                            rows={2}
                            value={pendingEditValues.reason}
                            onChange={(e) => setPendingEditValues((prev: any) => ({ ...prev, reason: e.target.value }))}
                          />
                        </div>
                        <div>
                          <Text type="secondary" style={{ fontSize: 12 }}>不确认的影响</Text>
                          <Input.TextArea
                            size="small"
                            rows={2}
                            value={pendingEditValues.impact_if_not_confirmed}
                            onChange={(e) => setPendingEditValues((prev: any) => ({ ...prev, impact_if_not_confirmed: e.target.value }))}
                          />
                        </div>
                        <div>
                          <Text type="secondary" style={{ fontSize: 12 }}>手工确认/补充内容</Text>
                          <Input.TextArea
                            size="small"
                            rows={2}
                            value={pendingEditValues.confirmed_value}
                            onChange={(e) => setPendingEditValues((prev: any) => ({ ...prev, confirmed_value: e.target.value }))}
                            placeholder="填写确认结果或补充信息..."
                          />
                        </div>
                        <div>
                          <Text type="secondary" style={{ fontSize: 12 }}>状态</Text>
                          <Select
                            size="small"
                            value={pendingEditValues.status}
                            onChange={(val: string) => setPendingEditValues((prev: any) => ({ ...prev, status: val }))}
                            options={['待确认', '已确认', '需补充'].map((v) => ({ label: v, value: v }))}
                            style={{ width: 140 }}
                          />
                        </div>
                        <Space style={{ marginTop: 4 }}>
                          <Button
                            size="small"
                            onClick={() => setPendingEditValues((prev: any) => ({ ...prev, status: '待确认' }))}
                          >
                            标记待确认
                          </Button>
                          <Button
                            size="small"
                            type="primary"
                            ghost
                            loading={savingPendingId === item.item_id}
                            onClick={async () => {
                              // 合并当前编辑值并设置状态为已确认，立即调用后端保存
                              const nextValues = { ...pendingEditValues, status: '已确认' }
                              if (!runId) return
                              setSavingPendingId(item.item_id)
                              try {
                                const res = await updatePendingItem(runId, item.item_id, nextValues)
                                if (res.success) {
                                  const updatedItems = pendingItems.map((it) =>
                                    it.item_id === item.item_id ? { ...it, ...nextValues } : it
                                  )
                                  setPendingItems(updatedItems)
                                  setEditingPendingId(null)
                                  setPendingEditValues({})
                                  message.success('已确认并保存')
                                } else {
                                  message.error(res.message || '保存失败')
                                }
                              } catch (err: any) {
                                message.error(err?.message || '保存请求失败')
                              } finally {
                                setSavingPendingId(null)
                              }
                            }}
                          >
                            确认并保存
                          </Button>
                        </Space>
                      </div>
                    ) : (
                      <div>
                        <p><Text type="secondary">涉及任务：</Text>{item.related_tasks}</p>
                        <p><Text type="secondary">原因：</Text>{item.reason}</p>
                        <p><Text type="secondary">建议向谁确认：</Text>{item.suggest_confirm_to}</p>
                        <p><Text type="secondary">不确认的影响：</Text>{item.impact_if_not_confirmed}</p>
                        {item.confirmed_value && <p><Text type="secondary">确认内容：</Text><Text type="success">{item.confirmed_value}</Text></p>}
                        <Tag color={item.status === '待确认' ? 'warning' : item.status === '需补充' ? 'error' : 'success'}>{item.status}</Tag>
                      </div>
                    )}
                  </Card>
                </List.Item>
              )
            }}
          />
        ) : (
          <Empty description="暂无待确认清单，请先生成" />
        )}
      </Drawer>

      {/* AI交付成果 Drawer */}
      <Drawer
        title="AI交付成果"
        open={deliverableDrawerOpen}
        onClose={() => setDeliverableDrawerOpen(false)}
        width={720}
      >
        <DeliverablePanel
          runId={runId || ''}
          tasks={tasks}
          selectedTask={selectedTask}
        />
      </Drawer>

      {/* 风险提示 Drawer */}
      <Drawer
        title="风险提示清单"
        open={riskDrawerOpen}
        onClose={() => setRiskDrawerOpen(false)}
        width={640}
      >
        {riskItems.length > 0 ? (
          <List
            dataSource={riskItems}
            renderItem={(item, index) => (
              <List.Item>
                <Card size="small" style={{ width: '100%' }} className="ledger-card" title={
                  <Space>
                    <Tag style={{ color: 'var(--crimson)', borderColor: 'var(--crimson)', background: 'rgba(161,30,45,0.06)' }}>风险</Tag>
                    <Text strong>{item.risk_point}</Text>
                    <Tag color={RISK_SEVERITY_COLORS[item.severity] || 'default'}>
                      {item.severity}
                    </Tag>
                  </Space>
                }>
                  <p><Text type="secondary">风险来源：</Text>{item.risk_source}</p>
                  <p><Text type="secondary">影响范围：</Text>{item.impact_scope}</p>
                  <p><Text type="secondary">建议处理方式：</Text>{item.suggestion}</p>
                </Card>
              </List.Item>
            )}
          />
        ) : (
          <Empty description="暂无风险提示，请先生成" />
        )}
      </Drawer>

      {/* 保存版本 Modal */}
      <Modal
        title="保存版本"
        open={saveVersionModalOpen}
        onCancel={() => setSaveVersionModalOpen(false)}
        onOk={handleSaveVersion}
        confirmLoading={savingVersion}
        okText="保存"
        cancelText="取消"
      >
        <Form form={versionForm} layout="vertical">
          <Form.Item
            name="description"
            label="版本描述"
            rules={[{ required: true, message: '请输入版本描述' }]}
          >
            <Input.TextArea
              rows={3}
              placeholder="请输入版本描述，如：首轮拆分完成、客户确认后修订版等"
            />
          </Form.Item>
          <Alert
            message={`当前任务总数：${tasks.length} 条`}
            type="info"
            showIcon
          />
        </Form>
      </Modal>

      {/* 校验结果 Modal */}
      <Modal
        title="报告校验结果"
        open={validationModalOpen}
        onCancel={() => setValidationModalOpen(false)}
        footer={[
          <Button key="close" onClick={() => setValidationModalOpen(false)}>关闭</Button>,
        ]}
        width={700}
      >
        {validationResult ? (
          <div>
            {validationResult.passed ? (
              <Alert
                message="校验通过"
                description="校验通过，可以导出报告。"
                type="success"
                showIcon
                style={{ marginBottom: 16 }}
              />
            ) : (
              <Alert
                message="校验未通过"
                description="存在阻断性错误，请修正后再导出报告。"
                type="error"
                showIcon
                style={{ marginBottom: 16 }}
              />
            )}

            {/* 阻断性错误 */}
            {validationResult.errors && validationResult.errors.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <Title level={5}>阻断性错误 ({validationResult.errors.length})</Title>
                <List
                  size="small"
                  bordered
                  dataSource={validationResult.errors}
                  renderItem={(item, idx) => (
                    <List.Item key={idx}>
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <Space>
                          <Tag style={{ color: 'var(--crimson)', borderColor: 'var(--crimson)', background: 'rgba(161,30,45,0.06)' }}>未通过</Tag>
                          <Text strong>{item.rule}</Text>
                        </Space>
                        <Text>{item.message}</Text>
                        {item.detail && <Text type="secondary" style={{ fontSize: 12 }}>{item.detail}</Text>}
                      </Space>
                    </List.Item>
                  )}
                />
              </div>
            )}

            {/* 警告 */}
            {validationResult.warnings && validationResult.warnings.length > 0 && (
              <div style={{ marginBottom: 16 }}>
                <Title level={5}>警告 ({validationResult.warnings.length})</Title>
                <Alert
                  message="以下为警告事项，不影响导出但建议修正"
                  type="warning"
                  showIcon
                  style={{ marginBottom: 8 }}
                />
                <List
                  size="small"
                  bordered
                  dataSource={validationResult.warnings}
                  renderItem={(item, idx) => (
                    <List.Item key={idx}>
                      <Space direction="vertical" style={{ width: '100%' }}>
                        <Space>
                          <Tag style={{ color: 'var(--amber)', borderColor: 'var(--amber)', background: 'rgba(196,140,30,0.06)' }}>警告</Tag>
                          <Text strong>{item.rule}</Text>
                        </Space>
                        <Text>{item.message}</Text>
                        {item.detail && <Text type="secondary" style={{ fontSize: 12 }}>{item.detail}</Text>}
                      </Space>
                    </List.Item>
                  )}
                />
              </div>
            )}

            {/* 全部检查项 */}
            {validationResult.checks && validationResult.checks.length > 0 && (
              <div>
                <Title level={5}>全部检查项 ({validationResult.checks.length})</Title>
                <List
                  size="small"
                  bordered
                  dataSource={validationResult.checks}
                  renderItem={(item, idx) => (
                    <List.Item key={idx}>
                      <Space>
                        <Tag color={item.passed ? 'success' : 'error'}>
                          {item.passed ? '通过' : '未通过'}
                        </Tag>
                        <Text strong>{item.rule}</Text>
                        <Text type="secondary">{item.message}</Text>
                      </Space>
                    </List.Item>
                  )}
                />
              </div>
            )}

            {validationResult.message && (
              <Alert
                message={validationResult.message}
                type={validationResult.passed ? 'info' : 'warning'}
                showIcon
                style={{ marginTop: 16 }}
              />
            )}
          </div>
        ) : (
          <Empty description="暂无校验结果" />
        )}
      </Modal>

      {/* 下一步 */}
      <div style={{ textAlign: 'right', marginTop: 16 }}>
        <Space>
          {!validationPassed && (
            <Text type="warning" style={{ fontSize: 12 }}>
              提示: 导出前请先通过报告校验
            </Text>
          )}
          <Button
            icon={<HistoryOutlined />}
            onClick={() => navigate('/version-history')}
          >
            查看版本记录
          </Button>
          <Button
            type="primary"
            onClick={handleNext}
            size="large"
            className="confirm-button"
            style={{ background: 'var(--ink)', borderColor: 'var(--ink)' }}
          >
            进入下一步
          </Button>
        </Space>
      </div>
    </div>
  )
}

export default TaskReviewPage
