"""应用配置。

所有默认值均为本地演示配置，不包含任何真实密钥。
真实部署时应通过环境变量或 .env 覆盖，且不要把 .env 提交到仓库。
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """从环境变量 / .env 读取的配置。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "AI Support Workflow"
    app_env: str = "local"
    app_version: str = "0.1.0"

    # 本地 docker-compose 中 PostgreSQL 的默认连接串（仅演示，无真实密钥）。
    # 使用 psycopg 3 驱动；真实部署请通过环境变量 DATABASE_URL 覆盖。
    database_url: str = (
        "postgresql+psycopg://demo:demo@localhost:5432/ai_support"
    )


@lru_cache
def get_settings() -> Settings:
    """返回进程内缓存的配置实例。"""
    return Settings()
