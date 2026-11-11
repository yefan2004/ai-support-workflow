"""FastAPI 依赖。"""

from app.providers.ai.base import AIProvider
from app.providers.ai.mock_provider import MockAIProvider


def get_ai_provider() -> AIProvider:
    """返回默认的离线 Mock Provider；测试可覆盖此依赖。"""
    return MockAIProvider()
