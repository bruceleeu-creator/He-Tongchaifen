"""
版本管理数据模型
"""
from pydantic import BaseModel, Field
from typing import Optional


class VersionInfo(BaseModel):
    """版本信息"""

    version_id: str = Field(default="", description="版本ID")
    run_id: str = Field(default="", description="运行ID")
    version_number: int = Field(default=1, description="版本号")
    description: str = Field(default="", description="版本描述")
    task_count: int = Field(default=0, description="任务数量")
    created_at: str = Field(default="", description="创建时间")
    created_by: str = Field(default="system", description="创建者")
    snapshot: Optional[dict] = Field(default=None, description="任务快照")


class VersionListResponse(BaseModel):
    """版本列表响应"""

    total: int = Field(default=0, description="版本总数")
    versions: list[VersionInfo] = Field(default_factory=list, description="版本列表")


class VersionSaveRequest(BaseModel):
    """保存版本请求"""

    description: str = Field(default="", description="版本描述")
