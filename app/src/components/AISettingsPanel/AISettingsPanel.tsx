/**
 * AI 配置侧边栏面板
 * 用于配置 LLM 服务商和 API Key
 * 顾问账簿主题 — 深墨海军蓝 · 羊皮纸 · 古金
 */
import React, { useState, useEffect, useCallback } from 'react'
import {
  Drawer,
  Form,
  Input,
  Radio,
  Button,
  Space,
  Tag,
  Alert,
  Divider,
  Spin,
  Typography,
  message,
} from 'antd'
import {
  ApiOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ThunderboltOutlined,
  SaveOutlined,
  KeyOutlined,
  InfoCircleOutlined,
} from '@ant-design/icons'
import {
  getAIConfig,
  updateAIConfig,
  testConnection,
  type AIConfig,
  type PresetInfo,
} from '../../services/aiConfig'

const { Text, Paragraph } = Typography

interface AISettingsPanelProps {
  open: boolean
  onClose: () => void
  onConfigChange?: (available: boolean) => void
}

/** 预设服务商配置 */
const PRESETS: Record<string, PresetInfo & { icon: string }> = {
  deepseek: {
    label: 'DeepSeek',
    base_url: 'https://api.deepseek.com/v1',
    model: 'deepseek-chat',
    description: '性价比高，中文合同理解能力强',
    icon: 'D',
  },
  qwen: {
    label: '通义千问 (Qwen)',
    base_url: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    model: 'qwen-plus',
    description: '阿里云通义千问，国内访问稳定',
    icon: 'Q',
  },
  openai: {
    label: 'OpenAI (GPT-4o)',
    base_url: 'https://api.openai.com/v1',
    model: 'gpt-4o',
    description: 'GPT-4o，理解能力最强但成本较高',
    icon: 'O',
  },
}

/** 区块标题样式：衬线体 + 金色左线 */
const sectionTitleStyle: React.CSSProperties = {
  fontFamily: 'var(--font-serif)',
  fontSize: 14,
  fontWeight: 600,
  color: 'var(--ink)',
  marginBottom: 10,
  paddingLeft: 10,
  borderLeft: '3px solid var(--gold)',
}

const AISettingsPanel: React.FC<AISettingsPanelProps> = ({ open, onClose, onConfigChange }) => {
  const [form] = Form.useForm()
  const [loading, setLoading] = useState(false)
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [config, setConfig] = useState<AIConfig | null>(null)
  const [llmAvailable, setLlmAvailable] = useState(false)
  const [testResult, setTestResult] = useState<{
    success: boolean
    message: string
    model?: string
    responsePreview?: string
  } | null>(null)

  /** 加载当前配置 */
  const loadConfig = useCallback(async () => {
    setLoading(true)
    setTestResult(null)
    try {
      const res = await getAIConfig()
      setConfig(res.config)
      setLlmAvailable(res.llm_available)
      const presetKey = res.config.preset || 'deepseek'
      const presetInfo = PRESETS[presetKey]
      form.setFieldsValue({
        preset: presetKey,
        api_key: '',
        base_url: res.config.base_url || presetInfo?.base_url || '',
        model: res.config.model || presetInfo?.model || '',
      })
      onConfigChange?.(res.llm_available)
    } catch (err) {
      message.error('加载 AI 配置失败')
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [form, onConfigChange])

  useEffect(() => {
    if (open) {
      loadConfig()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  /** 表单字段变化：切换预设时自动填充 base_url 和 model */
  const handleValuesChange = (changed: Record<string, unknown>) => {
    if (changed.preset !== undefined) {
      const presetInfo = PRESETS[changed.preset as string]
      if (presetInfo) {
        form.setFieldsValue({
          base_url: presetInfo.base_url,
          model: presetInfo.model,
        })
      }
      setTestResult(null)
    }
  }

  /** 测试连接 */
  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    try {
      const res = await testConnection()
      setTestResult({
        success: res.success,
        message: res.message,
        model: res.model,
        responsePreview: res.response_preview,
      })
      setLlmAvailable(res.llm_available)
      onConfigChange?.(res.llm_available)
      if (res.success) {
        message.success('连接测试成功')
      } else {
        message.warning('连接测试失败')
      }
    } catch (err) {
      const errMsg =
        err instanceof Error ? err.message : '测试连接时发生未知错误'
      setTestResult({
        success: false,
        message: errMsg,
      })
      message.error('测试连接失败')
    } finally {
      setTesting(false)
    }
  }

  /** 保存配置 */
  const handleSave = async () => {
    try {
      const values = await form.validateFields()
      setSaving(true)
      const payload: {
        preset?: string
        api_key?: string
        base_url?: string
        model?: string
      } = {
        preset: values.preset,
        base_url: values.base_url,
        model: values.model,
      }
      // 仅在用户输入了新密钥时才提交
      if (values.api_key) {
        payload.api_key = values.api_key
      }
      const res = await updateAIConfig(payload)
      setLlmAvailable(res.llm_available)
      onConfigChange?.(res.llm_available)
      if (res.success) {
        message.success(res.message || '配置已保存')
        await loadConfig()
      } else {
        message.error(res.message || '保存失败')
      }
    } catch (err) {
      if (err && typeof err === 'object' && 'errorFields' in err) {
        message.error('请检查表单填写是否完整')
      } else {
        message.error('保存配置失败')
        console.error(err)
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <Drawer
      title={
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <ApiOutlined style={{ color: 'var(--gold)' }} />
          <span
            style={{
              fontFamily: 'var(--font-serif)',
              fontWeight: 600,
              color: 'var(--ink)',
            }}
          >
            AI 配置
          </span>
          {llmAvailable ? (
            <Tag
              color="success"
              style={{ marginLeft: 8, marginInlineEnd: 0 }}
            >
              <CheckCircleOutlined /> 已配置
            </Tag>
          ) : (
            <Tag
              color="warning"
              style={{ marginLeft: 8, marginInlineEnd: 0 }}
            >
              <InfoCircleOutlined /> 未配置
            </Tag>
          )}
        </div>
      }
      open={open}
      onClose={onClose}
      width={480}
      placement="right"
      destroyOnClose
      extra={
        <Tag
          style={{
            fontFamily: 'var(--font-mono)',
            fontSize: 11,
            color: 'var(--slate)',
            border: '1px solid #E0D9C8',
            background: 'var(--parchment)',
            marginInlineEnd: 0,
          }}
        >
          {config?.updated_at
            ? `更新于 ${new Date(config.updated_at).toLocaleString('zh-CN')}`
            : '尚未配置'}
        </Tag>
      }
    >
      <Spin spinning={loading}>
        <Form
          form={form}
          layout="vertical"
          requiredMark={false}
          onValuesChange={handleValuesChange}
        >
          {/* 当前状态横幅 */}
          <div
            style={{
              background: llmAvailable
                ? 'rgba(91, 117, 83, 0.06)'
                : 'rgba(155, 44, 44, 0.04)',
              border: `1px solid ${
                llmAvailable
                  ? 'rgba(91, 117, 83, 0.2)'
                  : 'rgba(155, 44, 44, 0.15)'
              }`,
              borderRadius: 4,
              padding: '12px 16px',
              marginBottom: 24,
              display: 'flex',
              alignItems: 'center',
              gap: 10,
            }}
          >
            {llmAvailable ? (
              <CheckCircleOutlined
                style={{ color: 'var(--sage)', fontSize: 18, flexShrink: 0 }}
              />
            ) : (
              <CloseCircleOutlined
                style={{ color: 'var(--crimson)', fontSize: 18, flexShrink: 0 }}
              />
            )}
            <div>
              <Text
                style={{
                  fontFamily: 'var(--font-serif)',
                  fontWeight: 600,
                  color: 'var(--ink)',
                  fontSize: 14,
                }}
              >
                {llmAvailable ? 'AI 服务可用' : 'AI 服务未就绪'}
              </Text>
              <div
                style={{ fontSize: 12, color: 'var(--slate)', marginTop: 2 }}
              >
                {llmAvailable
                  ? `当前模型: ${config?.model || '—'} · 密钥已设置`
                  : '请配置服务商和 API Key 后启用 AI 功能'}
              </div>
            </div>
          </div>

          {/* 服务商选择 */}
          <div className="task-detail-section" style={{ marginBottom: 20 }}>
            <h4 style={sectionTitleStyle}>LLM 服务商</h4>
            <Form.Item name="preset" noStyle>
              <Radio.Group style={{ width: '100%' }}>
                <Space direction="vertical" style={{ width: '100%' }} size={12}>
                  {Object.entries(PRESETS).map(([key, info]) => (
                    <Radio
                      key={key}
                      value={key}
                      style={{
                        width: '100%',
                        alignItems: 'flex-start',
                        padding: '10px 12px',
                        borderRadius: 4,
                        border: '1px solid #E8E2D4',
                        background: 'var(--parchment)',
                      }}
                    >
                      <div
                        style={{
                          display: 'inline-block',
                          marginLeft: 6,
                          verticalAlign: 'top',
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            alignItems: 'center',
                            gap: 8,
                          }}
                        >
                          <span
                            style={{
                              display: 'inline-flex',
                              alignItems: 'center',
                              justifyContent: 'center',
                              width: 22,
                              height: 22,
                              borderRadius: 3,
                              background: 'var(--ink)',
                              color: 'var(--gold)',
                              fontFamily: 'var(--font-serif)',
                              fontWeight: 700,
                              fontSize: 12,
                              flexShrink: 0,
                            }}
                          >
                            {info.icon}
                          </span>
                          <span
                            style={{
                              fontFamily: 'var(--font-serif)',
                              fontWeight: 600,
                              color: 'var(--ink)',
                            }}
                          >
                            {info.label}
                          </span>
                        </div>
                        <div
                          style={{
                            fontSize: 12,
                            color: 'var(--slate)',
                            marginTop: 4,
                            lineHeight: 1.5,
                          }}
                        >
                          {info.description}
                        </div>
                        <div
                          style={{
                            fontSize: 11,
                            color: 'var(--slate-light)',
                            marginTop: 2,
                            fontFamily: 'var(--font-mono)',
                          }}
                        >
                          {info.model} · {info.base_url}
                        </div>
                      </div>
                    </Radio>
                  ))}
                </Space>
              </Radio.Group>
            </Form.Item>
          </div>

          <Divider style={{ borderColor: '#E8E2D4', margin: '20px 0' }} />

          {/* API Key */}
          <div className="task-detail-section" style={{ marginBottom: 20 }}>
            <h4 style={sectionTitleStyle}>
              <KeyOutlined style={{ marginRight: 6 }} />
              API Key
            </h4>
            <Form.Item
              name="api_key"
              label={
                <span style={{ fontSize: 13, color: 'var(--slate)' }}>
                  {config?.has_api_key
                    ? `已设置密钥 (${config.api_key_masked || '••••••••'})，留空则保持不变`
                    : '请输入服务商提供的 API Key'}
                </span>
              }
            >
              <Input.Password
                placeholder="sk-..."
                autoComplete="off"
                style={{ borderRadius: 4 }}
              />
            </Form.Item>
          </div>

          {/* 高级配置 */}
          <div className="task-detail-section" style={{ marginBottom: 20 }}>
            <h4 style={sectionTitleStyle}>接口地址与模型</h4>
            <Form.Item
              name="base_url"
              label={
                <span style={{ fontSize: 13, color: 'var(--slate)' }}>
                  Base URL
                </span>
              }
            >
              <Input
                placeholder="https://api.example.com/v1"
                style={{ borderRadius: 4 }}
              />
            </Form.Item>
            <Form.Item
              name="model"
              label={
                <span style={{ fontSize: 13, color: 'var(--slate)' }}>
                  模型名称
                </span>
              }
            >
              <Input
                placeholder="model-name"
                style={{ borderRadius: 4 }}
              />
            </Form.Item>
          </div>

          <Divider style={{ borderColor: '#E8E2D4', margin: '20px 0' }} />

          {/* 测试结果 */}
          {testResult && (
            <Alert
              type={testResult.success ? 'success' : 'error'}
              showIcon
              icon={
                testResult.success ? (
                  <CheckCircleOutlined />
                ) : (
                  <CloseCircleOutlined />
                )
              }
              message={testResult.success ? '连接成功' : '连接失败'}
              description={
                <div>
                  <div style={{ fontSize: 13 }}>{testResult.message}</div>
                  {testResult.model && (
                    <div
                      style={{
                        fontSize: 12,
                        color: 'var(--slate)',
                        marginTop: 4,
                        fontFamily: 'var(--font-mono)',
                      }}
                    >
                      Model: {testResult.model}
                    </div>
                  )}
                  {testResult.responsePreview && (
                    <div
                      style={{
                        fontSize: 12,
                        color: 'var(--slate)',
                        marginTop: 4,
                        padding: '6px 8px',
                        background: 'var(--parchment)',
                        borderRadius: 3,
                        border: '1px solid #E8E2D4',
                        maxHeight: 80,
                        overflow: 'auto',
                      }}
                    >
                      {testResult.responsePreview}
                    </div>
                  )}
                </div>
              }
              style={{ marginBottom: 20, borderRadius: 4 }}
            />
          )}

          {/* 操作按钮 */}
          <div style={{ display: 'flex', gap: 12, marginTop: 8 }}>
            <Button
              icon={<ThunderboltOutlined />}
              loading={testing}
              onClick={handleTest}
              style={{
                flex: 1,
                borderColor: 'var(--gold)',
                color: 'var(--gold)',
                fontWeight: 500,
              }}
            >
              测试连接
            </Button>
            <Button
              type="primary"
              icon={<SaveOutlined />}
              loading={saving}
              onClick={handleSave}
              style={{ flex: 1, fontWeight: 500 }}
            >
              保存配置
            </Button>
          </div>

          {/* 温馨提示 */}
          <Paragraph
            style={{
              marginTop: 24,
              padding: '10px 14px',
              background: 'var(--parchment)',
              borderRadius: 4,
              borderLeft: '3px solid var(--gold)',
              fontSize: 12,
              color: 'var(--slate)',
              lineHeight: 1.7,
              marginBottom: 0,
            }}
          >
            <InfoCircleOutlined
              style={{ marginRight: 6, color: 'var(--gold)' }}
            />
            API Key 仅存储在服务端，不会暴露在前端。建议先点击"测试连接"验证密钥有效性后再保存。
          </Paragraph>
        </Form>
      </Spin>
    </Drawer>
  )
}

export default AISettingsPanel
