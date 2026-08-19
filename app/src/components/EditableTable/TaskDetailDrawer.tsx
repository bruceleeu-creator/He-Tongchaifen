/**
 * 任务详情抽屉
 * - 查看模式：展示 18 字段
 * - 编辑模式：Form/Input/Select 控件，支持编辑全部 18 字段
 * - 保存调用父级 onUpdateTask，取消回退到查看模式
 */
import React, { useEffect, useMemo } from 'react'
import { Drawer, Tag, Descriptions, Divider, Button, Space, Form, Input, Select, DatePicker, message } from 'antd'
import { EditOutlined, SaveOutlined, CloseOutlined } from '@ant-design/icons'
import dayjs from 'dayjs'
import type { Task, TaskUpdate } from '../../types'
import { STATUS_TAG_COLORS, REVIEW_TAG_COLORS, TASK_FIELDS, SERVICE_MODULES, TASK_TYPES, CURRENT_STATUS, DELAY_RESPONSIBILITY, REVIEW_STATUS } from '../../utils/constants'

interface TaskDetailDrawerProps {
  open: boolean
  task: Task | null
  onClose: () => void
  /** 保存回调，由父级调用后端 */
  onUpdateTask?: (taskId: string, updates: TaskUpdate) => Promise<void> | void
}

