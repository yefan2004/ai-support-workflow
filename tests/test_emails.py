"""POST /api/v1/emails 的接口与数据库测试。

数据库测试依赖真实 PostgreSQL；若连接不可用，相关用例会被跳过。
并发用例使用真实线程同时发起 HTTP 请求，验证数据库唯一约束下的去重行为。
"""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from app.main import app
from app.schemas.emails import EmailTaskCreate
from app.services.email_tasks import register_email_task

VALID_PAYLOAD = {
    "mailbox_id": "support@example.com",
    "message_id": "<message-001@example.com>",
    "subject": "无法登录账号",
    "body": "你好，我的账号无法登录，请协助处理。",
}


def _count_tasks(engine: Engine) -> int:
    with engine.connect() as connection:
        return int(
            connection.execute(text("SELECT count(*) FROM email_tasks")).scalar_one()
        )


def test_create_email_task_returns_201_and_received(
    api_client: TestClient, db_engine: Engine
) -> None:
    response = api_client.post("/api/v1/emails", json=VALID_PAYLOAD)

    assert response.status_code == 201
    payload = response.json()
    assert payload["duplicate"] is False
    assert payload["status"] == "received"
    assert payload["mailbox_id"] == VALID_PAYLOAD["mailbox_id"]
    assert payload["message_id"] == VALID_PAYLOAD["message_id"]
    assert payload["subject"] == VALID_PAYLOAD["subject"]
    assert payload["body"] == VALID_PAYLOAD["body"]
    assert payload["id"] > 0
    assert payload["created_at"] == payload["updated_at"]
    assert _count_tasks(db_engine) == 1


def test_duplicate_submission_returns_existing_task(
    api_client: TestClient, db_engine: Engine
) -> None:
    first = api_client.post("/api/v1/emails", json=VALID_PAYLOAD)
    second = api_client.post("/api/v1/emails", json=VALID_PAYLOAD)

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["duplicate"] is True
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["status"] == "received"
    assert _count_tasks(db_engine) == 1


def test_same_message_id_in_different_mailbox_creates_new_task(
    api_client: TestClient, db_engine: Engine
) -> None:
    first_payload = {**VALID_PAYLOAD, "mailbox_id": "support@example.com"}
    second_payload = {**VALID_PAYLOAD, "mailbox_id": "sales@example.com"}

    first = api_client.post("/api/v1/emails", json=first_payload)
    second = api_client.post("/api/v1/emails", json=second_payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert second.json()["duplicate"] is False
    assert second.json()["id"] != first.json()["id"]
    assert _count_tasks(db_engine) == 2


@pytest.mark.parametrize("field", ["mailbox_id", "message_id"])
def test_missing_required_field_returns_422(
    api_client: TestClient, field: str
) -> None:
    payload = VALID_PAYLOAD.copy()
    payload.pop(field)

    response = api_client.post("/api/v1/emails", json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize("field", ["mailbox_id", "message_id"])
def test_blank_required_field_returns_422(
    api_client: TestClient, field: str
) -> None:
    payload = {**VALID_PAYLOAD, field: "   "}

    response = api_client.post("/api/v1/emails", json=payload)

    assert response.status_code == 422


def test_unique_constraint_rejects_duplicate_rows(
    db_engine: Engine, clean_db: None
) -> None:
    """绕过 API 直接写库，验证数据库层唯一约束确实存在。"""
    insert_sql = text(
        "INSERT INTO email_tasks (mailbox_id, message_id, subject, body, status) "
        "VALUES (:mailbox_id, :message_id, :subject, :body, 'received')"
    )
    params = {
        "mailbox_id": VALID_PAYLOAD["mailbox_id"],
        "message_id": VALID_PAYLOAD["message_id"],
        "subject": VALID_PAYLOAD["subject"],
        "body": VALID_PAYLOAD["body"],
    }

    with db_engine.begin() as connection:
        connection.execute(insert_sql, params)

    with pytest.raises(IntegrityError):
        with db_engine.begin() as connection:
            connection.execute(insert_sql, params)

    assert _count_tasks(db_engine) == 1


def test_register_email_task_recovers_from_unique_violation(
    db_engine: Engine, clean_db: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """确定性模拟并发冲突：预检查通过后，竞争请求抢先插入。

    在服务提交前用另一连接插入相同唯一键，使 ORM 提交必然触发
    IntegrityError；服务应回滚并返回已存在的记录，而不是报错。
    """
    testing_session_factory = sessionmaker(
        bind=db_engine, autoflush=False, expire_on_commit=False
    )
    session = testing_session_factory()
    payload = EmailTaskCreate(**VALID_PAYLOAD)
    original_commit = session.commit

    def commit_after_competing_insert() -> None:
        with db_engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO email_tasks "
                    "(mailbox_id, message_id, subject, body, status) "
                    "VALUES (:mailbox_id, :message_id, :subject, :body, 'received')"
                ),
                {
                    "mailbox_id": payload.mailbox_id,
                    "message_id": payload.message_id,
                    "subject": payload.subject,
                    "body": payload.body,
                },
            )
        original_commit()

    monkeypatch.setattr(session, "commit", commit_after_competing_insert)
    try:
        result = register_email_task(session, payload)
    finally:
        session.close()

    assert result.created is False
    assert result.task.mailbox_id == payload.mailbox_id
    assert _count_tasks(db_engine) == 1


def test_concurrent_duplicate_submissions_create_one_task(
    api_client: TestClient, db_engine: Engine
) -> None:
    """真实并发：8 个线程同时提交相同的 mailbox_id + message_id。"""
    worker_count = 8
    barrier = threading.Barrier(worker_count)

    def submit() -> tuple[int, dict]:
        barrier.wait(timeout=10)
        # 每个线程使用独立 TestClient，避免共享客户端状态。
        with TestClient(app) as thread_client:
            response = thread_client.post("/api/v1/emails", json=VALID_PAYLOAD)
        return response.status_code, response.json()

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = [executor.submit(submit) for _ in range(worker_count)]
        results = [future.result() for future in futures]

    statuses = [status_code for status_code, _ in results]
    assert statuses.count(201) == 1
    assert statuses.count(200) == worker_count - 1

    task_ids = {body["id"] for _, body in results}
    assert len(task_ids) == 1
    assert _count_tasks(db_engine) == 1
