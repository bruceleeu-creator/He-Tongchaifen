/**
 * 新增任务弹窗
 */
import React, { useEffect } from 'react'
import { Modal, Form, Input, Select, DatePicker } from 'antd'
import { message } from '../../utils/messageBridge'
import dayjs from 'dayjs'
import type { Task } from '../../types'
import {
  SERVICE_MODULES,
  TASK_TYPES,
  CURRENT_STATUS,
  DELAY_RESPONSIBILITY,
  REVIEW_STATUS,
} from '../../utils/constants'

const { TextArea } = Input

interface AddTaskModalProps {
  open: boolean
  onClose: () => void
  onAdd: (task: Omit<Task, 'task_id' | 'created_at' | 'updated_at'>) => void
  defaultValues?: Partial<Task>
}

const AddTaskModal: React.FC<AddTaskModalProps> = ({ open, onClose, onAdd, defaultValues }) => {
  const [form] = Form.useForm()

  useEffect(() => {
    if (open) {
      form.setFieldsValue({
        customer_name: defaultValues?.customer_name || '',
        project_name: defaultValues?.project_name || '',
        task_name: '',
        service_module: '',
        task_type: '',
        plan_start_date: null,
        plan_end_date: null,
        our_owner: '',
        client_contact: '',
        client_requirements: '',
        current_status: '未开始',
        delay_responsibility: '无延期',
        milestone_goal: '',
        next_action: '',
        deliverables: '',
        ai_deliverable_desc: '',
        ai_extraction_basis: '',
        review_status: '待复核',
      })
    }
  }, [open, defaultValues, form])

  const handleOk = async () => {
    try {
      const values = await form.validateFields()
      const task: Omit<Task, 'task_id' | 'created_at' | 'updated_at'> = {
        customer_name: values.customer_name || '',
        project_name: values.project_name || '',
        task_name: values.task_name || '',
        service_module: values.service_module || '',
        task_type: values.task_type || '',
        plan_start_date: values.plan_start_date
          ? dayjs(values.plan_start_date).format('YYYY-MM-DD')
          : '',
        plan_end_date: values.plan_end_date
          ? dayjs(values.plan_end_date).format('YYYY-MM-DD')
          : '',
        our_owner: values.our_owner || '',
        client_contact: values.client_contact || '',
        client_requirements: values.client_requirements || '',
        current_status: values.current_status || '未开始',
        delay_responsibility: values.delay_responsibility || '无延期',
        milestone_goal: values.milestone_goal || '',
        next_action: values.next_action || '',
        deliverables: values.deliverables || '',
        ai_deliverable_desc: values.ai_deliverable_desc || '',
        ai_extraction_basis: values.ai_extraction_basis || '',
        review_status: values.review_status || '待复核',
      }
      onAdd(task)
      form.resetFields()
      message.success('任务已添加')
    } catch (error) {
      // 校验失败
    }
  }

  const handleCancel = () => {
    form.resetFields()
    onClose()
  }

  return (
    <Modal
      title="新增任务"
      open={open}
      onOk={handleOk}
      onCancel={handleCancel}
      width={800}
      okText="确定添加"
      cancelText="取消"
      destroyOnClose
    >
      <Form form={form} layout="vertical" size="small">
        <Form.Item name="task_name" label="任务名称" rules={[{ required: true, message: '请输入任务名称' }]}>
          <Input placeholder="请输入任务名称" />
        </Form.Item>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
          <Form.Item name="customer_name" label="客户名称">
            <Input placeholder="请输入客户名称" />
          </Form.Item>
          <Form.Item name="project_name" label="项目名称">
            <Input placeholder="请输入项目名称" />
          </Form.Item>
          <Form.Item name="service_module" label="服务模块">
            <Select
              showSearch
              placeholder="请选择服务模块"
              options={SERVICE_MODULES.map((v) => ({ label: v, value: v }))}
            />
          </Form.Item>
          <Form.Item name="task_type" label="任务类型">
            <Select
              showSearch
              placeholder="请选择任务类型"
              options={TASK_TYPES.map((v) => ({ label: v, value: v }))}
            />
          </Form.Item>
          <Form.Item name="plan_start_date" label="计划开始时间">
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="plan_end_date" label="计划完成时间">
            <DatePicker style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="our_owner" label="我方负责人">
            <Input placeholder="请输入我方负责人" />
          </Form.Item>
          <Form.Item name="client_contact" label="客户责任人">
            <Input placeholder="请输入客户责任人" />
          </Form.Item>
          <Form.Item name="current_status" label="当前状态">
            <Select
              options={CURRENT_STATUS.map((v) => ({ label: v, value: v }))}
            />
          </Form.Item>
          <Form.Item name="delay_responsibility" label="延期责任归属">
            <Select
              options={DELAY_RESPONSIBILITY.map((v) => ({ label: v, value: v }))}
            />
          </Form.Item>
        </div>

        <Form.Item name="client_requirements" label="客户需提供的资料或配合事项">
          <TextArea rows={2} placeholder="请输入客户需提供的资料或配合事项" />
        </Form.Item>
        <Form.Item name="milestone_goal" label="节点目标/达到效果">
          <TextArea rows={2} placeholder="请输入节点目标/达到效果" />
        </Form.Item>
        <Form.Item name="next_action" label="下一步动作及承诺完成时间">
          <TextArea rows={2} placeholder="请输入下一步动作及承诺完成时间" />
        </Form.Item>
        <Form.Item name="deliverables" label="交付成果或完成凭证">
          <TextArea rows={2} placeholder="请输入交付成果或完成凭证" />
        </Form.Item>

        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0 16px' }}>
          <Form.Item name="review_status" label="人工复核状态">
            <Select options={REVIEW_STATUS.map((v) => ({ label: v, value: v }))} />
          </Form.Item>
        </div>

        <Form.Item name="ai_deliverable_desc" label="AI定制交付成果说明">
          <TextArea rows={2} placeholder="AI定制交付成果说明（可手动填写）" />
        </Form.Item>
        <Form.Item name="ai_extraction_basis" label="AI提取依据">
          <TextArea rows={2} placeholder="AI提取依据（可手动填写）" />
        </Form.Item>
      </Form>
    </Modal>
  )
}

export default AddTaskModal
