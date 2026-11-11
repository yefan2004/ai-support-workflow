"""POST /api/v1/emails/{id}/review 测试（真实 PostgreSQL）。"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine

from tests.api_helpers import (
    create_task,
    get_task,
    insert_awaiting_review,
)
from tests.fakes import RecordingProvider, make_result


def _create_awaiting_review(
    api_client: TestClient, override_ai_provider, *, draft_body: str = "草稿内容"
) -> int:
    provider = RecordingProvider(result=make_result(draft_body=draft_body))
    override_ai_provider(provider)
    task_id = create_task(api_client)
    response = api_client.post(f"/api/v1/emails/{task_id}/process")
    assert response.status_code == 200
    assert response.json()["status"] == "awaiting_review"
    return task_id


def _review(
    api_client: TestClient,
    task_id: int,
    action: str,
    *,
    reviewed_by: str = "agent@example.com",
    review_comment: str | None = "审核备注",
) -> object:
    return api_client.post(
        f"/api/v1/emails/{task_id}/review",
        json={
            "action": action,
            "reviewed_by": reviewed_by,
            "review_comment": review_comment,
        },
    )


def test_approve_with_draft_succeeds(
    api_client: TestClient, override_ai_provider
) -> None:
    task_id = _create_awaiting_review(api_client, override_ai_provider)

    response = _review(api_client, task_id, "approve")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "approved"
    assert payload["review_action"] == "approve"
    assert payload["reviewed_by"] == "agent@example.com"
    assert payload["reviewed_at"] is not None
    assert payload["review_comment"] == "审核备注"


@pytest.mark.parametrize(
    ("action", "expected_status"),
    [("reject", "rejected"), ("takeover", "human_takeover")],
)
def test_reject_and_takeover_succeed(
    api_client: TestClient,
    override_ai_provider,
    action: str,
    expected_status: str,
) -> None:
    task_id = _create_awaiting_review(api_client, override_ai_provider)

    response = _review(api_client, task_id, action)

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == expected_status
    assert payload["review_action"] == action


@pytest.mark.parametrize("draft_body", [None, "", "   ", " \n\t "])
def test_approve_without_draft_returns_409(
    api_client: TestClient,
    db_engine: Engine,
    draft_body: str | None,
) -> None:
    task_id = insert_awaiting_review(db_engine, draft_body=draft_body)

    response = _review(api_client, task_id, "approve")

    assert response.status_code == 409
    task = get_task(api_client, task_id)
    assert task["status"] == "awaiting_review"
    assert task["review_action"] is None
    assert task["reviewed_by"] is None


@pytest.mark.parametrize("action", ["reject", "takeover"])
def test_reject_or_takeover_allowed_for_blank_draft(
    api_client: TestClient,
    db_engine: Engine,
    action: str,
) -> None:
    task_id = insert_awaiting_review(db_engine, draft_body="   ")

    response = _review(api_client, task_id, action)

    assert response.status_code == 200
    task = get_task(api_client, task_id)
    assert task["review_action"] == action
    assert task["reviewed_by"] == "agent@example.com"
    assert task["status"] in {"rejected", "human_takeover"}


def test_review_wrong_status_returns_409(api_client: TestClient) -> None:
    task_id = create_task(api_client)

    response = _review(api_client, task_id, "approve")

    assert response.status_code == 409
    assert get_task(api_client, task_id)["status"] == "received"


def test_review_approved_task_again_returns_409(
    api_client: TestClient, override_ai_provider
) -> None:
    task_id = _create_awaiting_review(api_client, override_ai_provider)
    first = _review(api_client, task_id, "approve")
    assert first.status_code == 200

    second = _review(api_client, task_id, "reject")

    assert second.status_code == 409
    assert get_task(api_client, task_id)["status"] == "approved"


@pytest.mark.parametrize(
    "payload",
    [
        {"reviewed_by": "agent@example.com"},
        {"action": "unknown", "reviewed_by": "agent@example.com"},
        {"action": "approve"},
        {"action": "approve", "reviewed_by": "   "},
    ],
)
def test_review_invalid_payload_returns_422(
    api_client: TestClient, payload: dict
) -> None:
    task_id = create_task(api_client)

    response = api_client.post(
        f"/api/v1/emails/{task_id}/review", json=payload
    )

    assert response.status_code == 422


def test_review_missing_task_returns_404(api_client: TestClient) -> None:
    response = _review(api_client, 999999, "approve")

    assert response.status_code == 404
