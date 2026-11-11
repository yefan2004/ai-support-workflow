"""email_tasks 表结构与迁移结果测试。

需要连接已执行迁移的测试库（ai_support_test）。
"""

from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.engine import Engine

# 字段名: (是否可空, information_schema 数据类型, 最大字符长度)
EXPECTED_NEW_COLUMNS = {
    "category": ("YES", "character varying", 64),
    "summary": ("YES", "text", None),
    "risk_level": ("YES", "character varying", 32),
    "risk_reason": ("YES", "text", None),
    "draft_body": ("YES", "text", None),
    "requires_human": ("NO", "boolean", None),
    "processed_at": ("YES", "timestamp with time zone", None),
    "failure_reason": ("YES", "text", None),
    "review_action": ("YES", "character varying", 32),
    "reviewed_by": ("YES", "character varying", 255),
    "reviewed_at": ("YES", "timestamp with time zone", None),
    "review_comment": ("YES", "text", None),
}

NULLABLE_NEW_FIELDS = [
    "category",
    "summary",
    "risk_level",
    "risk_reason",
    "draft_body",
    "processed_at",
    "failure_reason",
    "review_action",
    "reviewed_by",
    "reviewed_at",
    "review_comment",
]


def _table_columns(engine: Engine) -> dict[str, dict]:
    with engine.connect() as connection:
        rows = connection.execute(
            text(
                """
                SELECT column_name, is_nullable, data_type,
                       character_maximum_length, column_default
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'email_tasks'
                """
            )
        ).mappings().all()
    return {str(row["column_name"]): dict(row) for row in rows}


def test_new_columns_exist_with_expected_types(
    db_engine: Engine, clean_db: None
) -> None:
    columns = _table_columns(db_engine)

    for name, (nullable, data_type, max_length) in EXPECTED_NEW_COLUMNS.items():
        assert name in columns, f"缺少字段 {name}"
        assert columns[name]["is_nullable"] == nullable
        assert columns[name]["data_type"] == data_type
        assert columns[name]["character_maximum_length"] == max_length

    requires_human_default = str(columns["requires_human"]["column_default"]).lower()
    assert "true" in requires_human_default


def test_existing_unique_constraint_still_exists(
    db_engine: Engine, clean_db: None
) -> None:
    with db_engine.connect() as connection:
        constraint_names = connection.execute(
            text(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'public.email_tasks'::regclass
                  AND contype = 'u'
                """
            )
        ).scalars().all()

    assert "uq_email_tasks_mailbox_id_message_id" in constraint_names


def test_database_default_for_requires_human_is_true(
    db_engine: Engine, clean_db: None
) -> None:
    with db_engine.begin() as connection:
        row = connection.execute(
            text(
                """
                INSERT INTO email_tasks
                    (mailbox_id, message_id, subject, body, status)
                VALUES
                    ('schema@example.com', '<schema-default@example.com>', '', '',
                     'received')
                RETURNING requires_human, category, summary, risk_level,
                          risk_reason, draft_body, processed_at, failure_reason,
                          review_action, reviewed_by, reviewed_at, review_comment
                """
            )
        ).mappings().one()

    assert row["requires_human"] is True
    for field in NULLABLE_NEW_FIELDS:
        assert row[field] is None


def test_api_created_task_requires_human_defaults_true(
    api_client: TestClient, db_engine: Engine
) -> None:
    response = api_client.post(
        "/api/v1/emails",
        json={
            "mailbox_id": "schema@example.com",
            "message_id": "<schema-api@example.com>",
            "subject": "schema 测试",
            "body": "验证 requires_human 默认值",
        },
    )

    assert response.status_code == 201
    task_id = response.json()["id"]

    with db_engine.connect() as connection:
        requires_human = connection.execute(
            text("SELECT requires_human FROM email_tasks WHERE id = :task_id"),
            {"task_id": task_id},
        ).scalar_one()

    assert requires_human is True
