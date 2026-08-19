/**
 * App 根组件
 * 使用 react-router-dom v6 配置路由
 * MainLayout 包裹所有页面
 */
import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import MainLayout from './components/Layout/MainLayout'
import UploadPage from './pages/Upload'
import RecognitionPage from './pages/Recognition'
import ClarificationPage from './pages/Clarification'
import TaskReviewPage from './pages/TaskReview'
import VersionHistoryPage from './pages/VersionHistory'
import ExportPage from './pages/Export'

const App: React.FC = () => {
  return (
    <Routes>
      <Route path="/" element={<MainLayout />}>
        <Route index element={<Navigate to="/upload" replace />} />
        <Route path="upload" element={<UploadPage />} />
        <Route path="recognition" element={<RecognitionPage />} />
        <Route path="clarification" element={<ClarificationPage />} />
        <Route path="task-review" element={<TaskReviewPage />} />
        <Route path="version-history" element={<VersionHistoryPage />} />
        <Route path="export" element={<ExportPage />} />
        <Route path="*" element={<Navigate to="/upload" replace />} />
      </Route>
    </Routes>
  )
}

export default App
