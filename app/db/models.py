"""SQLAlchemy ORM 模型。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text, UniqueConstraint, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.core.email_status import EmailTaskStatus
from app.db.base import Base


class EmailTask(Base):
    """邮件任务。

    同一邮箱（mailbox_id）下以 message_id 唯一标识一封邮件，
    数据库唯一约束负责并发场景下的最终去重。
    """

    __tablename__ = "email_tasks"
    __table_args__ = (
        UniqueConstraint(
            "mailbox_id",
            "message_id",
            name="uq_email_tasks_mailbox_id_message_id",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    mailbox_id: Mapped[str] = mapped_column(String(255), nullable=False)
    message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(998), nullable=False, default="")
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=EmailTaskStatus.RECEIVED.value,
        server_default=EmailTaskStatus.RECEIVED.value,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # --- 分流结果（后续阶段写入，本阶段仅建字段）---
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str | None] = mapped_column(String(32), nullable=True)
    risk_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    draft_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    requires_human: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- 人工审核（后续阶段写入，本阶段仅建字段）---
    review_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
