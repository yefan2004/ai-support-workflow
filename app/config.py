"""应用配置。

默认使用离线 Mock AI Provider；只有显式设置 AI_PROVIDER=deepseek
并提供 API Key 时才会启用外部模型。不要在仓库中保存真实密钥。
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator, model_validator
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

    # --- AI Provider ---
    # 默认 mock：离线、确定性，不调用外部 API。
    ai_provider: Literal["mock", "deepseek"] = "mock"
    deepseek_api_key: SecretStr | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_model: str = "deepseek-flash"
    deepseek_timeout_seconds: float = Field(default=30.0, gt=0, le=120)

    @field_validator("ai_provider", mode="before")
    @classmethod
    def _normalize_ai_provider(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip().lower()
        return value

    @field_validator("deepseek_base_url")
    @classmethod
    def _normalize_deepseek_base_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        if not normalized:
            raise ValueError("DEEPSEEK_BASE_URL 不能为空")
        if not normalized.startswith(("http://", "https://")):
            raise ValueError(
                "DEEPSEEK_BASE_URL 必须以 http:// 或 https:// 开头"
            )
        return normalized

    @field_validator("deepseek_model")
    @classmethod
    def _normalize_deepseek_model(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("DEEPSEEK_MODEL 不能为空")
        return normalized

    @model_validator(mode="after")
    def _validate_deepseek_config(self) -> "Settings":
        if self.ai_provider == "deepseek":
            api_key = (
                self.deepseek_api_key.get_secret_value().strip()
                if self.deepseek_api_key is not None
                else ""
            )
            if not api_key:
                raise ValueError(
                    "AI_PROVIDER=deepseek 时必须设置 DEEPSEEK_API_KEY"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """返回进程内缓存的配置实例。"""
    return Settings()
