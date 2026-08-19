"""
识别结果数据模型
"""
from pydantic import BaseModel, Field
from typing import Optional


class ContractRecognitionResult(BaseModel):
    """合同识别结果"""

    basic_info: list[dict] = Field(default_factory=list, description="项目基础信息")
    service_scope: list[dict] = Field(default_factory=list, description="合同约定的服务范围")
    client_responsibilities: list[dict] = Field(default_factory=list, description="客户责任和配合事项")
    our_responsibilities: list[dict] = Field(default_factory=list, description="我方责任和交付义务")
    delay_rules: list[dict] = Field(default_factory=list, description="暂停、延期和顺延规则")
    pending_items: list[dict] = Field(default_factory=list, description="待人工确认事项")
    raw_text: str = Field(default="", description="原始识别文本")
    source_file: str = Field(default="", description="来源文件名")


class PlanRecognitionResult(BaseModel):
    """年度服务计划识别结果"""

    service_modules: list[dict] = Field(default_factory=list, description="年度服务模块")
    milestones: list[dict] = Field(default_factory=list, description="阶段节点")
    client_data: list[dict] = Field(default_factory=list, description="客户资料和配合事项")
    meetings: list[dict] = Field(default_factory=list, description="会议和确认事项")
    pending_items: list[dict] = Field(default_factory=list, description="待人工确认事项")
    raw_text: str = Field(default="", description="原始识别文本")
    source_file: str = Field(default="", description="来源文件名")


class CrossValidationResult(BaseModel):
    """交叉核验结果"""

    consistent_items: list[dict] = Field(default_factory=list, description="一致事项")
    conflict_items: list[dict] = Field(default_factory=list, description="冲突事项")
    missing_items: list[dict] = Field(default_factory=list, description="缺失事项")
    summary: str = Field(default="", description="核验总结")


class RecognitionResponse(BaseModel):
    """识别响应"""

    success: bool = Field(default=True, description="是否成功")
    mode: str = Field(default="mock", description="运行模式: mock/real")
    data: Optional[dict] = Field(default=None, description="识别结果数据")
    message: str = Field(default="", description="消息")