const TaskDetailDrawer: React.FC<TaskDetailDrawerProps> = ({ open, task, onClose, onUpdateTask }) => {
  const [editMode, setEditMode] = React.useState(false)
  const [form] = Form.useForm()
  const [saving, setSaving] = React.useState(false)

  // 进入抽屉或切换任务时重置编辑状态
  useEffect(() => {
    if (open) {
      setEditMode(false)
      form.resetFields()
    }
  }, [open, task?.task_id])

  // 编辑模式开启时同步表单初值
  useEffect(() => {
    if (editMode && task) {
      const values: Record<string, any> = { ...task }
      // 日期字段转为 dayjs
      if (task.plan_start_date) values.plan_start_date = dayjs(task.plan_start_date)
      if (task.plan_end_date) values.plan_end_date = dayjs(task.plan_end_date)
      form.setFieldsValue(values)
    }
  }, [editMode, task, form])

  // 18 字段中需要 Select 的字段映射
  const selectFieldOptions: Record<string, string[]> = {
    service_module: SERVICE_MODULES,
    task_type: TASK_TYPES,
    current_status: CURRENT_STATUS,
    delay_responsibility: DELAY_RESPONSIBILITY,
    review_status: REVIEW_STATUS,
  }

  // 长文本字段使用 TextArea
  const textareaFields = useMemo(() => new Set([
    'client_requirements',
    'milestone_goal',
    'next_action',
    'deliverables',
    'ai_deliverable_desc',
    'ai_extraction_basis',
  ]), [])

  // 日期字段
  const dateFields = useMemo(() => new Set(['plan_start_date', 'plan_end_date']), [])

  /** 保存编辑 */
  const handleSave = async () => {
    if (!task || !onUpdateTask) {
      setEditMode(false)
      return
    }
    try {
      const values = await form.validateFields()
      // 日期字段转回字符串
      const updates: TaskUpdate = { ...values }
      if (values.plan_start_date) {
        updates.plan_start_date = dayjs(values.plan_start_date).format('YYYY-MM-DD')
      } else {
        updates.plan_start_date = ''
      }
      if (values.plan_end_date) {
        updates.plan_end_date = dayjs(values.plan_end_date).format('YYYY-MM-DD')
      } else {
        updates.plan_end_date = ''
      }
      setSaving(true)
      await onUpdateTask(task.task_id, updates)
      message.success('已保存')
      setEditMode(false)
    } catch (err: any) {
      if (err?.errorFields?.length) {
        message.warning('请检查表单必填项')
      } else {
        message.error(err?.message || '保存失败')
      }
    } finally {
      setSaving(false)
    }
  }

  /** 取消编辑 */
  const handleCancelEdit = () => {
    setEditMode(false)
    form.resetFields()
  }

  const titleExtra = onUpdateTask && !editMode ? (
    <Button size="small" icon={<EditOutlined />} onClick={() => setEditMode(true)}>编辑</Button>
  ) : null

  if (!task) {
    return (
      <Drawer title="任务详情" open={open} onClose={onClose} width={640}>
        <div>暂无数据</div>
      </Drawer>
    )
  }

  return (
    <Drawer
      title={
        <Space>
          <span>任务详情</span>
          {editMode && <Tag color="processing">编辑中</Tag>}
        </Space>
      }
      open={open}
      onClose={onClose}
      width={760}
      extra={
        <Space>
          {editMode ? (
            <>
              <Button size="small" icon={<CloseOutlined />} onClick={handleCancelEdit} disabled={saving}>取消</Button>
              <Button size="small" type="primary" icon={<SaveOutlined />} loading={saving} onClick={handleSave}>保存</Button>
            </>
          ) : (
            titleExtra
          )}
        </Space>
      }
    >
      {editMode ? (
        <Form form={form} layout="vertical">
          {TASK_FIELDS.map((field) => (
            <Form.Item
              key={field.key}
              name={field.key}
              label={field.label}
            >
              {selectFieldOptions[field.key] ? (
                <Select
                  showSearch
                  allowClear
                  options={selectFieldOptions[field.key].map((v) => ({ label: v, value: v }))}
                  placeholder={`选择或输入${field.label}`}
                />
              ) : dateFields.has(field.key) ? (
                <DatePicker style={{ width: '100%' }} />
              ) : textareaFields.has(field.key) ? (
                <Input.TextArea rows={2} placeholder={`输入${field.label}`} />
              ) : (
                <Input placeholder={`输入${field.label}`} />
              )}
            </Form.Item>
          ))}
        </Form>
      ) : (
        <>
          {/* 基本信息 */}
          <div className="task-detail-section">
            <h4>基本信息</h4>
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="客户名称" span={2}>
                {task.customer_name}
              </Descriptions.Item>
              <Descriptions.Item label="项目名称" span={2}>
                {task.project_name}
              </Descriptions.Item>
              <Descriptions.Item label="任务名称" span={2}>
                {task.task_name}
              </Descriptions.Item>
              <Descriptions.Item label="服务模块">
                <Tag color="blue">{task.service_module}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="任务类型">
                <Tag color="cyan">{task.task_type}</Tag>
              </Descriptions.Item>
              <Descriptions.Item label="计划开始时间">
                {task.plan_start_date}
              </Descriptions.Item>
              <Descriptions.Item label="计划完成时间">
                {task.plan_end_date}
              </Descriptions.Item>
              <Descriptions.Item label="我方负责人">
                {task.our_owner}
              </Descriptions.Item>
              <Descriptions.Item label="客户责任人">
                {task.client_contact}
              </Descriptions.Item>
              <Descriptions.Item label="当前状态">
                <Tag color={STATUS_TAG_COLORS[task.current_status] || 'default'}>
                  {task.current_status}
                </Tag>
              </Descriptions.Item>
              <Descriptions.Item label="延期责任归属">
                {task.delay_responsibility}
              </Descriptions.Item>
              <Descriptions.Item label="复核状态" span={2}>
                <Tag color={REVIEW_TAG_COLORS[task.review_status] || 'default'}>
                  {task.review_status}
                </Tag>
              </Descriptions.Item>
            </Descriptions>
          </div>

          <Divider />

          {/* 客户配合事项 */}
          <div className="task-detail-section">
            <h4>客户需提供的资料或配合事项</h4>
            <p>{task.client_requirements || '暂无'}</p>
          </div>

          {/* 节点目标 */}
          <div className="task-detail-section">
            <h4>节点目标/达到效果</h4>
            <p>{task.milestone_goal || '暂无'}</p>
          </div>

          {/* 下一步动作 */}
          <div className="task-detail-section">
            <h4>下一步动作及承诺完成时间</h4>
            <p>{task.next_action || '暂无'}</p>
          </div>

          {/* 交付成果 */}
          <div className="task-detail-section">
            <h4>交付成果或完成凭证</h4>
            <p>{task.deliverables || '暂无'}</p>
          </div>

          <Divider />

          {/* AI 相关 */}
          <div className="task-detail-section">
            <h4>AI定制交付成果说明</h4>
            <p style={{ background: '#f6ffed', padding: 12, borderRadius: 6, borderLeft: '3px solid #52c41a' }}>
              {task.ai_deliverable_desc || '暂无'}
            </p>
          </div>

          <div className="task-detail-section">
            <h4>AI提取依据</h4>
            <p style={{ background: '#e6f4ff', padding: 12, borderRadius: 6, borderLeft: '3px solid #1677ff' }}>
              {task.ai_extraction_basis || '暂无'}
            </p>
          </div>
        </>
      )}
    </Drawer>
  )
}

export default TaskDetailDrawer
