"""
澄清表单数据模型
"""
from pydantic import BaseModel, Field
from typing import Optional


class ClarificationItem(BaseModel):
    """单条待确认事项"""

    item_id: str = Field(default="", description="事项ID")
    pending_item: str = Field(default="", description="待确认事项")
    related_tasks: str = Field(default="", description="涉及任务")
    reason: str = Field(default="", description="原因")
    suggest_confirm_to: str = Field(default="", description="建议向谁确认")
    impact_if_not_confirmed: str = Field(default="", description="不确认的影响")
    status: str = Field(default="待确认", description="状态: 待确认/已确认/已忽略")
    confirmed_value: str = Field(default="", description="确认后的值")


class ClarificationForm(BaseModel):
    """澄清表单"""

    form_id: str = Field(default="", description="表单ID")
    run_id: str = Field(default="", description="运行ID")
    items: list[ClarificationItem] = Field(default_factory=list, description="待确认事项列表")
    created_at: str = Field(default="", description="创建时间")
    updated_at: str = Field(default="", description="更新时间")


class ClarificationSubmitItem(BaseModel):
    """提交澄清项"""

    item_id: str = Field(..., description="事项ID")
    status: str = Field(..., description="状态: 已确认/已忽略")
    confirmed_value: str = Field(default="", description="确认后的值")


class ClarificationSubmitRequest(BaseModel):
    """提交澄清表单请求"""

    items: list[ClarificationSubmitItem] = Field(..., description="提交的事项列表")
