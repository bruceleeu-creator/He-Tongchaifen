/**
 * 模式标识组件 — 顾问账簿主题
 * 显示当前运行模式（真实解析 / Mock 演示）
 */
import React from 'react'

interface ModeIndicatorProps {
  mode?: string
  modeLabel?: string
  dataSource?: string
}

const ModeIndicator: React.FC<ModeIndicatorProps> = ({ mode, modeLabel, dataSource }) => {
  const isMock = mode === 'mock'
  const cssClass = isMock ? 'mode-indicator mock' : 'mode-indicator real'
  const label = modeLabel || (isMock ? 'Mock 演示' : '真实解析')

  return (
    <span className={cssClass} title={dataSource || ''}>
      <span className="mode-dot" />
      {label}
    </span>
  )
}

export default ModeIndicator
