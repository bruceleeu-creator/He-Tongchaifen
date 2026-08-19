/**
 * 步骤状态管理
 * 管理当前步骤(0-5)和已完成步骤集合
 * 使用 localStorage 手动持久化，防止页面刷新丢失步骤进度
 */
import { create } from 'zustand'

const STORAGE_KEY = 'psw-steps'

interface StepState {
  currentStep: number
  completedSteps: Set<number>
  setCurrentStep: (step: number) => void
  completeStep: (step: number) => void
  setCompletedSteps: (steps: number[]) => void
  reset: () => void
}

/** 从 localStorage 加载持久化状态 */
function loadPersistedSteps(): { currentStep: number; completedSteps: Set<number> } {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { currentStep: 0, completedSteps: new Set() }
    const parsed = JSON.parse(raw)
    return {
      currentStep: parsed.currentStep ?? 0,
      completedSteps: new Set(parsed.completedSteps ?? []),
    }
  } catch {
    return { currentStep: 0, completedSteps: new Set() }
  }
}

/** 保存状态到 localStorage */
function savePersistedSteps(currentStep: number, completedSteps: Set<number>) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      currentStep,
      completedSteps: Array.from(completedSteps),
    }))
  } catch {
    // localStorage 不可用时静默失败
  }
}

const persisted = loadPersistedSteps()

export const useStepStore = create<StepState>((set) => ({
  currentStep: persisted.currentStep,
  completedSteps: persisted.completedSteps,
  setCurrentStep: (currentStep) => {
    set({ currentStep })
    const s = useStepStore.getState()
    savePersistedSteps(s.currentStep, s.completedSteps)
  },
  completeStep: (step) =>
    set((state) => {
      const newSet = new Set(state.completedSteps)
      newSet.add(step)
      savePersistedSteps(state.currentStep, newSet)
      return { completedSteps: newSet }
    }),
  setCompletedSteps: (steps) => {
    const newSet = new Set(steps)
    set({ completedSteps: newSet })
    const s = useStepStore.getState()
    savePersistedSteps(s.currentStep, s.completedSteps)
  },
  reset: () => {
    set({ currentStep: 0, completedSteps: new Set<number>() })
    try { localStorage.removeItem(STORAGE_KEY) } catch { /* noop */ }
  },
}))
