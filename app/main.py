"""FastAPI 应用入口。

演示项目：AI 辅助客服邮件分流与人工审核。
提供健康检查、邮件登记、AI 分流与人工审核接口；
AI Provider 默认使用离线 Mock，可通过配置启用 DeepSeek。
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse

from app.api.routes import ai, emails, health
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
# AI 路由只在注册处加一次 /api/v1；router 自身不带前缀。
app.include_router(ai.router, prefix="/api/v1")

_UI_PAGE = Path(__file__).resolve().parent / "static" / "review.html"


@app.get("/ui", include_in_schema=False)
def review_ui() -> FileResponse:
    """返回同源的人工审核单页。"""
    return FileResponse(_UI_PAGE, media_type="text/html")


@app.get("/", tags=["meta"])
def root() -> dict[str, str]:
    """返回应用基础信息，方便快速确认服务已启动。"""
    return {
        "app": settings.app_name,
        "version": settings.app_version,
        "docs": "/docs",
    }
