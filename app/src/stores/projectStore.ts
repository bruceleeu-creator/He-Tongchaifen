/**
 * 项目状态管理
 * 管理 runId、项目信息、文件列表
 * 使用 localStorage 手动持久化 runId，防止页面刷新丢失
 */
import { create } from 'zustand'
import type { RunInfo } from '../types'

const STORAGE_KEY = 'psw-project'

interface PersistedState {
  runId: string | null
  mode: string
  runInfo: RunInfo | null
}

/** 从 localStorage 读取持久化状态 */
function loadPersistedState(): Partial<PersistedState> {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return {}
    return JSON.parse(raw)
  } catch {
    return {}
  }
}

/** 保存状态到 localStorage */
function savePersistedState(state: PersistedState) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      runId: state.runId,
      mode: state.mode,
      runInfo: state.runInfo,
    }))
  } catch {
    // localStorage 不可用时静默失败
  }
}

interface ProjectState extends PersistedState {
  projectName: string
  clientName: string
  files: RunInfo[]
  setRunId: (runId: string | null) => void
  setProjectName: (name: string) => void
  setClientName: (name: string) => void
  setRunInfo: (info: RunInfo | null) => void
  setFiles: (files: RunInfo[]) => void
  reset: () => void
}

const persisted = loadPersistedState()

export const useProjectStore = create<ProjectState>((set) => ({
  runId: persisted.runId ?? null,
  mode: persisted.mode ?? 'rule',
  projectName: '',
  clientName: '',
  files: [],
  runInfo: persisted.runInfo ?? null,
  setRunId: (runId) => {
    set({ runId })
    const s = useProjectStore.getState()
    savePersistedState({ runId: s.runId, mode: s.mode, runInfo: s.runInfo })
  },
  setProjectName: (projectName) => set({ projectName }),
  setClientName: (clientName) => set({ clientName }),
  setRunInfo: (runInfo) => {
    set({ runInfo })
    const s = useProjectStore.getState()
    savePersistedState({ runId: s.runId, mode: s.mode, runInfo: s.runInfo })
  },
  setFiles: (files) => set({ files }),
  reset: () => {
    set({ runId: null, mode: 'rule', projectName: '', clientName: '', files: [], runInfo: null })
    try { localStorage.removeItem(STORAGE_KEY) } catch { /* noop */ }
  },
}))
