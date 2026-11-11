"""process 的 Provider 错误、404 与终态冲突测试（真实 PostgreSQL）。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

from app.providers.ai.base import AIProviderTimeoutError
from tests.api_helpers import create_task, get_task
from tests.fakes import InvalidOutputProvider, RecordingProvider


def test_provider_timeout_marks_failed(
    api_client: TestClient, override_ai_provider
) -> None:
    provider = RecordingProvider(error=AIProviderTimeoutError("timeout"))
    override_ai_provider(provider)
    task_id = create_task(api_client)

    response = api_client.post(f"/api/v1/emails/{task_id}/process")

    assert response.status_code == 502
    assert "AIProviderTimeoutError" in response.json()["detail"]
    task = get_task(api_client, task_id)
    assert task["status"] == "failed"
    assert task["processed_at"] is not None
    assert "AIProviderTimeoutError" in task["failure_reason"]
    assert "请问产品功能" not in task["failure_reason"]


def test_provider_invalid_output_marks_failed(
    api_client: TestClient, override_ai_provider
) -> None:
    override_ai_provider(InvalidOutputProvider())
    task_id = create_task(api_client)

    response = api_client.post(f"/api/v1/emails/{task_id}/process")

    assert response.status_code == 502
    task = get_task(api_client, task_id)
    assert task["status"] == "failed"
    assert "ValidationError" in task["failure_reason"]


def test_unexpected_provider_error_returns_500_not_failed(
    api_client: TestClient, override_ai_provider
) -> None:
    provider = RecordingProvider(error=RuntimeError("unexpected bug"))
    override_ai_provider(provider)
    task_id = create_task(api_client)

    response = api_client.post(f"/api/v1/emails/{task_id}/process")

    assert response.status_code == 500
    task = get_task(api_client, task_id)
    assert task["status"] == "processing"
    assert task["failure_reason"] is None


def test_process_missing_task_returns_404(api_client: TestClient) -> None:
    response = api_client.post("/api/v1/emails/999999/process")

    assert response.status_code == 404


@pytest.mark.parametrize(
    "terminal_status",
    ["approved", "rejected", "human_takeover", "failed"],
)
def test_process_terminal_status_returns_409(
    api_client: TestClient,
    db_engine: Engine,
    terminal_status: str,
) -> None:
    task_id = create_task(api_client)
    with db_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE email_tasks SET status=:status, updated_at=now() "
                "WHERE id=:task_id"
            ),
            {"status": terminal_status, "task_id": task_id},
        )

    response = api_client.post(f"/api/v1/emails/{task_id}/process")

    assert response.status_code == 409
    assert get_task(api_client, task_id)["status"] == terminal_status
