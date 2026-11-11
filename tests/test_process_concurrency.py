"""process 重复请求、并发认领与事务边界测试（真实 PostgreSQL）。"""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from app.db.session import get_db
from app.main import app
from tests.api_helpers import create_task, get_task
from tests.fakes import RecordingProvider, make_result


def test_repeated_process_awaiting_review_returns_existing(
    api_client: TestClient, override_ai_provider
) -> None:
    provider = RecordingProvider(result=make_result())
    override_ai_provider(provider)
    task_id = create_task(api_client)

    first = api_client.post(f"/api/v1/emails/{task_id}/process")
    second = api_client.post(f"/api/v1/emails/{task_id}/process")

    assert first.status_code == 200
    assert second.status_code == 200
    for field in ("id", "status", "category", "summary", "draft_body"):
        assert second.json()[field] == first.json()[field]
    assert second.json()["status"] == "awaiting_review"
    assert provider.calls == 1


def test_processing_task_rejects_second_process(
    api_client: TestClient, override_ai_provider
) -> None:
    started = threading.Event()
    release = threading.Event()

    def on_classify() -> None:
        started.set()
        assert release.wait(timeout=10)

    provider = RecordingProvider(
        result=make_result(), on_classify=on_classify
    )
    override_ai_provider(provider)
    task_id = create_task(api_client)

    def first_request() -> int:
        with TestClient(app) as client:
            return client.post(
                f"/api/v1/emails/{task_id}/process"
            ).status_code

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(first_request)
        assert started.wait(timeout=10)

        second = api_client.post(f"/api/v1/emails/{task_id}/process")
        assert second.status_code == 409

        release.set()
        first_status = future.result()

    assert first_status == 200
    assert provider.calls == 1
    assert get_task(api_client, task_id)["status"] == "awaiting_review"


def test_final_update_conflict_does_not_report_success(
    api_client: TestClient, override_ai_provider, db_engine: Engine
) -> None:
    task_id = create_task(api_client)

    def change_status_externally() -> None:
        with db_engine.begin() as connection:
            connection.execute(
                text(
                    "UPDATE email_tasks "
                    "SET status='human_takeover', updated_at=now() "
                    "WHERE id=:task_id"
                ),
                {"task_id": task_id},
            )

    provider = RecordingProvider(
        result=make_result(),
        on_classify=change_status_externally,
    )
    override_ai_provider(provider)

    response = api_client.post(f"/api/v1/emails/{task_id}/process")

    assert response.status_code == 409
    task = get_task(api_client, task_id)
    assert task["status"] == "human_takeover"
    assert task["category"] is None
    assert task["summary"] is None
    assert task["draft_body"] is None
    assert provider.calls == 1


def test_claim_commit_failure_returns_503_with_uncertainty(
    api_client: TestClient, db_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_id = create_task(api_client)
    testing_session_factory = sessionmaker(
        bind=db_engine, autoflush=False, expire_on_commit=False
    )
    broken_session = testing_session_factory()

    def fail_commit() -> None:
        raise OperationalError(
            "commit", {}, Exception("database connection lost")
        )

    monkeypatch.setattr(broken_session, "commit", fail_commit)

    def override_get_db():
        try:
            yield broken_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = api_client.post(f"/api/v1/emails/{task_id}/process")
    finally:
        broken_session.close()

    assert response.status_code == 503
    assert "可能不确定" in response.json()["detail"]
    # 不在此断言任务状态一定未改变：提交确认阶段中断时状态可能未知。


def test_final_commit_failure_returns_503_without_success(
    api_client: TestClient, db_engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    task_id = create_task(api_client)
    testing_session_factory = sessionmaker(
        bind=db_engine, autoflush=False, expire_on_commit=False
    )
    session = testing_session_factory()
    original_commit = session.commit
    commit_calls = {"count": 0}

    def fail_second_commit() -> None:
        commit_calls["count"] += 1
        if commit_calls["count"] == 2:
            raise OperationalError(
                "commit", {}, Exception("commit acknowledgement lost")
            )
        original_commit()

    monkeypatch.setattr(session, "commit", fail_second_commit)

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    try:
        response = api_client.post(f"/api/v1/emails/{task_id}/process")
    finally:
        session.close()

    assert response.status_code == 503
    assert "可能不确定" in response.json()["detail"]
