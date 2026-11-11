"""API 测试辅助函数（仅用于测试数据库）。"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine


def create_task(
    api_client: TestClient,
    *,
    subject: str = "产品功能咨询",
    body: str = "请问产品功能？",
    mailbox_id: str = "process@example.com",
    message_id: str | None = None,
) -> int:
    message_id = message_id or f"<task-{uuid.uuid4().hex}@example.com>"
    response = api_client.post(
        "/api/v1/emails",
        json={
            "mailbox_id": mailbox_id,
            "message_id": message_id,
            "subject": subject,
            "body": body,
        },
    )
    assert response.status_code == 201
    return int(response.json()["id"])


def get_task(api_client: TestClient, task_id: int) -> dict:
    response = api_client.get(f"/api/v1/emails/{task_id}")
    assert response.status_code == 200
    return response.json()


def insert_awaiting_review(
    engine: Engine,
    *,
    draft_body: str | None,
    message_id: str | None = None,
) -> int:
    """构造异常/待审核记录，用于审核防御性测试。"""
    message_id = message_id or f"<awaiting-{uuid.uuid4().hex}@example.com>"
    with engine.begin() as connection:
        task_id = connection.execute(
            text(
                """
                INSERT INTO email_tasks
                    (mailbox_id, message_id, subject, body, status,
                     draft_body, requires_human, processed_at)
                VALUES
                    ('review@example.com', :message_id, '待审核任务', '正文',
                     'awaiting_review', :draft_body, true, now())
                RETURNING id
                """
            ),
            {"message_id": message_id, "draft_body": draft_body},
        ).scalar_one()
    return int(task_id)
