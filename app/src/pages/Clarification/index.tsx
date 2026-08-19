/**
 * 页面3: 澄清追问（动态追问交互区）
 * - 顶部显示运行模式 Tag
 * - 动态生成的追问问题列表
 * - 每个问题根据 question_type 显示不同输入（text/choice）
 * - 显示追问原因、不确认的影响
 * - 提交所有回答
 * - 提交后显示"执行二次拆分"按钮
 * - 二次拆分完成后跳转到任务复核页
 */
import React, { useState, useEffect } from 'react'
import {
  Card,
  Button,
  Input,
  Select,
  Tag,
  Typography,
  Space,
  Alert,
  Spin,
  Empty,
  Tooltip,
  Divider,
} from 'antd'
import { message } from '../../utils/messageBridge'
import { FormOutlined, RightOutlined, ReloadOutlined, CheckCircleOutlined, ThunderboltOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import { generateForm, getForm, submitAnswers, secondSplit } from '../../services/clarification'
import { useProjectStore } from '../../stores/projectStore'
import { useTaskStore } from '../../stores/taskStore'
import { useStepStore } from '../../stores/stepStore'
import ModeIndicator from '../../components/ModeIndicator'
import type { ClarificationForm as ClarificationFormType, ClarificationItem } from '../../types'

const { Title, Text, Paragraph } = Typography
const { TextArea } = Input

const ClarificationPage: React.FC = () => {
  const navigate = useNavigate()
  const { runId } = useProjectStore()
  const { setTasks } = useTaskStore()
  const { setCurrentStep, completeStep } = useStepStore()

  const [loading, setLoading] = useState(false)
  const [generating, setGenerating] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [splitting, setSplitting] = useState(false)
  const [clarificationData, setClarificationData] = useState<ClarificationFormType | null>(null)
  const [mode, setMode] = useState<string>('rule')
  const [modeLabel, setModeLabel] = useState<string>('')
  const [dataSource, setDataSource] = useState<string>('')
  // 收集所有问题的回答
  const [answers, setAnswers] = useState<Record<string, string>>({})
  // 提交成功后显示二次拆分按钮
  const [submitted, setSubmitted] = useState(false)

  /** 加载已有澄清表单 */
  const loadForm = async () => {
    if (!runId) return
    setLoading(true)
    try {
      const res = await getForm(runId)
      if (res.success && res.data) {
        setClarificationData(res.data)
        setMode(res.mode || res.data?.generated_by || 'rule')
        setModeLabel(res.mode_label || '')
        setDataSource(res.data_source || '')
        // 初始化回答值，使用 suggested_answer 作为默认值
        const initialAnswers: Record<string, string> = {}
        res.data.items?.forEach((item: ClarificationItem) => {
          initialAnswers[item.item_id] = item.suggested_answer || item.confirmed_value || ''
        })
        setAnswers(initialAnswers)
      }
    } catch {
      // 表单可能不存在
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadForm()
  }, [runId])

  /** 生成动态追问表单 */
  const handleGenerate = async () => {
    if (!runId) {
      message.warning('请先在资料上传页面创建运行实例')
      return
    }
    setGenerating(true)
    try {
      const res = await generateForm(runId)
      if (res.success) {
        const data = res.data
        setClarificationData(data)
        setMode(res.mode || data?.generated_by || 'rule')
        setModeLabel(res.mode_label || '')
        setDataSource(res.data_source || '')
        // 初始化回答值
        const initialAnswers: Record<string, string> = {}
        data.items?.forEach((item: ClarificationItem) => {
          initialAnswers[item.item_id] = item.suggested_answer || ''
        })
        setAnswers(initialAnswers)
        setSubmitted(false)
        message.success('动态追问表单生成完成')
      }
    } catch {
      // 忽略
    } finally {
      setGenerating(false)
    }
  }

  /** 更新某个问题的回答 */
  const handleAnswerChange = (itemId: string, value: string) => {
    setAnswers((prev) => ({ ...prev, [itemId]: value }))
  }

  /** 提交所有回答 */
  const handleSubmitAnswers = async () => {
    if (!runId || !clarificationData) return
    setSubmitting(true)
    try {
      // 将表单数据转换为提交格式
      const submitData = clarificationData.items.map((item) => ({
        item_id: item.item_id,
        pending_item: item.pending_item,
        confirmed_value: answers[item.item_id] || '',
      }))

      const res = await submitAnswers(runId, submitData)
      if (res.success) {
        setSubmitted(true)
        message.success('所有回答已提交，请执行二次拆分')
      }
    } catch {
      // 忽略
    } finally {
      setSubmitting(false)
    }
  }

  /** 执行二次拆分 */
  const handleSecondSplit = async () => {
    if (!runId) return
    setSplitting(true)
    try {
      const res = await secondSplit(runId)
      if (res.success) {
        // 如果返回了任务列表，更新 store
        if (res.data?.tasks) {
          setTasks(res.data.tasks)
        }
        message.success('二次拆分完成，正在跳转到任务复核页')
        completeStep(2)
        setCurrentStep(3)
        navigate('/task-review')
      }
    } catch {
      // 忽略
    } finally {
      setSplitting(false)
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
      <div className="ledger-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h4>澄清追问</h4>
            <div className="ledger-subtitle">基于合同识别结果动态生成追问 · 确认后执行二次拆分</div>
            <div style={{ marginTop: 8 }}>
              <ModeIndicator mode={mode} modeLabel={modeLabel} dataSource={dataSource} />
            </div>
          </div>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={loadForm} loading={loading}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<FormOutlined />}
              onClick={handleGenerate}
              loading={generating}
              className="confirm-button"
              style={{ background: 'var(--ink)', borderColor: 'var(--ink)' }}
            >
              生成追问
            </Button>
          </Space>
        </div>
      </div>

      <Spin spinning={loading || generating}>
        {clarificationData && clarificationData.items && clarificationData.items.length > 0 ? (
          <div>
            {/* 统计信息 */}
            {clarificationData.total != null && (
              <Alert
                message={`共 ${clarificationData.total} 个待澄清问题`}
                description={clarificationData.generated_by ? `生成方式: ${clarificationData.generated_by}` : '请逐一确认以下追问问题'}
                type="info"
                showIcon
                style={{ marginBottom: 16 }}
              />
            )}

            {/* 问题列表 */}
            {clarificationData.items.map((item, index) => {
              const questionType = item.question_type || 'text'
              const currentAnswer = answers[item.item_id] || ''
              return (
                <div key={item.item_id} className="question-card">
                  <div className="question-header">
                    <div className="question-number">{index + 1}</div>
                    <div className="question-title">{item.pending_item}</div>
                    {questionType === 'choice' && <Tag style={{ borderColor: 'var(--gold)', color: 'var(--gold)', background: 'rgba(184,149,74,0.06)' }}>选择</Tag>}
                    {questionType === 'text' && <Tag style={{ borderColor: 'var(--slate)', color: 'var(--slate)' }}>填空</Tag>}
                  </div>
                  <div className="question-body">
                    {/* 追问原因和不确认的影响 */}
                    <div className="question-meta">
                      {item.reason && (
                        <div className="question-meta-item">
                          <span className="meta-label">追问原因:</span>
                          <Tooltip title={item.reason}>{item.reason}</Tooltip>
                        </div>
                      )}
                      {item.impact_if_not_confirmed && (
                        <div className="question-meta-item" style={{ color: 'var(--crimson)' }}>
                          <span className="meta-label">不确认影响:</span>
                          <Tooltip title={item.impact_if_not_confirmed}>{item.impact_if_not_confirmed}</Tooltip>
                        </div>
                      )}
                    </div>

                    {/* 涉及任务和建议确认人 */}
                    {(item.related_tasks || item.suggest_confirm_to) && (
                      <div className="question-meta" style={{ marginBottom: 12 }}>
                        {item.related_tasks && (
                          <div className="question-meta-item">
                            <span className="meta-label">涉及任务:</span>{item.related_tasks}
                          </div>
                        )}
                        {item.suggest_confirm_to && (
                          <div className="question-meta-item">
                            <span className="meta-label">建议确认人:</span>{item.suggest_confirm_to}
                          </div>
                        )}
                      </div>
                    )}

                    {/* 输入区域 - 根据 question_type 显示不同输入 */}
                    <div style={{ marginTop: 8 }}>
                      {questionType === 'choice' ? (
                        <Select
                          style={{ width: '100%' }}
                          placeholder="请选择"
                          value={currentAnswer || undefined}
                          onChange={(value) => handleAnswerChange(item.item_id, value)}
                          options={item.options?.map((opt) => ({ label: opt, value: opt }))}
                        />
                      ) : (
                        <TextArea
                          rows={2}
                          placeholder={item.suggested_answer ? `建议答案: ${item.suggested_answer}` : '请输入确认后的值'}
                          value={currentAnswer}
                          onChange={(e) => handleAnswerChange(item.item_id, e.target.value)}
                        />
                      )}
                      {/* 如果有建议答案且当前为选择题，显示建议 */}
                      {item.suggested_answer && questionType === 'choice' && (
                        <Text type="secondary" style={{ fontSize: 12, marginTop: 4, display: 'block' }}>
                          建议答案: {item.suggested_answer}
                        </Text>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}

            <Divider />

            {/* 操作区域 */}
            <div style={{ textAlign: 'center' }}>
              {submitted ? (
                <Alert
                  message="回答已提交成功"
                  description="请点击下方按钮执行二次任务拆分，拆分完成后将自动跳转到任务复核页。"
                  type="success"
                  showIcon
                  action={
                    <Button
                      type="primary"
                      size="large"
                      icon={<ThunderboltOutlined />}
                      onClick={handleSecondSplit}
                      loading={splitting}
                      className="confirm-button"
                      style={{ background: 'var(--ink)', borderColor: 'var(--ink)' }}
                    >
                      执行二次拆分
                    </Button>
                  }
                />
              ) : (
                <Space>
                  <Button
                    type="primary"
                    size="large"
                    icon={<CheckCircleOutlined />}
                    onClick={handleSubmitAnswers}
                    loading={submitting}
                    className="confirm-button"
                    style={{ background: 'var(--ink)', borderColor: 'var(--ink)' }}
                  >
                    提交所有回答
                  </Button>
                </Space>
              )}
            </div>

            {/* 底部进入下一步（已提交且未拆分时可手动跳转） */}
            {submitted && (
              <div style={{ textAlign: 'right', marginTop: 16 }}>
                <Button
                  type="primary"
                  icon={<RightOutlined />}
                  onClick={() => {
                    completeStep(2)
                    setCurrentStep(3)
                    navigate('/task-review')
                  }}
                  size="large"
                  className="confirm-button"
                  ghost
                >
                  跳转到任务复核
                </Button>
              </div>
            )}
          </div>
        ) : (
          <Empty
            description="暂无追问表单，请点击「生成追问表单」按钮"
            style={{ marginTop: 60 }}
          >
            <Button type="primary" icon={<FormOutlined />} onClick={handleGenerate} loading={generating} className="confirm-button" style={{ background: 'var(--ink)', borderColor: 'var(--ink)' }}>
              生成追问
            </Button>
          </Empty>
        )}
      </Spin>
    </div>
  )
}

export default ClarificationPage
