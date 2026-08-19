/**
 * 页面1: 项目资料上传
 * - 文件拖拽上传区域
 * - 文件类型选择器
 * - 已上传文件列表
 * - 文本预览
 * - 进入下一步按钮
 */
import React, { useState, useEffect } from 'react'
import { Card, Button, Select, List, Tag, Typography, Space, Alert, Empty, Spin, Divider, Popconfirm } from 'antd'
import { InboxOutlined, FileTextOutlined, RightOutlined, ReloadOutlined, ThunderboltOutlined, DeleteOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { message } from '../../utils/messageBridge'
import { uploadFile, createRun, getRun, listRuns, deleteUploadedFile } from '../../services/upload'
import { runPipeline } from '../../services/pipeline'
import { useProjectStore } from '../../stores/projectStore'
import { useStepStore } from '../../stores/stepStore'

const { Text, Paragraph, Title } = Typography

const UploadPage: React.FC = () => {
  const navigate = useNavigate()
  const { runId, setRunId, setRunInfo, runInfo } = useProjectStore()
  const { setCurrentStep, completeStep } = useStepStore()
  const [fileType, setFileType] = useState('contract')
  const [uploading, setUploading] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<Array<{ name: string; type: string; status: string; parseInfo?: any; parsedAt?: string }>>([])
  const [previewText, setPreviewText] = useState('')
  const [loadingRuns, setLoadingRuns] = useState(false)
  const [existingRuns, setExistingRuns] = useState<any[]>([])
  const [pipelineRunning, setPipelineRunning] = useState(false)
  const [typeWarning, setTypeWarning] = useState<string>('')
  // 多文件批量上传进度
  const [batchProgress, setBatchProgress] = useState<{ current: number; total: number; filename: string } | null>(null)
  const currentFileTypeLabel = fileType === 'plan' ? '年度服务计划' : fileType === 'meeting_minutes' ? '启动会纪要' : '合同'

  /** 是否已上传合同文件 */
  const hasContract = uploadedFiles.some(f => f.type === 'contract')

  /** 加载已有运行实例 */
  const loadRuns = async () => {
    setLoadingRuns(true)
    try {
      const res = await listRuns()
      setExistingRuns(res.runs || [])
    } catch {
      // 忽略
    } finally {
      setLoadingRuns(false)
    }
  }

  /** 从后端运行实例元数据恢复已上传文件清单 */
  const syncUploadedFilesFromMeta = (meta: any) => {
    if (!meta) return
    const records = meta.file_records || []
    if (records.length > 0) {
      setUploadedFiles(records.map((r: any) => ({
        name: r.filename || '未知文件',
        type: r.file_type || r.requested_file_type || 'unknown',
        status: '已上传',
        parseInfo: { parsed_at: r.parsed_at },
        parsedAt: r.parsed_at,
      })))
    } else {
      setUploadedFiles([])
    }
  }

  useEffect(() => {
    loadRuns()
  }, [])

  /** runId 变化时（如选择已有实例），从后端恢复已上传文件清单 */
  useEffect(() => {
    if (!runId) {
      setUploadedFiles([])
      return
    }
    getRun(runId).then((res: any) => {
      if (res.success && res.run) {
        setRunInfo(res.run)
        syncUploadedFilesFromMeta(res.run)
      }
    }).catch(() => {
      // 忽略
    })
  }, [runId])

  /** 处理文件上传 */
  const handleUpload = async (file: File) => {
    setUploading(true)
    try {
      const res = await uploadFile(file, fileType, runId)
      if (res.success) {
        setRunId(res.run_id)
        if (res.warning) {
          // 后端返回了类型不一致警告，显示在页面上并弹出提示
          setTypeWarning(res.warning)
          message.warning(res.warning)
        } else if (res.file_type_corrected) {
          const correctedLabel = res.file_type === 'plan' ? '年度服务计划' : res.file_type === 'contract' ? '合同' : res.file_type
          setTypeWarning(`${file.name} 已按内容识别为「${correctedLabel}」`)
          message.warning(`${file.name} 已按内容识别为「${correctedLabel}」`)
        } else {
          setTypeWarning('')
          message.success(`${file.name} 上传解析成功`)
        }
        setUploadedFiles((prev) => [
        ...prev,
        {
          name: file.name,
          type: res.file_type || fileType,
          status: '解析成功',
          parseInfo: res.parse_result,
          parsedAt: new Date().toISOString(),
        },
      ])
      // 获取运行实例详情并从后端同步文件清单（确保类型校正后的准确状态）
      try {
        const runRes = await getRun(res.run_id)
        setRunInfo(runRes.run)
        syncUploadedFilesFromMeta(runRes.run)
      } catch {
        // 忽略
      }
    }
  } catch (err: any) {
    // 错误已由 axios 拦截器处理
  } finally {
    setUploading(false)
  }
}

/** 多文件批量上传：逐个上传到同一 run_id，显示进度 X/Y */
const handleUploadMultiple = async (files: FileList) => {
  if (!files || files.length === 0) return
  const fileArray = Array.from(files)
  setUploading(true)
  setBatchProgress({ current: 0, total: fileArray.length, filename: fileArray[0].name })
  let successCount = 0
  let failCount = 0
  let firstRunId = runId
  for (let i = 0; i < fileArray.length; i++) {
    const f = fileArray[i]
    setBatchProgress({ current: i + 1, total: fileArray.length, filename: f.name })
    try {
      const res = await uploadFile(f, fileType, firstRunId)
      if (res.success) {
        if (!firstRunId) {
          firstRunId = res.run_id
          setRunId(res.run_id)
        }
        successCount++
        if (res.warning) {
          setTypeWarning(res.warning)
        } else if (res.file_type_corrected) {
          const correctedLabel = res.file_type === 'plan' ? '年度服务计划' : res.file_type === 'contract' ? '合同' : res.file_type
          setTypeWarning(`${f.name} 已按内容识别为「${correctedLabel}」`)
        }
      } else {
        failCount++
        message.error(`${f.name} 上传失败: ${res.message || '未知错误'}`)
      }
    } catch (err: any) {
      failCount++
      // 错误已由 axios 拦截器处理
    }
  }
  // 全部上传完成后，从后端同步文件清单
  if (firstRunId) {
    try {
      const runRes = await getRun(firstRunId)
      setRunInfo(runRes.run)
      syncUploadedFilesFromMeta(runRes.run)
    } catch {
      // 忽略
    }
  }
  setBatchProgress(null)
  setUploading(false)
  if (successCount > 0 && failCount === 0) {
    message.success(`已成功上传 ${successCount} 个文件`)
  } else if (successCount > 0 && failCount > 0) {
    message.warning(`上传完成: 成功 ${successCount} 个，失败 ${failCount} 个`)
  } else if (failCount > 0) {
    message.error(`全部 ${failCount} 个文件上传失败`)
  }
}

  /** 使用 Mock 数据创建运行实例 */
  const handleUseMock = async () => {
    setUploading(true)
    try {
      const res = await createRun('Mock演示项目', true)
      if (res.success) {
        setRunId(res.run_id)
        message.success('Mock 数据已加载')
        setUploadedFiles((prev) => [
          ...prev,
          {
            name: 'Mock演示数据',
            type: 'mock',
            status: '已加载',
            parseInfo: { mode: 'mock' },
          },
        ])
        const runRes = await getRun(res.run_id)
        setRunInfo(runRes.run)
      }
    } catch {
      // 忽略
    } finally {
      setUploading(false)
    }
  }

  /** 删除已上传文件（带确认弹窗） */
  const handleDeleteFile = async (item: { name: string; type: string; parsedAt?: string }) => {
    if (!runId) {
      message.warning('当前没有运行实例，无法删除')
      return
    }
    setUploading(true)
    try {
      const res = await deleteUploadedFile(runId, item.name, item.type, item.parsedAt)
      if (res.success) {
        message.success(res.message || `已删除文件 ${item.name}`)
        // 从本地列表移除（后端同步会再次校正，这里先乐观更新）
        setUploadedFiles((prev) => prev.filter((f) => !(f.name === item.name && f.type === item.type && (f.parsedAt || '') === (item.parsedAt || ''))))
        // 刷新运行实例详情，同步最新 file_records / file_types / *_parsed.json 状态
        try {
          const runRes = await getRun(runId)
          setRunInfo(runRes.run)
          syncUploadedFilesFromMeta(runRes.run)
        } catch {
          // 忽略
        }
      } else {
        message.error(res.message || '删除失败')
      }
    } catch {
      // 错误已由 axios 拦截器处理
    } finally {
      setUploading(false)
    }
  }

  /** 选择已有运行实例 */
  const handleSelectRun = async (selectedRunId: string) => {
    setRunId(selectedRunId)
    // runId 变化会触发 useEffect 自动加载文件清单
    try {
      const runRes = await getRun(selectedRunId)
      setRunInfo(runRes.run)
      syncUploadedFilesFromMeta(runRes.run)
      message.success(`已切换到运行实例: ${selectedRunId}`)
    } catch {
      // 忽略
    }
  }

  /** 进入下一步：自动合并 AI 全流程分析，分析完成后跳转到合同识别 */
  const handleNext = async () => {
    if (!runId) {
      message.warning('请先上传文件或加载 Mock 数据')
      return
    }
    if (!hasContract) {
      message.error('未上传合同文件，无法进入下一步。请将文件类型选择为「合同」并上传合同文件')
      return
    }
    setPipelineRunning(true)
    try {
      const res = await runPipeline(runId)
      if (res.success) {
        if (res.status === 'completed') {
          message.success('AI 全流程分析已完成，正在跳转到合同识别')
          completeStep(0)
          setCurrentStep(1)
          navigate('/recognition')
        } else if (res.status === 'paused') {
          message.info('AI 全流程已暂停，可在侧边栏恢复后再进入下一步')
        } else {
          // 已启动但未完成：仍跳转到合同识别，让用户在识别页查看进度
          message.success('AI 全流程分析已启动，正在跳转到合同识别')
          completeStep(0)
          setCurrentStep(1)
          navigate('/recognition')
        }
      } else {
        message.error(res.message || 'AI 全流程分析失败，请检查后再进入下一步')
      }
    } catch {
      // 错误已由 axios 拦截器处理
    } finally {
      setPipelineRunning(false)
    }
  }

  /** 启动 AI 全流程分析 */
  const handleStartPipeline = async () => {
    if (!runId) {
      message.warning('请先上传合同文件')
      return
    }
    if (!hasContract) {
      message.error('未上传合同文件，无法运行全流程分析。请将文件类型选择为「合同」并上传合同文件')
      return
    }
    setPipelineRunning(true)
    try {
      const res = await runPipeline(runId)
      if (res.success) {
        if (res.status === 'completed') {
          // 完成后跳转到合同识别，让用户逐步确认识别/澄清/任务复核
          // 不直接标记澄清追问和任务复核为已完成
          message.success('全流程分析已完成，请先进入合同识别查看识别结果，再逐步确认后续模块。')
          completeStep(0)
          setCurrentStep(1)
          navigate('/recognition')
        } else if (res.status === 'paused') {
          message.info('全流程已暂停，可在侧边栏恢复')
        } else {
          message.success('全流程分析已启动')
        }
      } else {
        message.error(res.message || '全流程分析失败')
      }
    } catch {
      // 错误已由 axios 拦截器处理
    } finally {
      setPipelineRunning(false)
    }
  }

  return (
    <div className="page-container">
      <div className="ledger-header">
        <h4>项目资料上传</h4>
        <div className="ledger-subtitle">上传合同或服务计划，系统将深度解析并创建工作实例</div>
      </div>

      <div style={{ marginTop: 24 }}>
        <Card variant="borderless" className="ledger-card">
          <Space direction="vertical" style={{ width: '100%' }} size="large">
            {/* 快速操作 */}
            <div>
              <Space>
                <Button
                  icon={<ReloadOutlined />}
                  onClick={handleUseMock}
                  loading={uploading}
                  ghost
                  style={{ borderColor: 'var(--slate)', color: 'var(--slate)' }}
                >
                  使用 Mock 数据快速开始
                </Button>
                <Button onClick={loadRuns} loading={loadingRuns}>
                  刷新运行实例列表
                </Button>
              </Space>
            </div>

            {/* 已有运行实例 */}
            {existingRuns.length > 0 && (
              <div>
                <Text strong style={{ marginRight: 12 }}>已有运行实例：</Text>
                <Select
                  placeholder="选择已有运行实例"
                  style={{ width: 400 }}
                  onChange={handleSelectRun}
                  options={existingRuns.map((r: any) => ({
                    label: `${r.run_id.substring(0, 16)}... (${r.status})`,
                    value: r.run_id,
                  }))}
                />
              </div>
            )}

            {/* 上传区域 */}
            <div>
              <Text strong style={{ marginRight: 12 }}>文件类型：</Text>
              <Select
                value={fileType}
                onChange={setFileType}
                style={{ width: 200 }}
                options={[
                  { label: '合同', value: 'contract' },
                  { label: '年度服务计划', value: 'plan' },
                  { label: '启动会纪要', value: 'meeting_minutes' },
                ]}
              />
            </div>

            <div
              className="upload-zone"
              onClick={() => {
                if (uploading) return
                const input = document.createElement('input')
                input.type = 'file'
                input.accept = '.docx,.doc'
                input.multiple = true
                input.onchange = (e: any) => {
                  if (e.target.files && e.target.files.length > 0) {
                    if (e.target.files.length === 1) {
                      handleUpload(e.target.files[0])
                    } else {
                      handleUploadMultiple(e.target.files)
                    }
                  }
                }
                input.click()
              }}
            >
              {uploading ? (
                batchProgress ? (
                  <Spin tip={`正在上传第 ${batchProgress.current}/${batchProgress.total} 个文件：${batchProgress.filename}`}>
                    <div style={{ minHeight: 60 }} />
                  </Spin>
                ) : (
                  <Spin tip={`正在解析${currentFileTypeLabel}...`}>
                    <div style={{ minHeight: 60 }} />
                  </Spin>
                )
              ) : (
                <>
                  <InboxOutlined className="upload-icon" />
                  <div className="upload-hint">点击或拖拽{currentFileTypeLabel}文件到此区域（支持一次选择多个文件）</div>
                  <div className="upload-sub">支持 .docx / .doc 格式 · 可多选 · 系统将自动解析并校正资料类型</div>
                </>
              )}
            </div>

            {/* 已上传文件列表 */}
            {uploadedFiles.length > 0 && (
              <div>
                <Text strong>已上传文件：</Text>
                <List
                  style={{ marginTop: 8 }}
                  size="small"
                  bordered
                  dataSource={uploadedFiles}
                  renderItem={(item, index) => (
                    <List.Item key={index}>
                      <List.Item.Meta
                        avatar={<FileTextOutlined style={{ fontSize: 20, color: 'var(--sage)' }} />}
                        title={
                          <Space>
                            <Text strong>{item.name}</Text>
                            <Tag style={{ color: 'var(--gold)', borderColor: 'var(--gold)', background: 'rgba(184,149,74,0.06)' }}>{item.type}</Tag>
                          </Space>
                        }
                        description={
                          item.parseInfo
                            ? `段落数: ${item.parseInfo.paragraph_count || '-'}, 表格数: ${item.parseInfo.table_count || '-'}, 字符数: ${item.parseInfo.char_count || '-'}`
                            : item.status
                        }
                      />
                      <Space>
                        <Tag color="success">{item.status}</Tag>
                        <Popconfirm
                          title="确认删除该文件？"
                          description="删除后将同步清理该文件的解析记录与下游旧结果，不可恢复。"
                          okText="删除"
                          cancelText="取消"
                          okButtonProps={{ danger: true }}
                          onConfirm={() => handleDeleteFile(item)}
                          disabled={uploading}
                        >
                          <Button
                            type="text"
                            danger
                            size="small"
                            icon={<DeleteOutlined />}
                            disabled={uploading}
                            aria-label={`删除文件 ${item.name}`}
                          >
                            删除
                          </Button>
                        </Popconfirm>
                      </Space>
                    </List.Item>
                  )}
                />
              </div>
            )}

            {/* 文件类型不一致警告 */}
            {typeWarning && (
              <Alert
                message="文件类型提示"
                description={typeWarning}
                type="warning"
                showIcon
                closable
                onClose={() => setTypeWarning('')}
              />
            )}

            {/* 缺少合同文件提示 */}
            {uploadedFiles.length > 0 && !hasContract && (
              <Alert
                message="尚未上传合同文件"
                description="全流程分析需要合同文件作为基础。请将文件类型选择为「合同」并上传合同文件后，再运行 AI 全流程分析。"
                type="error"
                showIcon
              />
            )}

            {/* 当前运行实例信息 */}
            {runId && (
              <Alert
                message={<span>当前运行实例: <span style={{ fontFamily: 'var(--font-mono)' }}>{runId}</span></span>}
                description={`状态: ${runInfo?.status || 'unknown'} | 模式: ${runInfo?.mode || 'mock'}`}
                type={runInfo?.file_types?.length ? 'success' : 'info'}
                showIcon
              />
            )}

            {/* 下一步 */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 8 }}>
              <Button
                size="large"
                icon={<ThunderboltOutlined />}
                onClick={handleStartPipeline}
                loading={pipelineRunning}
                disabled={!runId}
                style={{
                  borderColor: 'var(--gold)',
                  color: 'var(--gold)',
                  fontWeight: 500,
                }}
              >
                AI 全流程分析
              </Button>
              <Button
                type="primary"
                icon={<RightOutlined />}
                onClick={handleNext}
                disabled={!runId || pipelineRunning}
                loading={pipelineRunning}
                size="large"
                className="confirm-button"
                style={{ background: 'var(--ink)', borderColor: 'var(--ink)' }}
              >
                {pipelineRunning ? 'AI 全流程分析中…' : '进入下一步'}
              </Button>
            </div>
          </Space>
        </Card>
      </div>
    </div>
  )
}

export default UploadPage
