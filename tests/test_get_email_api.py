"""GET /api/v1/emails/{id} 测试（真实 PostgreSQL）。"""

from fastapi.testclient import TestClient

from tests.api_helpers import create_task, get_task
from tests.fakes import RecordingProvider, make_result


def test_get_email_task_returns_full_detail(api_client: TestClient) -> None:
    task_id = create_task(
        api_client,
        subject="产品咨询",
        body="请问产品价格？",
    )

    task = get_task(api_client, task_id)

    assert task["id"] == task_id
    assert task["status"] == "received"
    assert task["category"] is None
    assert task["summary"] is None
    assert task["risk_level"] is None
    assert task["risk_reason"] is None
    assert task["draft_body"] is None
    assert task["requires_human"] is True
    assert task["processed_at"] is None
    assert task["failure_reason"] is None
    assert task["review_action"] is None
    assert task["reviewed_by"] is None
    assert task["reviewed_at"] is None
    assert task["review_comment"] is None


def test_get_email_task_after_process(
    api_client: TestClient, override_ai_provider
) -> None:
    provider = RecordingProvider(result=make_result())
    override_ai_provider(provider)
    task_id = create_task(api_client)
    process_response = api_client.post(
        f"/api/v1/emails/{task_id}/process"
    )
    assert process_response.status_code == 200

    task = get_task(api_client, task_id)

    assert task["status"] == "awaiting_review"
    assert task["category"] == "product_question"
    assert task["draft_body"] == "您好，这是测试草稿。"
    assert task["processed_at"] is not None


def test_get_email_task_missing_returns_404(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/emails/999999")

    assert response.status_code == 404
