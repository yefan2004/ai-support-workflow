"""SQLAlchemy ORM 模型。"""

import enum
from datetime import datetime

from sqlalchemy import DateTime, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class EmailTaskStatus(str, enum.Enum):
    """邮件任务状态。

    本阶段仅使用 received；其余状态为后续阶段（分流/审核/发送）预留。
    """

    RECEIVED = "received"


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
