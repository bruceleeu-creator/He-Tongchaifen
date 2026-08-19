/**
 * 页面2: 识别结果
 * - 合同识别摘要确认 Tab（新增，排在第一个）
 * - 合同识别 Tab
 * - 计划识别 Tab
 * - 交叉核验 Tab
 * - 顶部显示运行模式标识
 */
import React, { useState, useEffect } from 'react'
import { Card, Button, Tabs, Table, Tag, Typography, Space, Alert, Spin, Empty, Descriptions, List, Row, Col, Tooltip } from 'antd'
import { message } from '../../utils/messageBridge'
import { PlayCircleOutlined, RightOutlined, ReloadOutlined, CheckCircleOutlined } from '@ant-design/icons'
import { useNavigate } from 'react-router-dom'
import {
  recognizeContract,
  recognizePlan,
  crossCheck,
  getRecognitionResults,
  getContractSummary,
  confirmContractSummary,
} from '../../services/recognition'
import { useProjectStore } from '../../stores/projectStore'
import { useStepStore } from '../../stores/stepStore'
import ModeIndicator from '../../components/ModeIndicator'
import type { ContractRecognitionResult, PlanRecognitionResult, CrossValidationResult, ContractSummaryResponse, RecognitionBasisItem } from '../../types'

/** 从 basic_info 条目兼容读取新/旧字段名 */
const getFieldLabel = (item: RecognitionBasisItem): string => item['字段名称'] || item['字段'] || '-'
const getFieldValue = (item: RecognitionBasisItem): string => item['提取结果'] || '-'
const getFieldExcerpt = (item: RecognitionBasisItem): string =>
  item['依据原文摘录'] || item['原文摘录'] || item['依据摘要'] || '合同未明确'
const getFieldSource = (item: RecognitionBasisItem): string => item['来源文件'] || '-'
const getFieldPending = (item: RecognitionBasisItem): string => {
  const raw = item['是否待确认']
  if (raw) return raw
  // 旧数据无此字段时，根据提取结果推断
  const value = item['提取结果'] || ''
  return (!value || value === '待人工确认' || value === '待确认' || value === '合同未明确') ? '是' : '否'
}
const getFieldConfidence = (item: RecognitionBasisItem): string => {
  const raw = item['置信度']
  if (raw) return raw
  return getFieldPending(item) === '是' ? '低' : '高'
}

const { Title, Text } = Typography

const RecognitionPage: React.FC = () => {
  const navigate = useNavigate()
  const { runId } = useProjectStore()
  const { setCurrentStep, completeStep } = useStepStore()
  const [activeTab, setActiveTab] = useState('summary')
  const [loading, setLoading] = useState(false)
  const [recognizing, setRecognizing] = useState(false)
  const [contractResult, setContractResult] = useState<ContractRecognitionResult | null>(null)
  const [planResult, setPlanResult] = useState<PlanRecognitionResult | null>(null)
  const [crossCheckResult, setCrossCheckResult] = useState<CrossValidationResult | null>(null)

  // 摘要相关状态
  const [summaryData, setSummaryData] = useState<ContractSummaryResponse | null>(null)
  const [summaryConfirmed, setSummaryConfirmed] = useState(false)
  const [confirmingSummary, setConfirmingSummary] = useState(false)

  /** 加载合同识别摘要 */
  const loadSummary = async () => {
    if (!runId) return
    try {
      const res = await getContractSummary(runId, { silent: true })
      if (res.success) {
        setSummaryData(res)
        // 如果不需要确认或已确认过，标记为已确认
        if (!res.confirm_required) {
          setSummaryConfirmed(true)
        }
      }
    } catch {
      // 摘要可能不存在
    }
  }

  /** 加载已有识别结果 */
  const loadResults = async () => {
    if (!runId) return
    setLoading(true)
    setContractResult(null)
    setPlanResult(null)
    setCrossCheckResult(null)
    try {
      const results = await getRecognitionResults(runId)
      if (results.contract) setContractResult(results.contract)
      if (results.plan) setPlanResult(results.plan)
      if (results.crossCheck) setCrossCheckResult(results.crossCheck)
    } catch {
      // 忽略
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    setSummaryData(null)
    setSummaryConfirmed(false)
    loadSummary()
    loadResults()
  }, [runId])

  /** 确认合同摘要 */
  const handleConfirmSummary = async () => {
    if (!runId) return
    setConfirmingSummary(true)
    try {
      const res = await confirmContractSummary(runId)
      if (res.success) {
        setSummaryConfirmed(true)
        message.success('合同摘要已确认，请继续进行澄清追问')
        // 引导用户进入澄清问题环节
        setActiveTab('contract')
      }
    } catch {
      // 忽略
    } finally {
      setConfirmingSummary(false)
    }
  }

  /** 执行所有识别 */
  const handleRecognizeAll = async () => {
    if (!runId) {
      message.warning('请先在资料上传页面创建运行实例')
      return
    }
    setRecognizing(true)
    try {
      const contractRes = await recognizeContract(runId)
      if (contractRes.success) {
        setContractResult(contractRes.data)
        message.success('合同识别完成')
      }

      const planRes = await recognizePlan(runId)
      if (planRes.success) {
        setPlanResult(planRes.data)
        if (planRes.skipped) {
          message.warning(planRes.message || '未上传年度服务计划，已跳过计划识别')
        } else {
          message.success('计划识别完成')
        }
      }

      const crossRes = await crossCheck(runId)
      if (crossRes.success) {
        setCrossCheckResult(crossRes.data)
        message.success('交叉核验完成')
      }

      message.success('全部识别完成')
      // 刷新摘要
      loadSummary()
    } catch {
      // 忽略
    } finally {
      setRecognizing(false)
    }
  }

  /** 渲染只读表格（通用）
   * 修复滚动问题（需求5）：
   * - 列宽自适应内容，最少 120px，避免被挤到重叠
   * - 同时启用 x（左右）和 y（上下）滚动，y 限制最大 360px，超过出现垂直滚动条
   * - 第一列固定（fixed: 'left'），便于横向滚动时仍可识别行
   */
  const renderReadOnlyTable = (data: Array<Record<string, string>> | undefined, emptyText: string) => {
    if (!data || data.length === 0) {
      return <Empty description={emptyText} />
    }
    const keys = Object.keys(data[0])
    const columns = keys.map((key, idx) => ({
      title: key,
      dataIndex: key,
      key: key,
      width: 160,
      minWidth: 120,
      ellipsis: true,
      fixed: idx === 0 ? ('left' as const) : undefined,
      render: (text: string) => (
        <Tooltip title={text || '-'} placement="topLeft">
          <span style={{ fontSize: 13, display: 'inline-block', maxWidth: '100%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{text || '-'}</span>
        </Tooltip>
      ),
    }))
    // 计算横向宽度：列数 * 160（minWidth），保证一定溢出触发横向滚动条
    const xWidth = Math.max(keys.length * 160, 800)
    return (
      <Table
        columns={columns}
        dataSource={data.map((item, index) => ({ ...item, _key: index }))}
        rowKey="_key"
        size="small"
        pagination={false}
        scroll={{ x: xWidth, y: 360 }}
        bordered
      />
    )
  }

  /** 渲染合同摘要 */
  const renderSummary = () => {
    if (!summaryData) {
      return (
        <Empty description="暂无合同识别摘要，请先执行合同识别">
          <Button type="primary" icon={<PlayCircleOutlined />} onClick={handleRecognizeAll} loading={recognizing}>
            开始识别
          </Button>
        </Empty>
      )
    }

    const s = summaryData.summary
    return (
      <Spin spinning={loading}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          {/* 待确认事项提示 */}
          {summaryData.pending_items && summaryData.pending_items.length > 0 && (
            <Alert
              message={`发现 ${summaryData.pending_items.length} 项待确认事项`}
              description="请仔细核对以下待确认事项，确认摘要后可进入澄清追问环节处理。"
              type="warning"
              showIcon
            />
          )}

          {/* 统计卡片 */}
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <div className="summary-stat gold">
                <div className="stat-value">{s['服务费用（总计）'] || '-'}</div>
                <div className="stat-label">合同总额</div>
              </div>
            </Col>
            <Col span={6}>
              <div className="summary-stat">
                <div className="stat-value">{s.交付成果数量 ?? '-'}</div>
                <div className="stat-label">交付成果</div>
              </div>
            </Col>
            <Col span={6}>
              <div className="summary-stat">
                <div className="stat-value">{s.服务模块?.length ?? '-'}</div>
                <div className="stat-label">服务模块</div>
              </div>
            </Col>
            <Col span={6}>
              <div className="summary-stat">
                <div className="stat-value" style={{ color: 'var(--amber)' }}>{s.待确认事项数量 ?? '-'}</div>
                <div className="stat-label">待确认事项</div>
              </div>
            </Col>
          </Row>

          {/* 合同核心字段 */}
          <Card title="合同核心信息" size="small" className="ledger-card">
            <Descriptions bordered column={2} size="small">
              <Descriptions.Item label="甲方">{s.甲方 || '-'}</Descriptions.Item>
              <Descriptions.Item label="乙方">{s.乙方 || '-'}</Descriptions.Item>
              <Descriptions.Item label="项目名称">{s.项目名称 || '-'}</Descriptions.Item>
              <Descriptions.Item label="服务期限">{s.服务期限 || '-'}</Descriptions.Item>
              <Descriptions.Item label="合同签署日期">{s.合同签署日期 || '-'}</Descriptions.Item>
              <Descriptions.Item label="服务费用（总计）">{s['服务费用（总计）'] || '-'}</Descriptions.Item>
              <Descriptions.Item label="首期款">{s.首期款 || '-'}</Descriptions.Item>
              <Descriptions.Item label="尾期款">{s.尾期款 || '-'}</Descriptions.Item>
              <Descriptions.Item label="服务方式">{s.服务方式 || '-'}</Descriptions.Item>
              <Descriptions.Item label="驻场安排">{s.驻场安排 || '-'}</Descriptions.Item>
              <Descriptions.Item label="响应时效">{s.响应时效 || '-'}</Descriptions.Item>
              <Descriptions.Item label="交付成果数量">{s.交付成果数量 ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="待确认事项数量">{s.待确认事项数量 ?? '-'}</Descriptions.Item>
              <Descriptions.Item label="识别模式">{s.识别模式 || '-'}</Descriptions.Item>
              <Descriptions.Item label="数据来源">{s.数据来源 || '-'}</Descriptions.Item>
              <Descriptions.Item label="是否使用样例任务">
                {s.是否使用样例任务 ? '是' : '否'}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          {/* 服务模块 */}
          {s.服务模块 && s.服务模块.length > 0 && (
            <Card title="服务模块" size="small" className="ledger-card">
              <Space wrap>
                {s.服务模块.map((mod, idx) => (
                  <Tag key={idx} style={{ color: 'var(--gold)', borderColor: 'var(--gold)', background: 'rgba(184,149,74,0.06)' }}>{mod}</Tag>
                ))}
              </Space>
            </Card>
          )}

          {/* 服务范围明细表 */}
          {summaryData.service_scope && summaryData.service_scope.length > 0 && (
            <Card title="服务范围明细" size="small" className="ledger-card">
              {renderReadOnlyTable(summaryData.service_scope, '暂无服务范围数据')}
            </Card>
          )}

          {/* 识别依据明细表 */}
          {summaryData.basic_info && summaryData.basic_info.length > 0 && (
            <Card title="识别依据明细" size="small" className="ledger-card">
              <Table
                size="small"
                bordered
                rowKey={(_, idx) => String(idx)}
                dataSource={summaryData.basic_info}
                pagination={false}
                scroll={{ x: 1100, y: 360 }}
                columns={[
                  {
                    title: '字段名称',
                    dataIndex: '字段名称',
                    key: '字段名称',
                    width: 160,
                    render: (_: string, record: RecognitionBasisItem) => (
                      <Text strong>{getFieldLabel(record)}</Text>
                    ),
                  },
                  {
                    title: '提取结果',
                    dataIndex: '提取结果',
                    key: '提取结果',
                    width: 200,
                    ellipsis: { showTitle: false },
                    render: (_: string, record: RecognitionBasisItem) => {
                      const value = getFieldValue(record)
                      return (
                        <Tooltip title={value} placement="topLeft">
                          <span style={{ fontSize: 13 }}>{value}</span>
                        </Tooltip>
                      )
                    },
                  },
                  {
                    title: '依据原文摘录',
                    dataIndex: '依据原文摘录',
                    key: '依据原文摘录',
                    ellipsis: { showTitle: false },
                    render: (_: string, record: RecognitionBasisItem) => {
                      const excerpt = getFieldExcerpt(record)
                      return (
                        <Tooltip title={excerpt} placement="topLeft">
                          <Text type="secondary" style={{ fontSize: 12 }}>{excerpt}</Text>
                        </Tooltip>
                      )
                    },
                  },
                  {
                    title: '来源文件',
                    dataIndex: '来源文件',
                    key: '来源文件',
                    width: 180,
                    ellipsis: { showTitle: false },
                    render: (_: string, record: RecognitionBasisItem) => {
                      const src = getFieldSource(record)
                      return (
                        <Tooltip title={src} placement="topLeft">
                          <span style={{ fontSize: 12 }}>{src}</span>
                        </Tooltip>
                      )
                    },
                  },
                  {
                    title: '是否待确认',
                    dataIndex: '是否待确认',
                    key: '是否待确认',
                    width: 100,
                    render: (_: string, record: RecognitionBasisItem) => {
                      const pending = getFieldPending(record)
                      return (
                        <Tag color={pending === '是' ? 'warning' : 'success'}>{pending}</Tag>
                      )
                    },
                  },
                  {
                    title: '置信度',
                    dataIndex: '置信度',
                    key: '置信度',
                    width: 80,
                    render: (_: string, record: RecognitionBasisItem) => {
                      const conf = getFieldConfidence(record)
                      return (
                        <Tag color={conf === '高' ? 'green' : 'orange'}>{conf}</Tag>
                      )
                    },
                  },
                ]}
              />
            </Card>
          )}

          {/* 待确认事项列表 */}
          {summaryData.pending_items && summaryData.pending_items.length > 0 && (
            <Card title="待确认事项列表" size="small" className="ledger-card">
              <List
                size="small"
                bordered
                dataSource={summaryData.pending_items}
                renderItem={(item, idx) => (
                  <List.Item key={idx}>
                    {Object.entries(item).map(([k, v]) => (
                      <span key={k} style={{ marginRight: 16 }}>
                        <Text type="secondary">{k}: </Text>
                        <Text>{v}</Text>
                      </span>
                    ))}
                  </List.Item>
                )}
              />
            </Card>
          )}

          {/* 确认按钮 */}
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            {summaryConfirmed ? (
              <Alert
                message="合同摘要已确认"
                description="您可以继续查看识别详情或进入下一步澄清追问。"
                type="success"
                showIcon
                action={
                  <Button type="primary" icon={<RightOutlined />} onClick={handleNext}>
                    进入澄清追问
                  </Button>
                }
              />
            ) : (
              <Space>
                <Button
                  type="primary"
                  size="large"
                  icon={<CheckCircleOutlined />}
                  onClick={handleConfirmSummary}
                  loading={confirmingSummary}
                  className="confirm-button"
                  style={{ background: 'var(--ink)', borderColor: 'var(--ink)' }}
                >
                  确认摘要
                </Button>
                <Button size="large" onClick={() => setActiveTab('contract')}>
                  查看识别详情
                </Button>
              </Space>
            )}
          </div>
        </Space>
      </Spin>
    )
  }

  /** 进入下一步 */
  const handleNext = () => {
    completeStep(1)
    setCurrentStep(2)
    navigate('/clarification')
  }

  if (!runId) {
    return (
      <div className="page-container">
        <Alert
          message="请先上传文件"
          description="请先在资料上传页面上传文件或加载 Mock 数据"
          type="warning"
          showIcon
          action={
            <Button type="primary" onClick={() => navigate('/upload')}>
              去上传
            </Button>
          }
        />
      </div>
    )
  }

  const tabItems = [
    {
      key: 'summary',
      label: (
        <span>
          合同识别摘要
          {summaryConfirmed && <Tag color="success" style={{ marginLeft: 4 }}>已确认</Tag>}
          {summaryData && !summaryConfirmed && <Tag color="warning" style={{ marginLeft: 4 }}>待确认</Tag>}
        </span>
      ),
      children: renderSummary(),
    },
    {
      key: 'contract',
      label: (
        <span>
          合同识别
          {contractResult && <Tag color="success" style={{ marginLeft: 4 }}>已完成</Tag>}
        </span>
      ),
      children: (
        <Spin spinning={loading}>
          {contractResult ? (
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              <Descriptions title="基础信息" bordered size="small" column={1}>
                {contractResult.basic_info?.map((item, idx) => (
                  <Descriptions.Item key={idx} label={getFieldLabel(item)}>
                    {getFieldValue(item)}
                    <br />
                    <Text type="secondary" style={{ fontSize: 12 }}>依据: {getFieldExcerpt(item)}</Text>
                  </Descriptions.Item>
                ))}
              </Descriptions>
              <div>
                <Title level={5}>合同约定的服务范围</Title>
                {renderReadOnlyTable(contractResult.service_scope, '暂无服务范围数据')}
              </div>
              <div>
                <Title level={5}>客户责任和配合事项</Title>
                {renderReadOnlyTable(contractResult.client_responsibilities, '暂无客户责任数据')}
              </div>
              <div>
                <Title level={5}>我方责任和交付义务</Title>
                {renderReadOnlyTable(contractResult.our_responsibilities, '暂无我方责任数据')}
              </div>
              <div>
                <Title level={5}>暂停、延期和顺延规则</Title>
                {renderReadOnlyTable(contractResult.delay_rules, '暂无延期规则数据')}
              </div>
              <div>
                <Title level={5}>待人工确认事项</Title>
                {renderReadOnlyTable(contractResult.pending_items, '暂无待确认事项')}
              </div>
            </Space>
          ) : (
            <Empty description="尚未执行合同识别，请点击上方按钮开始" />
          )}
        </Spin>
      ),
    },
    {
      key: 'plan',
      label: (
        <span>
          计划识别
          {planResult && <Tag color="success" style={{ marginLeft: 4 }}>已完成</Tag>}
        </span>
      ),
      children: (
        <Spin spinning={loading}>
          {planResult ? (
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              {planResult.plan_summary && (
                <Card title="计划总体摘要" size="small" className="ledger-card">
                  <Descriptions bordered column={1} size="small">
                    <Descriptions.Item label="项目周期">{planResult.plan_summary.项目周期 || '-'}</Descriptions.Item>
                    <Descriptions.Item label="总体服务频次">{planResult.plan_summary.总体服务频次 || '-'}</Descriptions.Item>
                    <Descriptions.Item label="驻场安排">{planResult.plan_summary.驻场安排 || '-'}</Descriptions.Item>
                  </Descriptions>
                </Card>
              )}
              <div>
                <Title level={5}>年度服务模块</Title>
                {renderReadOnlyTable(planResult.service_modules, '暂无服务模块数据')}
              </div>
              <div>
                <Title level={5}>阶段节点</Title>
                {renderReadOnlyTable(planResult.milestones, '暂无阶段节点数据')}
              </div>
              <div>
                <Title level={5}>客户资料和配合事项</Title>
                {renderReadOnlyTable(planResult.client_data, '暂无客户资料数据')}
              </div>
              <div>
                <Title level={5}>会议和确认事项</Title>
                {renderReadOnlyTable(planResult.meetings, '暂无会议数据')}
              </div>
              <div>
                <Title level={5}>交付物清单</Title>
                {renderReadOnlyTable(planResult.deliverables, '暂无交付物数据')}
              </div>
              <div>
                <Title level={5}>责任人安排</Title>
                {renderReadOnlyTable(planResult.responsible_parties, '暂无责任人数据')}
              </div>
              <div>
                <Title level={5}>待人工确认事项</Title>
                {renderReadOnlyTable(planResult.pending_items, '暂无待确认事项')}
              </div>
            </Space>
          ) : (
            <Empty description="尚未执行计划识别，请点击上方按钮开始" />
          )}
        </Spin>
      ),
    },
    {
      key: 'cross-check',
      label: (
        <span>
          交叉核验
          {crossCheckResult && <Tag color="success" style={{ marginLeft: 4 }}>已完成</Tag>}
        </span>
      ),
      children: (
        <Spin spinning={loading}>
          {crossCheckResult ? (
            <Space direction="vertical" style={{ width: '100%' }} size="middle">
              {crossCheckResult.summary && (
                <Alert message="核验总结" description={crossCheckResult.summary} type="info" showIcon />
              )}
              <div>
                <Title level={5}>一致事项</Title>
                {renderReadOnlyTable(crossCheckResult.consistent_items, '暂无一致事项')}
              </div>
              <div>
                <Title level={5}>冲突事项</Title>
                {renderReadOnlyTable(crossCheckResult.conflict_items, '暂无冲突事项')}
              </div>
              <div>
                <Title level={5}>缺失事项</Title>
                {renderReadOnlyTable(crossCheckResult.missing_items, '暂无缺失事项')}
              </div>
            </Space>
          ) : (
            <Empty description="尚未执行交叉核验，请点击上方按钮开始" />
          )}
        </Spin>
      ),
    },
  ]

  return (
    <div className="page-container">
      <div className="ledger-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h4>合同识别</h4>
            <div className="ledger-subtitle">深度解析合同原文 · 确认识别摘要 · 交叉核验</div>
            <div style={{ marginTop: 8 }}>
              <ModeIndicator
                mode={summaryData?.mode || 'rule'}
                modeLabel={summaryData?.mode_label}
                dataSource={summaryData?.data_source}
              />
            </div>
          </div>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => { loadSummary(); loadResults() }} loading={loading}>
              刷新
            </Button>
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              onClick={handleRecognizeAll}
              loading={recognizing}
              size="large"
              className="confirm-button"
              style={{ background: 'var(--ink)', borderColor: 'var(--ink)' }}
            >
              开始识别
            </Button>
          </Space>
        </div>
      </div>

      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        items={tabItems}
        style={{ minHeight: 400 }}
      />

      <div style={{ textAlign: 'right', marginTop: 16 }}>
        <Button
          type="primary"
          icon={<RightOutlined />}
          onClick={handleNext}
          disabled={!contractResult}
          size="large"
          className="confirm-button"
          style={{ background: 'var(--ink)', borderColor: 'var(--ink)' }}
        >
          进入下一步
        </Button>
      </div>
    </div>
  )
}

export default RecognitionPage
