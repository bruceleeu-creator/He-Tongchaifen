/**
 * Antd v5 Message 桥接工具
 * 解决 message 静态方法无法消费 ConfigProvider 主题上下文的警告
 * 用法：
 *   1. 在根组件内挂载 <MessageBridge />
 *   2. 各文件将 `import { message } from 'antd'` 改为 `import { message } from '../utils/messageBridge'`
 */
import React, { createContext, useContext, useRef } from 'react'
import type { MessageInstance } from 'antd/es/message/interface'
import { App } from 'antd'

// 模块级引用，供非组件代码（如 axios 拦截器）使用
let staticMessage: MessageInstance | null = null

export const setMessageInstance = (instance: MessageInstance) => {
  staticMessage = instance
}

/** 代理对象：在组件未挂载前静默，挂载后转发到真实 API */
export const message = {
  success: (...args: Parameters<MessageInstance['success']>) => staticMessage?.success(...args),
  error: (...args: Parameters<MessageInstance['error']>) => staticMessage?.error(...args),
  warning: (...args: Parameters<MessageInstance['warning']>) => staticMessage?.warning(...args),
  info: (...args: Parameters<MessageInstance['info']>) => staticMessage?.info(...args),
  loading: (...args: Parameters<MessageInstance['loading']>) => staticMessage?.loading(...args),
  open: (...args: Parameters<MessageInstance['open']>) => staticMessage?.open(...args),
  destroy: (...args: Parameters<MessageInstance['destroy']>) => staticMessage?.destroy(...args),
}

/** 挂载在 <App> 内部的隐形组件，将 message API 桥接到模块级变量 */
export const MessageBridge: React.FC = () => {
  const { message: msgApi } = App.useApp()
  // 用 ref 确保只赋值一次
  const assigned = useRef(false)
  if (!assigned.current) {
    setMessageInstance(msgApi)
    assigned.current = true
  }
  return null
}
