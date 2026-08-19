/**
 * Axios 实例
 * baseURL 为 /api，由 vite proxy 代理到 http://localhost:8000
 */
import axios from 'axios'
import { message } from '../utils/messageBridge'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    return config
  },
  (error) => {
    return Promise.reject(error)
  },
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    if (error.response) {
      const { status, data } = error.response
      const detail = data?.detail || data?.message || '请求失败'
      if ((error.config as any)?.suppressErrorMessage) {
        return Promise.reject(error)
      } else if (status === 404) {
        message.error(`资源不存在: ${detail}`)
      } else if (status === 500) {
        message.error(`服务器错误: ${detail}`)
      } else {
        message.error(`请求错误(${status}): ${detail}`)
      }
    } else if (error.request) {
      message.error('网络连接失败，请检查后端服务是否启动')
    } else {
      message.error(`请求异常: ${error.message}`)
    }
    return Promise.reject(error)
  },
)

export default api
