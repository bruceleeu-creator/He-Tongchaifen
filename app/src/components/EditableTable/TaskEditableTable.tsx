/**
 * 18字段可编辑表格组件
 * - 使用 Ant Design Table
 * - 固定列：序号、任务名称、服务模块、任务类型、计划完成时间
 * - 可展开行显示全部18字段
 * - 行内编辑：双击单元格进入编辑模式
 * - 下拉选择：服务模块、任务类型、当前状态、延期责任归属、人工复核状态
 * - 日期选择：计划开始/完成时间
 * - 操作列：编辑、删除、查看依据、标记状态
 */
import React, { useState, useMemo } from 'react'
import {
  Table,
  Input,
  Select,
  DatePicker,
  Tag,
  Space,
  Button,
  Popconfirm,
  Tooltip,
  Typography,
} from 'antd'
import { message } from '../../utils/messageBridge'
import {
  EditOutlined,
  DeleteOutlined,
  FileSearchOutlined,
  CheckOutlined,
  CloseOutlined,
} from '@ant-design/icons'
import type { ColumnsType } from 'antd/es/table'
import dayjs from 'dayjs'
import type { Task } from '../../types'
import {
  TASK_FIELDS,
  SERVICE_MODULES,
  TASK_TYPES,
  CURRENT_STATUS,
  DELAY_RESPONSIBILITY,
  REVIEW_STATUS,
  STATUS_TAG_COLORS,
  REVIEW_TAG_COLORS,
} from '../../utils/constants'

const { Text } = Typography

interface EditableCellProps {
  field: (typeof TASK_FIELDS)[0]
  value: any
  editing: boolean
  onChange: (value: any) => void
}

/** 可编辑单元格 */
const EditableCell: React.FC<EditableCellProps> = ({ field, value, editing, onChange }) => {
  const formatValue = (val: any): string => {
    if (!val) return ''
    return String(val)
  }

  if (!editing) {
    // 非编辑模式 - 显示值
    if (field.type === 'select') {
      return (
        <div className="editable-cell-text">
          <Tag
            color={
              field.key === 'current_status'
                ? STATUS_TAG_COLORS[value] || 'default'
                : field.key === 'review_status'
                  ? REVIEW_TAG_COLORS[value] || 'default'
                  : 'blue'
            }
            style={{ margin: 0 }}
          >
            {value || '-'}
          </Tag>
        </div>
      )
    }
    if (field.type === 'date') {
      return <div className="editable-cell-text">{value || '-'}</div>
    }
    const displayValue = formatValue(value)
    return (
      <Tooltip title={displayValue} mouseEnterDelay={0.5}>
        <div className="editable-cell-text">
          {displayValue.length > 30 ? displayValue.substring(0, 30) + '...' : displayValue || '-'}
        </div>
      </Tooltip>
    )
  }

  // 编辑模式
  if (field.type === 'select') {
    let options = field.options || []
    return (
      <Select
        size="small"
        value={value}
        onChange={onChange}
        style={{ width: '100%' }}
        options={options.map((v) => ({ label: v, value: v }))}
        showSearch
      />
    )
  }
  if (field.type === 'date') {
    return (
      <DatePicker
        size="small"
        value={value ? dayjs(value) : null}
        onChange={(_, dateStr) => onChange(dateStr as string)}
        style={{ width: '100%' }}
        format="YYYY-MM-DD"
      />
    )
  }
  // 长文本字段使用 TextArea，其他用 Input
  const isLongText = ['client_requirements', 'milestone_goal', 'next_action', 'deliverables', 'ai_deliverable_desc', 'ai_extraction_basis'].includes(field.key)
  if (isLongText) {
    return (
      <Input.TextArea
        size="small"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        autoSize={{ minRows: 1, maxRows: 4 }}
      />
    )
  }
  return (
    <Input
      size="small"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  )
}

interface TaskEditableTableProps {
  tasks: Task[]
  onUpdateTask: (taskId: string, updates: Partial<Task>) => void
  onDeleteTask: (taskId: string) => void
  onViewDetail?: (task: Task) => void
  onMarkReview?: (taskId: string, status: string) => void
  loading?: boolean
}

