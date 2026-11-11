"""GET /health 与根路径的基础测试。

本阶段测试完全不依赖 PostgreSQL 等外部服务，可在 CI 中直接运行。
"""

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app

client = TestClient(app)
settings = get_settings()


def test_health_returns_200_and_ok_status() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_contains_app_metadata() -> None:
    payload = client.get("/health").json()

    assert payload["app"] == settings.app_name
    assert payload["version"] == settings.app_version
    assert payload["environment"] == settings.app_env


def test_root_returns_app_info() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert response.json()["docs"] == "/docs"


def test_openapi_schema_contains_health_route() -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health" in response.json()["paths"]
