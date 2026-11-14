"""DeepSeek Provider 与 process API 的错误边界测试（真实测试数据库）。"""

import httpx
from fastapi.testclient import TestClient

from app.providers.ai.deepseek_provider import DeepSeekAIProvider
from tests.api_helpers import create_task, get_task

_TEST_KEY = "unit-test-deepseek-key"
_RESPONSE_MARKER = "raw-provider-body-marker"


def test_provider_failure_response_does_not_leak_key(
    api_client: TestClient,
    override_ai_provider,
) -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(
            500,
            json={
                "error": {
                    "message": f"{_RESPONSE_MARKER} {_TEST_KEY}",
                }
            },
        )

    provider = DeepSeekAIProvider(
        api_key=_TEST_KEY,
        base_url="https://api.deepseek.com",
        model="deepseek-flash",
        timeout_seconds=5.0,
        transport=httpx.MockTransport(handler),
    )
    override_ai_provider(provider)
    task_id = create_task(api_client)

    response = api_client.post(f"/api/v1/emails/{task_id}/process")

    assert response.status_code == 502
    assert _TEST_KEY not in response.text
    assert _RESPONSE_MARKER not in response.text
    assert calls == 1

    task = get_task(api_client, task_id)
    assert task["status"] == "failed"
    assert _TEST_KEY not in (task["failure_reason"] or "")
