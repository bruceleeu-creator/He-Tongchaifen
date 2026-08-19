/**
 * 文件拖拽上传组件
 */
import React from 'react'
import { Upload, Card, Select, Typography } from 'antd'
import { message } from '../../utils/messageBridge'
import { InboxOutlined, FileTextOutlined, CheckCircleOutlined } from '@ant-design/icons'
import type { UploadProps } from 'antd'

const { Dragger } = Upload
const { Text } = Typography

interface FileUploadCardProps {
  fileType: string
  onFileTypeChange: (value: string) => void
  onUploadSuccess: (result: any) => void
  uploadedFiles?: Array<{ name: string; type: string; status: string }>
}

const FileUploadCard: React.FC<FileUploadCardProps> = ({
  fileType,
  onFileTypeChange,
  onUploadSuccess,
  uploadedFiles = [],
}) => {
  const uploadProps: UploadProps = {
    name: 'file',
    multiple: false,
    accept: '.docx,.doc',
    action: '',
    beforeUpload: (file) => {
      const formData = new FormData()
      formData.append('file', file)
      formData.append('file_type', fileType)

      fetch('/api/upload/docx', {
        method: 'POST',
        body: formData,
      })
        .then((res) => res.json())
        .then((data) => {
          if (data.success) {
            message.success(`${file.name} 上传解析成功`)
            onUploadSuccess(data)
          } else {
            message.error(data.detail || '上传失败')
          }
        })
        .catch((err) => {
          message.error(`上传失败: ${err.message}`)
        })

      return false // 阻止 antd 默认上传行为
    },
  }

  return (
    <Card title="项目资料上传" variant="borderless">
      <div style={{ marginBottom: 16 }}>
        <Text strong style={{ marginRight: 12 }}>文件类型：</Text>
        <Select
          value={fileType}
          onChange={onFileTypeChange}
          style={{ width: 200 }}
          options={[
            { label: '合同', value: 'contract' },
            { label: '年度服务计划', value: 'plan' },
            { label: '启动会纪要', value: 'meeting_minutes' },
          ]}
        />
      </div>

      <Dragger {...uploadProps} style={{ padding: 8 }}>
        <p className="ant-upload-drag-icon">
          <InboxOutlined />
        </p>
        <p className="ant-upload-text">点击或拖拽文件到此区域上传</p>
        <p className="ant-upload-hint">
          支持 .docx / .doc 格式文件，单次上传一个文件
        </p>
      </Dragger>

      {uploadedFiles.length > 0 && (
        <div style={{ marginTop: 16 }}>
          <Text strong>已上传文件：</Text>
          {uploadedFiles.map((file, index) => (
            <div
              key={index}
              style={{
                display: 'flex',
                alignItems: 'center',
                padding: '8px 12px',
                marginTop: 8,
                background: '#f6ffed',
                borderRadius: 6,
                border: '1px solid #b7eb8f',
              }}
            >
              <FileTextOutlined style={{ color: '#52c41a', marginRight: 8 }} />
              <Text style={{ flex: 1 }}>{file.name}</Text>
              <Text type="secondary" style={{ marginRight: 12 }}>{file.type}</Text>
              <CheckCircleOutlined style={{ color: '#52c41a' }} />
              <Text type="success" style={{ marginLeft: 4 }}>{file.status}</Text>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}

export default FileUploadCard
