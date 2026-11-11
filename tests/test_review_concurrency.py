"""review 并发测试（真实 PostgreSQL）。"""

import threading
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import app
from tests.api_helpers import create_task, get_task
from tests.fakes import RecordingProvider, make_result


def _create_awaiting_review(
    api_client: TestClient, override_ai_provider
) -> int:
    provider = RecordingProvider(result=make_result())
    override_ai_provider(provider)
    task_id = create_task(api_client)
    response = api_client.post(f"/api/v1/emails/{task_id}/process")
    assert response.status_code == 200
    assert response.json()["status"] == "awaiting_review"
    return task_id


def test_concurrent_reviews_only_one_succeeds(
    api_client: TestClient, override_ai_provider
) -> None:
    task_id = _create_awaiting_review(api_client, override_ai_provider)
    barrier = threading.Barrier(2)

    def submit(action: str, reviewed_by: str) -> int:
        barrier.wait(timeout=10)
        with TestClient(app) as client:
            response = client.post(
                f"/api/v1/emails/{task_id}/review",
                json={
                    "action": action,
                    "reviewed_by": reviewed_by,
                    "review_comment": f"由 {reviewed_by} 提交",
                },
            )
        return response.status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(submit, "approve", "approver@example.com"),
            executor.submit(submit, "reject", "rejecter@example.com"),
        ]
        statuses = sorted(future.result() for future in futures)

    assert statuses == [200, 409]

    task = get_task(api_client, task_id)
    mapping = {"approve": "approved", "reject": "rejected"}
    assert task["review_action"] in mapping
    assert task["status"] == mapping[task["review_action"]]
    assert task["reviewed_by"] in {
        "approver@example.com",
        "rejecter@example.com",
    }
    assert task["reviewed_at"] is not None
