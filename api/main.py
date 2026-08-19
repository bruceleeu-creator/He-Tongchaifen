"""
年度财税顾问项目拆分工作台 - FastAPI 应用入口
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import upload, recognition, clarification, task, review, version, export
from routers import ai_config, pipeline, deliverable
from services.ai_config_store import ai_config_store

# 创建 FastAPI 应用
app = FastAPI(
    title="年度财税顾问项目拆分工作台 API",
    description="""
    ## 项目说明

    年度财税顾问项目拆分工作台后端 API。

    ### 核心功能

    1. **文件上传与解析** - 上传 Word 合同和年度服务计划，自动解析
    2. **AI 识别服务** - 合同识别、计划识别、交叉核验
    3. **任务拆分** - AI 自动拆分任务主表
    4. **澄清表单** - 生成待人工确认事项清单
    5. **复核服务** - 颗粒度检查、待确认清单、风险提示
    6. **版本管理** - 保存版本、回退
    7. **导出服务** - CSV / Markdown 导出

    ### 运行模式

    - **mock 模式**（默认）: 使用预设 JSON 数据，无需 LLM API Key
    - **real 模式**: 配置 LLM_API_KEY 后切换为真实 LLM 调用

    ### 18 字段标准

    客户名称 | 项目名称 | 任务名称 | 服务模块 | 任务类型 | 计划开始时间 | 计划完成时间 |
    我方负责人 | 客户责任人 | 客户需提供的资料或配合事项 | 当前状态 | 延期责任归属 |
    节点目标/达到效果 | 下一步动作及承诺完成时间 | 交付成果或完成凭证 |
    AI定制交付成果说明 | AI提取依据 | 人工复核状态
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(upload.router)
app.include_router(recognition.router)
app.include_router(clarification.router)
app.include_router(task.router)
app.include_router(review.router)
app.include_router(version.router)
app.include_router(export.router)
app.include_router(ai_config.router)
app.include_router(pipeline.router)
app.include_router(deliverable.router)


@app.get("/")
async def root():
    """根路径 - 应用信息"""
    return {
        "name": "年度财税顾问项目拆分工作台 API",
        "version": "1.0.0",
        "mode": settings.parser_mode,
        "mode_label": settings.run_mode_label,
        "llm_available": ai_config_store.is_available,
        "docs": "/docs",
        "endpoints": {
            "上传与解析": "/api/upload",
            "识别服务": "/api/recognition",
            "澄清表单": "/api/clarification",
            "任务管理": "/api/tasks",
            "复核服务": "/api/review",
            "版本管理": "/api/versions",
            "导出服务": "/api/export",
            "AI配置": "/api/ai-config",
            "全流程自动化": "/api/pipeline",
        },
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {
        "status": "ok",
        "mode": settings.parser_mode,
        "mode_label": settings.run_mode_label,
        "llm_available": ai_config_store.is_available,
        "llm_model": ai_config_store.model if ai_config_store.is_available else "",
    }


@app.get("/api/field-options")
async def get_field_options():
    """获取字段选项标准（全局接口）"""
    return {
        "success": True,
        "field_options": settings.FIELD_OPTIONS,
        "field_mapping": settings.FIELD_MAPPING,
        "field_names_cn": settings.FIELD_NAMES_CN,
        "field_names_en": settings.FIELD_NAMES_EN,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_DEBUG,
    )
