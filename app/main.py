"""FastAPI 应用入口。

演示项目：AI 辅助客服邮件分流与人工审核。
本阶段提供健康检查与邮件任务登记（含数据库去重）接口；
AI 分流、审核与发送等模块仍为后续阶段占位。
"""

from fastapi import FastAPI

from app.api.routes import emails, health
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "演示项目：AI 辅助客服邮件分流与人工审核"
        "（FastAPI + PostgreSQL + n8n）。"
        "仅用于本地演示，不可直接用于生产环境。"
    ),
)

app.include_router(health.router)
app.include_router(emails.router)


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    """返回应用基础信息，方便快速确认服务已启动。"""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }
