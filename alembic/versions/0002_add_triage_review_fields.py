"""add triage and review fields to email_tasks

Revision ID: 0002_add_triage_review_fields
Revises: 0001_create_email_tasks
Create Date: 2026-11-11

只新增可空字段与 requires_human 默认值，不删除、不重建现有表。
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_add_triage_review_fields"
down_revision: str | None = "0001_create_email_tasks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "email_tasks", sa.Column("category", sa.String(length=64), nullable=True)
    )
    op.add_column("email_tasks", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column(
        "email_tasks", sa.Column("risk_level", sa.String(length=32), nullable=True)
    )
    op.add_column("email_tasks", sa.Column("risk_reason", sa.Text(), nullable=True))
    op.add_column("email_tasks", sa.Column("draft_body", sa.Text(), nullable=True))
    # NOT NULL + 常量默认值：PostgreSQL 会为已有记录回填 true。
    op.add_column(
        "email_tasks",
        sa.Column(
            "requires_human",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.add_column(
        "email_tasks",
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "email_tasks", sa.Column("failure_reason", sa.Text(), nullable=True)
    )
    op.add_column(
        "email_tasks", sa.Column("review_action", sa.String(length=32), nullable=True)
    )
    op.add_column(
        "email_tasks", sa.Column("reviewed_by", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "email_tasks",
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "email_tasks", sa.Column("review_comment", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("email_tasks", "review_comment")
    op.drop_column("email_tasks", "reviewed_at")
    op.drop_column("email_tasks", "reviewed_by")
    op.drop_column("email_tasks", "review_action")
    op.drop_column("email_tasks", "failure_reason")
    op.drop_column("email_tasks", "processed_at")
    op.drop_column("email_tasks", "requires_human")
    op.drop_column("email_tasks", "draft_body")
    op.drop_column("email_tasks", "risk_reason")
    op.drop_column("email_tasks", "risk_level")
    op.drop_column("email_tasks", "summary")
    op.drop_column("email_tasks", "category")
