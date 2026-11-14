"""AI Provider 配置选择测试（不访问网络/数据库）。"""

import pytest
from pydantic import ValidationError

from app.api.deps import get_ai_provider
from app.config import Settings, get_settings
from app.providers.ai.deepseek_provider import DeepSeekAIProvider
from app.providers.ai.mock_provider import MockAIProvider


@pytest.fixture(autouse=True)
def _clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_default_settings_provider_is_mock(monkeypatch) -> None:
    monkeypatch.delenv("AI_PROVIDER", raising=False)

    settings = Settings(_env_file=None)

    assert settings.ai_provider == "mock"


def test_default_get_ai_provider_returns_mock(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "mock")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    get_settings.cache_clear()

    provider = get_ai_provider()

    assert isinstance(provider, MockAIProvider)


def test_deepseek_provider_can_be_selected(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "deepseek")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "unit-test-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    monkeypatch.setenv("DEEPSEEK_MODEL", "deepseek-flash")
    monkeypatch.setenv("DEEPSEEK_TIMEOUT_SECONDS", "12.5")
    get_settings.cache_clear()

    provider = get_ai_provider()

    assert isinstance(provider, DeepSeekAIProvider)


def test_provider_name_is_case_insensitive(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "DEEPSEEK")
    monkeypatch.setenv("DEEPSEEK_API_KEY", "unit-test-key")

    settings = Settings(_env_file=None)

    assert settings.ai_provider == "deepseek"


def test_deepseek_requires_api_key(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "deepseek")
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    with pytest.raises(ValidationError, match="DEEPSEEK_API_KEY"):
        Settings(_env_file=None)


def test_unsupported_provider_is_rejected(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER", "unsupported")

    with pytest.raises(ValidationError):
        Settings(_env_file=None)


@pytest.mark.parametrize(
    "overrides",
    [
        {"deepseek_base_url": "api.deepseek.com"},
        {"deepseek_timeout_seconds": 0},
        {"deepseek_model": "   "},
    ],
)
def test_invalid_deepseek_config_is_rejected(
    overrides: dict[str, object],
) -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            ai_provider="deepseek",
            deepseek_api_key="unit-test-key",
            **overrides,
        )


def test_api_key_is_masked_in_settings_repr() -> None:
    settings = Settings(
        _env_file=None,
        ai_provider="deepseek",
        deepseek_api_key="unit-test-secret-key",
    )

    assert "unit-test-secret-key" not in repr(settings)
    assert "unit-test-secret-key" not in str(settings)
