/**
 * 页面6: 导出
 * - 导出选项卡片（CSV / Markdown / 完整导出）
 * - 导出预览
 * - 已导出文件列表
 * - CSV导出按钮、Markdown导出按钮
 */
import React, { useState, useEffect } from 'react'
import {
  Card,
  Button,
  Typography,
  Space,
  Row,
  Col,
  Tag,
  Empty,
  Spin,
  Alert,
  Tabs,
  Input,
} from 'antd'
import { message } from '../../utils/messageBridge'
import {
  FileExcelOutlined,
  FileMarkdownOutlined,
  FileZipOutlined,
  DownloadOutlined,
  ReloadOutlined,
} from '@ant-design/icons'
import { exportCSV, exportMarkdown, exportFull, downloadFile, triggerBlobDownload } from '../../services/export'
import { downloadCSV, tasksToCSV } from '../../utils/csv'
import { generateTaskReport, downloadMarkdown } from '../../utils/markdown'
import { useProjectStore } from '../../stores/projectStore'
import { useTaskStore } from '../../stores/taskStore'
import { useStepStore } from '../../stores/stepStore'
import type { Task } from '../../types'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input

const ExportPage: React.FC = () => {
  const { runId } = useProjectStore()
  const { tasks, pendingItems, riskItems } = useTaskStore()
  const { completeStep } = useStepStore()
  const [loading, setLoading] = useState(false)
  const [previewContent, setPreviewContent] = useState('')
  const [exportedFiles, setExportedFiles] = useState<Array<{ name: string; type: string; time: string; taskCount: number }>>([])
  const [activeTab, setActiveTab] = useState('csv')

  /** 从后端导出 CSV */
  const handleExportCSV = async () => {
    if (!runId) {
      message.warning('请先创建运行实例')
      return
    }
    setLoading(true)
    try {
      const blob = await exportCSV(runId)
      triggerBlobDownload(blob, `task_list_${runId}.csv`)
      setExportedFiles((prev) => [
        ...prev,
        { name: `task_list_${runId}.csv`, type: 'CSV', time: new Date().toLocaleString(), taskCount: tasks.length },
      ])
      message.success('CSV 导出成功')
    } catch {
      // 如果后端失败，使用前端生成
      downloadCSV(tasks, `task_list_${runId}`)
      setExportedFiles((prev) => [
        ...prev,
        { name: `task_list_${runId}.csv`, type: 'CSV(前端)', time: new Date().toLocaleString(), taskCount: tasks.length },
      ])
      message.success('CSV 导出成功（前端生成）')
    } finally {
      setLoading(false)
    }
  }

  /** 前端直接生成 CSV */
  const handleExportCSVFrontend = () => {
    if (tasks.length === 0) {
      message.warning('暂无任务数据')
      return
    }
    downloadCSV(tasks, `task_list_${runId || 'local'}`)
    setExportedFiles((prev) => [
      ...prev,
      { name: `task_list_${runId || 'local'}.csv`, type: 'CSV(前端)', time: new Date().toLocaleString(), taskCount: tasks.length },
    ])
    message.success('CSV 导出成功')
  }

  /** 从后端导出 Markdown */
  const handleExportMarkdown = async () => {
    if (!runId) {
      message.warning('请先创建运行实例')
      return
    }
    setLoading(true)
    try {
      const res = await exportMarkdown(runId)
      if (res.success && res.content) {
        setPreviewContent(res.content)
        downloadMarkdown(res.content, `task_report_${runId}`)
        setExportedFiles((prev) => [
          ...prev,
          { name: `task_report_${runId}.md`, type: 'Markdown', time: new Date().toLocaleString(), taskCount: tasks.length },
        ])
        message.success('Markdown 导出成功')
      }
    } catch {
      // 如果后端失败，使用前端生成
      const content = generateTaskReport(tasks, runId || 'local', pendingItems, riskItems)
      setPreviewContent(content)
      downloadMarkdown(content, `task_report_${runId || 'local'}`)
      setExportedFiles((prev) => [
        ...prev,
        { name: `task_report_${runId || 'local'}.md`, type: 'Markdown(前端)', time: new Date().toLocaleString(), taskCount: tasks.length },
      ])
      message.success('Markdown 导出成功（前端生成）')
    } finally {
      setLoading(false)
    }
  }

  /** 前端直接生成 Markdown */
  const handleExportMarkdownFrontend = () => {
    if (tasks.length === 0) {
      message.warning('暂无任务数据')
      return
    }
    const content = generateTaskReport(tasks, runId || 'local', pendingItems, riskItems)
    setPreviewContent(content)
    downloadMarkdown(content, `task_report_${runId || 'local'}`)
    setExportedFiles((prev) => [
      ...prev,
      { name: `task_report_${runId || 'local'}.md`, type: 'Markdown(前端)', time: new Date().toLocaleString(), taskCount: tasks.length },
    ])
    message.success('Markdown 导出成功')
  }

  /** 完整导出 */
  const handleExportFull = async () => {
    if (!runId) {
      message.warning('请先创建运行实例')
      return
    }
    setLoading(true)
    try {
      const res = await exportFull(runId)
      if (res.success) {
        message.success(`完整导出成功：${res.task_count} 条任务，${res.pending_count} 项待确认，${res.risk_count} 项风险`)
        // 下载文件
        try {
          const blob = await downloadFile(runId, res.filename)
          triggerBlobDownload(blob, res.filename)
        } catch {
          // 忽略下载失败
        }
        setExportedFiles((prev) => [
          ...prev,
          { name: res.filename, type: '完整导出', time: new Date().toLocaleString(), taskCount: res.task_count },
        ])
      }
    } catch {
      // 前端生成完整报告
      const content = generateTaskReport(tasks, runId, pendingItems, riskItems)
      setPreviewContent(content)
      downloadMarkdown(content, `full_report_${runId}`)
      setExportedFiles((prev) => [
        ...prev,
        { name: `full_report_${runId}.md`, type: '完整导出(前端)', time: new Date().toLocaleString(), taskCount: tasks.length },
      ])
      message.success('完整导出成功（前端生成）')
    } finally {
      setLoading(false)
    }
  }

  /** 生成预览 */
  const handlePreview = () => {
    if (activeTab === 'csv') {
      setPreviewContent(tasksToCSV(tasks))
    } else if (activeTab === 'markdown') {
      const content = generateTaskReport(tasks, runId || 'local', pendingItems, riskItems)
      setPreviewContent(content)
    }
  }

  useEffect(() => {
    completeStep(5)
  }, [])

  if (!runId) {
    return (
      <div className="page-container">
        <Alert
          message="请先上传文件"
          description="请先在资料上传页面上传文件或加载 Mock 数据"
          type="warning"
          showIcon
        />
      </div>
    )
  }

  const tabItems = [
    {
      key: 'csv',
      label: 'CSV 导出',
      children: (
        <div>
          <Paragraph>
            将任务主表导出为 CSV 格式（UTF-8 BOM 编码，兼容 Excel 直接打开）。包含全部 18 字段。
          </Paragraph>
          <Space>
            <Button
              type="primary"
              icon={<FileExcelOutlined />}
              onClick={handleExportCSV}
              loading={loading}
            >
              从后端导出 CSV
            </Button>
            <Button
              icon={<DownloadOutlined />}
              onClick={handleExportCSVFrontend}
            >
              前端直接生成 CSV
            </Button>
          </Space>
        </div>
      ),
    },
    {
      key: 'markdown',
      label: 'Markdown 导出',
      children: (
        <div>
          <Paragraph>
            将任务主表和报告导出为 Markdown 格式，包含统计摘要、待确认清单和风险提示。
          </Paragraph>
          <Space>
            <Button
              type="primary"
              icon={<FileMarkdownOutlined />}
              onClick={handleExportMarkdown}
              loading={loading}
            >
              从后端导出 Markdown
            </Button>
            <Button
              icon={<DownloadOutlined />}
              onClick={handleExportMarkdownFrontend}
            >
              前端直接生成 Markdown
            </Button>
          </Space>
        </div>
      ),
    },
    {
      key: 'full',
      label: '完整导出',
      children: (
        <div>
          <Paragraph>
            导出完整数据包，包含任务主表、待确认清单、风险提示清单和颗粒度检查结果。
          </Paragraph>
          <Button
            type="primary"
            icon={<FileZipOutlined />}
            onClick={handleExportFull}
            loading={loading}
            size="large"
          >
            导出完整数据包
          </Button>
        </div>
      ),
    },
  ]

  return (
    <div className="page-container">
      <Title level={4}>导出</Title>
      <Text type="secondary">将任务主表导出为 CSV / Markdown / 完整数据包</Text>

      <Row gutter={16} style={{ marginTop: 24 }}>
        <Col span={8}>
          <Card
            hoverable
            onClick={() => setActiveTab('csv')}
            style={{ borderColor: activeTab === 'csv' ? '#1677ff' : undefined }}
          >
            <div style={{ textAlign: 'center' }}>
              <FileExcelOutlined style={{ fontSize: 40, color: '#52c41a' }} />
              <Title level={5} style={{ marginTop: 12 }}>CSV 导出</Title>
              <Text type="secondary">18字段完整导出，兼容 Excel</Text>
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card
            hoverable
            onClick={() => setActiveTab('markdown')}
            style={{ borderColor: activeTab === 'markdown' ? '#1677ff' : undefined }}
          >
            <div style={{ textAlign: 'center' }}>
              <FileMarkdownOutlined style={{ fontSize: 40, color: '#1677ff' }} />
              <Title level={5} style={{ marginTop: 12 }}>Markdown 导出</Title>
              <Text type="secondary">含统计摘要、待确认和风险清单</Text>
            </div>
          </Card>
        </Col>
        <Col span={8}>
          <Card
            hoverable
            onClick={() => setActiveTab('full')}
            style={{ borderColor: activeTab === 'full' ? '#1677ff' : undefined }}
          >
            <div style={{ textAlign: 'center' }}>
              <FileZipOutlined style={{ fontSize: 40, color: '#fa8c16' }} />
              <Title level={5} style={{ marginTop: 12 }}>完整导出</Title>
              <Text type="secondary">任务+待确认+风险+颗粒度</Text>
            </div>
          </Card>
        </Col>
      </Row>

      <Card style={{ marginTop: 24 }}>
        <Tabs
          activeKey={activeTab}
          onChange={setActiveTab}
          items={tabItems}
        />
      </Card>

      {/* 导出预览 */}
      <Card
        title="导出预览"
        style={{ marginTop: 24 }}
        extra={
          <Button
            icon={<ReloadOutlined />}
            onClick={handlePreview}
            size="small"
          >
            生成预览
          </Button>
        }
      >
        {previewContent ? (
          <TextArea
            value={previewContent}
            readOnly
            autoSize={{ minRows: 8, maxRows: 20 }}
            style={{ fontFamily: 'monospace', fontSize: 12 }}
          />
        ) : (
          <Empty description="点击「生成预览」查看导出内容" />
        )}
      </Card>

      {/* 已导出文件列表 */}
      <Card title="已导出文件" style={{ marginTop: 24 }}>
        {exportedFiles.length > 0 ? (
          <div>
            {exportedFiles.map((file, index) => (
              <div
                key={index}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  padding: '8px 12px',
                  marginBottom: 8,
                  background: '#f6ffed',
                  borderRadius: 6,
                  border: '1px solid #b7eb8f',
                }}
              >
                <DownloadOutlined style={{ color: '#52c41a', marginRight: 8 }} />
                <div style={{ flex: 1 }}>
                  <Text strong>{file.name}</Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    类型: {file.type} | 时间: {file.time} | 任务数: {file.taskCount}
                  </Text>
                </div>
                <Tag color="success">已导出</Tag>
              </div>
            ))}
          </div>
        ) : (
          <Empty description="暂无已导出文件" />
        )}
      </Card>

      {/* 统计摘要 */}
      <Row gutter={16} style={{ marginTop: 24 }}>
        <Col span={6}>
          <Card>
            <div style={{ textAlign: 'center' }}>
              <Title level={3}>{tasks.length}</Title>
              <Text type="secondary">任务总数</Text>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <div style={{ textAlign: 'center' }}>
              <Title level={3} style={{ color: '#52c41a' }}>
                {tasks.filter(t => t.review_status === '已确认').length}
              </Title>
              <Text type="secondary">已确认</Text>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <div style={{ textAlign: 'center' }}>
              <Title level={3} style={{ color: '#faad14' }}>
                {pendingItems.length}
              </Title>
              <Text type="secondary">待确认事项</Text>
            </div>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <div style={{ textAlign: 'center' }}>
              <Title level={3} style={{ color: '#ff4d4f' }}>
                {riskItems.length}
              </Title>
              <Text type="secondary">风险提示</Text>
            </div>
          </Card>
        </Col>
      </Row>
    </div>
  )
}

export default ExportPage