const TaskEditableTable: React.FC<TaskEditableTableProps> = ({
  tasks,
  onUpdateTask,
  onDeleteTask,
  onViewDetail,
  onMarkReview,
  loading,
}) => {
  // 编辑状态: { [task_id]: { [field_key]: boolean } }
  const [editingCells, setEditingCells] = useState<Record<string, Set<string>>>({})
  // 编辑值缓存
  const [editValues, setEditValues] = useState<Record<string, any>>({})
  // 分页状态
  const [currentPage, setCurrentPage] = useState(1)
  const [pageSize, setPageSize] = useState(20)

  /** 获取单元格编辑缓存 key */
  const cellKey = (taskId: string, fieldKey: string) => `${taskId}__${fieldKey}`

  /** 进入编辑 */
  const startEdit = (taskId: string, fieldKey: string, currentValue: any) => {
    setEditValues((prev) => ({ ...prev, [cellKey(taskId, fieldKey)]: currentValue }))
    setEditingCells((prev) => {
      const taskSet = new Set(prev[taskId] || [])
      taskSet.add(fieldKey)
      return { ...prev, [taskId]: taskSet }
    })
  }

  /** 取消编辑 */
  const cancelEdit = (taskId: string, fieldKey: string) => {
    setEditingCells((prev) => {
      const taskSet = new Set(prev[taskId] || [])
      taskSet.delete(fieldKey)
      return { ...prev, [taskId]: taskSet }
    })
    setEditValues((prev) => {
      const next = { ...prev }
      delete next[cellKey(taskId, fieldKey)]
      return next
    })
  }

  /** 保存编辑 */
  const saveEdit = (taskId: string, fieldKey: string) => {
    const value = editValues[cellKey(taskId, fieldKey)]
    onUpdateTask(taskId, { [fieldKey]: value } as Partial<Task>)
    cancelEdit(taskId, fieldKey)
    message.success('已更新')
  }

  /** 双击单元格 */
  const handleDoubleClick = (taskId: string, fieldKey: string, currentValue: any) => {
    startEdit(taskId, fieldKey, currentValue)
  }

  /** 生成可见列（表格主视图显示的列） */
  const visibleFieldKeys = [
    'task_name',
    'service_module',
    'task_type',
    'plan_end_date',
    'current_status',
    'review_status',
  ]

  /** 构建表格列 */
  const columns: ColumnsType<Task> = useMemo(() => {
    const cols: ColumnsType<Task> = [
      {
        title: '序号',
        key: '_index',
        width: 60,
        fixed: 'left',
        render: (_: any, __: Task, index: number) => (currentPage - 1) * pageSize + index + 1,
      },
    ]

    // 添加可见字段列
    for (const field of TASK_FIELDS) {
      if (!visibleFieldKeys.includes(field.key)) continue
      cols.push({
        title: field.label,
        dataIndex: field.key,
        key: field.key,
        width: field.width || 120,
        fixed: field.key === 'task_name' ? 'left' : undefined,
        onCell: (record: Task) => ({
          onDoubleClick: () => handleDoubleClick(record.task_id, field.key, (record as any)[field.key]),
        }),
        render: (_: any, record: Task) => {
          const isEditing = editingCells[record.task_id]?.has(field.key)
          const value = isEditing ? editValues[cellKey(record.task_id, field.key)] : (record as any)[field.key]
          return (
            <EditableCell
              field={field}
              value={value}
              editing={!!isEditing}
              onChange={(val) =>
                setEditValues((prev) => ({
                  ...prev,
                  [cellKey(record.task_id, field.key)]: val,
                }))
              }
            />
          )
        },
      })

      // 如果当前列正在编辑，添加保存/取消按钮
      const lastIndex = cols.length - 1
      const originalRender = cols[lastIndex].render
      cols[lastIndex].render = (value: any, record: Task, index: number) => {
        const isEditing = editingCells[record.task_id]?.has(field.key)
        const content = originalRender ? originalRender(value, record, index) : value
        if (isEditing) {
          return (
            <Space size="small">
              <div style={{ flex: 1, minWidth: 60 }}>{content}</div>
              <Button
                type="link"
                size="small"
                icon={<CheckOutlined />}
                onClick={() => saveEdit(record.task_id, field.key)}
              />
              <Button
                type="link"
                size="small"
                danger
                icon={<CloseOutlined />}
                onClick={() => cancelEdit(record.task_id, field.key)}
              />
            </Space>
          )
        }
        return content
      }
    }

    // 操作列
    cols.push({
      title: '操作',
      key: '_action',
      width: 200,
      fixed: 'right',
      render: (_: any, record: Task) => (
        <Space size="small">
          {onViewDetail && (
            <Button
              type="link"
              size="small"
              icon={<EditOutlined />}
              onClick={() => onViewDetail(record)}
            >
              详情
            </Button>
          )}
          {onMarkReview && (
            <Select
              size="small"
              value={record.review_status}
              style={{ width: 90 }}
              onChange={(val) => onMarkReview(record.task_id, val)}
              options={REVIEW_STATUS.map((v) => ({ label: v, value: v }))}
            />
          )}
          <Popconfirm
            title="确定删除此任务吗？"
            onConfirm={() => onDeleteTask(record.task_id)}
            okText="确定"
            cancelText="取消"
          >
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    })

    return cols
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editingCells, editValues, tasks, currentPage, pageSize])

  /** 展开行内容 - 显示全部18字段 */
  const expandedRowRender = (record: Task) => {
    const otherFields = TASK_FIELDS.filter((f) => !visibleFieldKeys.includes(f.key))
    return (
      <div style={{ padding: '8px 24px' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(2, 1fr)',
            gap: '8px 24px',
          }}
        >
          {otherFields.map((field) => {
            const value = (record as any)[field.key]
            return (
              <div key={field.key} style={{ display: 'flex', alignItems: 'flex-start' }}>
                <Text
                  type="secondary"
                  style={{
                    minWidth: 140,
                    fontSize: 12,
                    paddingTop: 2,
                    flexShrink: 0,
                  }}
                >
                  {field.label}：
                </Text>
                <Text style={{ fontSize: 12, flex: 1, wordBreak: 'break-all' }}>
                  {field.type === 'select' ? (
                    <Tag
                      color={
                        field.key === 'current_status'
                          ? STATUS_TAG_COLORS[value] || 'default'
                          : field.key === 'review_status'
                            ? REVIEW_TAG_COLORS[value] || 'default'
                            : 'blue'
                      }
                      style={{ margin: 0 }}
                    >
                      {value || '-'}
                    </Tag>
                  ) : (
                    value || '-'
                  )}
                </Text>
              </div>
            )
          })}
        </div>
        <div style={{ marginTop: 12, paddingTop: 8, borderTop: '1px dashed #f0f0f0' }}>
          <Space size="small">
            <Button
              size="small"
              type="link"
              icon={<FileSearchOutlined />}
              onClick={() => onViewDetail?.(record)}
            >
              查看依据
            </Button>
          </Space>
        </div>
      </div>
    )
  }

  return (
    <Table<Task>
      columns={columns}
      dataSource={tasks}
      rowKey="task_id"
      loading={loading}
      // 修复滚动问题（需求5）：
      // - x: 1800，保证列宽总和溢出容器，触发稳定可见的左右滚动条
      // - y: 使用固定像素而非 calc，避免 calc 在某些布局下被压缩导致滚动条消失
      //   同时为顶部工具栏/分页预留 280px 空间
      scroll={{ x: 1800, y: 520 }}
      expandable={{
        expandedRowRender,
        rowExpandable: () => true,
      }}
      size="small"
      pagination={{
        current: currentPage,
        pageSize: pageSize,
        showSizeChanger: true,
        showTotal: (total) => `共 ${total} 条任务`,
        pageSizeOptions: ['10', '20', '50', '100'],
        onChange: (page, size) => {
          setCurrentPage(page)
          if (size) setPageSize(size)
        },
      }}
      bordered
    />
  )
}

export default TaskEditableTable
