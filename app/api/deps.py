"""FastAPI 依赖。"""

from app.config import get_settings
from app.providers.ai.base import AIProvider
from app.providers.ai.deepseek_provider import DeepSeekAIProvider
from app.providers.ai.mock_provider import MockAIProvider


def get_ai_provider() -> AIProvider:
    """按配置选择 AI Provider；默认 Mock，测试可覆盖此依赖。"""
    settings = get_settings()
    if settings.ai_provider == "deepseek":
        return DeepSeekAIProvider(
            api_key=settings.deepseek_api_key,
            base_url=settings.deepseek_base_url,
            model=settings.deepseek_model,
            timeout_seconds=settings.deepseek_timeout_seconds,
        )
    return MockAIProvider()
