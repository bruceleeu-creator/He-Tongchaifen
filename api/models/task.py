"""
任务数据模型 - 18字段定义
中文字段名 -> 英文key 的映射在 config.py 中定义
"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TaskBase(BaseModel):
    """任务基础模型 - 18字段"""

    # 1. 客户名称
    customer_name: str = Field(default="", description="客户名称")
    # 2. 项目名称
    project_name: str = Field(default="", description="项目名称")
    # 3. 任务名称
    task_name: str = Field(default="", description="任务名称")
    # 4. 服务模块
    service_module: str = Field(default="", description="服务模块")
    # 5. 任务类型
    task_type: str = Field(default="", description="任务类型")
    # 6. 计划开始时间
    plan_start_date: str = Field(default="", description="计划开始时间")
    # 7. 计划完成时间
    plan_end_date: str = Field(default="", description="计划完成时间")
    # 8. 我方负责人
    our_owner: str = Field(default="", description="我方负责人")
    # 9. 客户责任人
    client_contact: str = Field(default="", description="客户责任人")
    # 10. 客户需提供的资料或配合事项
    client_requirements: str = Field(default="", description="客户需提供的资料或配合事项")
    # 11. 当前状态
    current_status: str = Field(default="未开始", description="当前状态")
    # 12. 延期责任归属
    delay_responsibility: str = Field(default="无延期", description="延期责任归属")
    # 13. 节点目标/达到效果
    milestone_goal: str = Field(default="", description="节点目标/达到效果")
    # 14. 下一步动作及承诺完成时间
    next_action: str = Field(default="", description="下一步动作及承诺完成时间")
    # 15. 交付成果或完成凭证
    deliverables: str = Field(default="", description="交付成果或完成凭证")
    # 16. AI定制交付成果说明
    ai_deliverable_desc: str = Field(default="", description="AI定制交付成果说明")
    # 17. AI提取依据
    ai_extraction_basis: str = Field(default="", description="AI提取依据")
    # 18. 人工复核状态
    review_status: str = Field(default="待复核", description="人工复核状态")


class TaskCreate(TaskBase):
    """创建任务请求模型"""
    pass


class TaskUpdate(BaseModel):
    """更新任务请求模型 - 所有字段可选"""

    customer_name: Optional[str] = None
    project_name: Optional[str] = None
    task_name: Optional[str] = None
    service_module: Optional[str] = None
    task_type: Optional[str] = None
    plan_start_date: Optional[str] = None
    plan_end_date: Optional[str] = None
    our_owner: Optional[str] = None
    client_contact: Optional[str] = None
    client_requirements: Optional[str] = None
    current_status: Optional[str] = None
    delay_responsibility: Optional[str] = None
    milestone_goal: Optional[str] = None
    next_action: Optional[str] = None
    deliverables: Optional[str] = None
    ai_deliverable_desc: Optional[str] = None
    ai_extraction_basis: Optional[str] = None
    review_status: Optional[str] = None


class Task(TaskBase):
    """完整任务模型（含系统字段）"""

    task_id: str = Field(default="", description="任务ID")
    created_at: str = Field(default="", description="创建时间")
    updated_at: str = Field(default="", description="更新时间")


class TaskListResponse(BaseModel):
    """任务列表响应"""

    total: int = Field(default=0, description="任务总数")
    tasks: list[Task] = Field(default_factory=list, description="任务列表")


class GranularityCheckResult(BaseModel):
    """颗粒度检查结果"""

    need_split: list[dict] = Field(default_factory=list, description="需要继续拆分的任务")
    missing_fields: list[dict] = Field(default_factory=list, description="缺少关键字段的任务")
    client_data_issues: list[dict] = Field(default_factory=list, description="客户资料未独立成行")
    deliverable_issues: list[dict] = Field(default_factory=list, description="交付成果不明确")
    summary: str = Field(default="", description="检查总结")
