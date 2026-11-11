"""FastAPI 应用入口。

演示项目：AI 辅助客服邮件分流与人工审核。
本阶段仅提供健康检查接口，业务模块为后续阶段的占位。
"""

from fastapi import FastAPI

from app.api.routes import health
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


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    """返回应用基础信息，方便快速确认服务已启动。"""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }
