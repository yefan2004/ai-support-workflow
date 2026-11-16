"""待审核列表接口的单元测试（不连接数据库）。"""

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.schemas.emails import EmailTaskReviewRequest


from tests.api_helpers import create_task
from tests.fakes import RecordingProvider, make_result


class _FakeDb:
    def scalars(self, statement):
        return self

    def all(self):
        return [
            SimpleNamespace(
                id=2,
                status="awaiting_review",
                summary="待审核摘要",
                risk_level="low",
            ),
            SimpleNamespace(
                id=1,
                status="approved",
                summary="已处理摘要",
                risk_level="medium",
            ),
        ]

    def rollback(self):
        pass


def test_list_emails_includes_database_task(api_client) -> None:
    task_id = create_task(api_client)

    response = api_client.get("/api/v1/emails")

    assert response.status_code == 200
    assert any(
        item["id"] == task_id and item["status"] == "received"
        for item in response.json()
    )


def test_approve_saves_edited_draft(
    api_client, override_ai_provider
) -> None:
    provider = RecordingProvider(
        result=make_result(draft_body="原始草稿")
    )
    override_ai_provider(provider)
    task_id = create_task(api_client)
    process_response = api_client.post(
        f"/api/v1/emails/{task_id}/process"
    )
    assert process_response.status_code == 200
    assert process_response.json()["status"] == "awaiting_review"

    response = api_client.post(
        f"/api/v1/emails/{task_id}/review",
        json={
            "action": "approve",
            "reviewed_by": "local-reviewer",
            "draft_body": "审核人编辑后的草稿",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["draft_body"] == "审核人编辑后的草稿"


def test_list_emails_returns_inbox_fields() -> None:
    app.dependency_overrides[get_db] = lambda: _FakeDb()
    try:
        with TestClient(app) as client:
            response = client.get("/api/v1/emails")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": 2,
            "status": "awaiting_review",
            "summary": "待审核摘要",
            "risk_level": "low",
        },
        {
            "id": 1,
            "status": "approved",
            "summary": "已处理摘要",
            "risk_level": "medium",
        },
    ]


def test_review_request_accepts_optional_edited_draft() -> None:
    request = EmailTaskReviewRequest(
        action="approve",
        reviewed_by="local-reviewer",
        draft_body="审核人编辑后的草稿",
    )

    assert request.draft_body == "审核人编辑后的草稿"
