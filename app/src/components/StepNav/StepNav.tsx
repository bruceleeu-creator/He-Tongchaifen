/**
 * 步骤导航条组件
 */
import React from 'react'
import { Steps } from 'antd'
import { STEPS } from '../../utils/constants'
import { useStepStore } from '../../stores/stepStore'
import { useNavigate } from 'react-router-dom'

const StepNav: React.FC = () => {
  const { currentStep, completedSteps } = useStepStore()
  const navigate = useNavigate()

  const handleClick = (path: string, index: number) => {
    navigate(path)
    useStepStore.getState().setCurrentStep(index)
  }

  return (
    <div className="step-nav-container">
      <Steps
        current={currentStep}
        size="small"
        items={STEPS.map((step, index) => ({
          title: step.title,
          description: step.description,
          status:
            completedSteps.has(index) && index < currentStep
              ? 'finish'
              : index === currentStep
                ? 'process'
                : 'wait',
        }))}
      />
    </div>
  )
}

export default StepNav
