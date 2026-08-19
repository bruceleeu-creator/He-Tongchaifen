/**
 * 任务状态管理
 * 管理任务列表、待确认清单、风险提示、选中任务索引
 */
import { create } from 'zustand'
import type { Task, PendingItem, RiskItem, GranularityCheckResult } from '../types'

interface TaskState {
  /** 任务列表 */
  tasks: Task[]
  /** 任务总数 */
  total: number
  /** 待确认清单 */
  pendingItems: PendingItem[]
  /** 风险提示列表 */
  riskItems: RiskItem[]
  /** 颗粒度检查结果 */
  granularityResult: GranularityCheckResult | null
  /** 选中任务索引 */
  selectedIndex: number
  /** 设置任务列表 */
  setTasks: (tasks: Task[]) => void
  /** 更新单个任务 */
  updateTaskInStore: (taskId: string, updates: Partial<Task>) => void
  /** 添加任务 */
  addTaskToStore: (task: Task) => void
  /** 删除任务 */
  removeTaskFromStore: (taskId: string) => void
  /** 设置待确认清单 */
  setPendingItems: (items: PendingItem[]) => void
  /** 设置风险提示 */
  setRiskItems: (items: RiskItem[]) => void
  /** 设置颗粒度检查结果 */
  setGranularityResult: (result: GranularityCheckResult | null) => void
  /** 设置选中索引 */
  setSelectedIndex: (index: number) => void
  /** 重置 */
  reset: () => void
}

export const useTaskStore = create<TaskState>((set) => ({
  tasks: [],
  total: 0,
  pendingItems: [],
  riskItems: [],
  granularityResult: null,
  selectedIndex: -1,
  setTasks: (tasks) => set({ tasks, total: tasks.length }),
  updateTaskInStore: (taskId, updates) =>
    set((state) => ({
      tasks: state.tasks.map((t) => (t.task_id === taskId ? { ...t, ...updates } : t)),
    })),
  addTaskToStore: (task) =>
    set((state) => ({
      tasks: [...state.tasks, task],
      total: state.tasks.length + 1,
    })),
  removeTaskFromStore: (taskId) =>
    set((state) => ({
      tasks: state.tasks.filter((t) => t.task_id !== taskId),
      total: state.tasks.length - 1,
    })),
  setPendingItems: (pendingItems) => set({ pendingItems }),
  setRiskItems: (riskItems) => set({ riskItems }),
  setGranularityResult: (granularityResult) => set({ granularityResult }),
  setSelectedIndex: (selectedIndex) => set({ selectedIndex }),
  reset: () =>
    set({
      tasks: [],
      total: 0,
      pendingItems: [],
      riskItems: [],
      granularityResult: null,
      selectedIndex: -1,
    }),
}))
