"""健康检查接口。"""

from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(tags=["health"])


@router.get("/health", summary="健康检查")
def health() -> dict[str, str]:
    """返回服务运行状态。

    本阶段不检查数据库连通性，避免测试依赖外部服务；
    后续阶段可增加 /ready 就绪探针。
    """
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "version": settings.app_version,
        "environment": settings.app_env,
    }
