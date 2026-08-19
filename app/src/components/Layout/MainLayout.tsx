/**
 * 整体布局 — 顾问账簿主题
 * 深墨海军蓝侧边栏 + 金色强调线 + 羊皮纸内容区
 * 集成 AI 配置面板和全流程进度面板
 */
import React, { useState } from 'react'
import { Layout, Menu, Button, Badge, Tooltip } from 'antd'
import {
  UploadOutlined,
  ScanOutlined,
  FormOutlined,
  TableOutlined,
  HistoryOutlined,
  DownloadOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons'
import { useNavigate, useLocation, Outlet } from 'react-router-dom'
import StepNav from '../StepNav/StepNav'
import AISettingsPanel from '../AISettingsPanel/AISettingsPanel'
import PipelineProgress from '../PipelineProgress/PipelineProgress'
import { useProjectStore } from '../../stores/projectStore'
import { getAIConfig } from '../../services/aiConfig'

const { Header, Sider, Content } = Layout

const iconMap: Record<string, React.ReactNode> = {
  UploadOutlined: <UploadOutlined />,
  ScanOutlined: <ScanOutlined />,
  FormOutlined: <FormOutlined />,
  TableOutlined: <TableOutlined />,
  HistoryOutlined: <HistoryOutlined />,
  DownloadOutlined: <DownloadOutlined />,
}

const menuItems = [
  { key: '/upload', icon: 'UploadOutlined', label: '资料上传' },
  { key: '/recognition', icon: 'ScanOutlined', label: '合同识别' },
  { key: '/clarification', icon: 'FormOutlined', label: '澄清追问' },
  { key: '/task-review', icon: 'TableOutlined', label: '任务复核' },
  { key: '/version-history', icon: 'HistoryOutlined', label: '版本记录' },
  { key: '/export', icon: 'DownloadOutlined', label: '导出报告' },
]

const MainLayout: React.FC = () => {
  const [collapsed, setCollapsed] = useState(false)
  const [aiPanelOpen, setAiPanelOpen] = useState(false)
  const [pipelineOpen, setPipelineOpen] = useState(false)
  const [aiAvailable, setAiAvailable] = useState(false)
  const navigate = useNavigate()
  const location = useLocation()
  const { runId } = useProjectStore()

  const selectedKey = '/' + location.pathname.split('/')[1]

  const handleMenuClick = ({ key }: { key: string }) => {
    navigate(key)
  }

  // 打开 AI 配置面板时刷新状态
  const handleOpenAIPanel = async () => {
    setAiPanelOpen(true)
    try {
      const res = await getAIConfig()
      setAiAvailable(res.llm_available)
    } catch {
      // 忽略错误
    }
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        theme="dark"
        width={220}
        style={{
          background: 'var(--ink)',
          position: 'sticky',
          top: 0,
          height: '100vh',
          overflow: 'auto',
        }}
      >
        {/* 品牌区 */}
        <div className="sidebar-brand">
          <div className="brand-mark">合同</div>
          {!collapsed && <span className="brand-text">项目拆分监督</span>}
        </div>

        <Menu
          mode="inline"
          theme="dark"
          selectedKeys={[selectedKey]}
          items={menuItems.map((item) => ({
            key: item.key,
            icon: iconMap[item.icon],
            label: item.label,
          }))}
          onClick={handleMenuClick}
          style={{
            background: 'transparent',
            borderRight: 'none',
            paddingTop: 8,
          }}
        />

        {/* AI 功能区 */}
        <div className="sidebar-ai-section">
          {!collapsed && (
            <>
              <div className="sidebar-ai-label">AI 工具</div>
              <Button
                block
                ghost
                size="small"
                icon={<ThunderboltOutlined />}
                onClick={() => setPipelineOpen(true)}
                disabled={!runId}
                style={{
                  marginBottom: 8,
                  borderColor: 'var(--gold)',
                  color: 'var(--gold)',
                  fontSize: 13,
                }}
              >
                全流程分析
              </Button>
              <Button
                block
                ghost
                size="small"
                icon={<SettingOutlined />}
                onClick={handleOpenAIPanel}
                style={{
                  borderColor: aiAvailable ? 'var(--sage)' : 'var(--slate-light)',
                  color: aiAvailable ? 'var(--sage)' : 'var(--slate-light)',
                  fontSize: 13,
                }}
              >
                AI 配置 {aiAvailable ? '✓' : ''}
              </Button>
            </>
          )}
          {collapsed && (
            <>
              <Tooltip title="全流程分析" placement="right">
                <Button
                  ghost
                  size="small"
                  icon={<ThunderboltOutlined />}
                  onClick={() => setPipelineOpen(true)}
                  disabled={!runId}
                  style={{ marginBottom: 8, borderColor: 'var(--gold)', color: 'var(--gold)' }}
                />
              </Tooltip>
              <Tooltip title="AI 配置" placement="right">
                <Button
                  ghost
                  size="small"
                  icon={<SettingOutlined />}
                  onClick={handleOpenAIPanel}
                  style={{ borderColor: aiAvailable ? 'var(--sage)' : 'var(--slate-light)', color: aiAvailable ? 'var(--sage)' : 'var(--slate-light)' }}
                />
              </Tooltip>
            </>
          )}
        </div>

        {/* 运行实例标识 */}
        {!collapsed && runId && (
          <div className="sidebar-runid">
            RUN · {runId.substring(0, 12)}
          </div>
        )}
      </Sider>

      <Layout>
        <StepNav />
        <Content
          style={{
            margin: 16,
            padding: 0,
            background: 'var(--porcelain)',
            borderRadius: 6,
            overflow: 'auto',
            boxShadow: '0 1px 4px rgba(27, 35, 50, 0.04)',
          }}
        >
          <Outlet />
        </Content>
      </Layout>

      {/* AI 配置侧边栏 */}
      <AISettingsPanel
        open={aiPanelOpen}
        onClose={() => setAiPanelOpen(false)}
        onConfigChange={(available) => setAiAvailable(available)}
      />

      {/* 全流程进度面板 */}
      <PipelineProgress
        open={pipelineOpen}
        onClose={() => setPipelineOpen(false)}
        runId={runId}
      />
    </Layout>
  )
}

export default MainLayout
