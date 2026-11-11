"""邮件任务的请求与响应模型。"""

import enum
from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

MailboxId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
MessageId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
ReviewerId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]


class EmailTaskCreate(BaseModel):
    """登记邮件任务的请求体。

    mailbox_id 与 message_id 为必填的唯一键；
    subject 与 body 可缺省（默认为空字符串），但不能为 null。
    """

    mailbox_id: MailboxId = Field(
        description="邮箱标识，例如 support@example.com",
        examples=["support@example.com"],
    )
    message_id: MessageId = Field(
        description="邮件 Message-ID，例如 <abc123@example.com>",
        examples=["<abc123@example.com>"],
    )
    subject: str = Field(default="", max_length=998, description="邮件主题")
    body: str = Field(default="", description="邮件正文（纯文本）")


class EmailTaskResponse(BaseModel):
    """邮件任务登记响应体。"""

    id: int
    mailbox_id: str
    message_id: str
    subject: str
    body: str
    status: str
    duplicate: bool = Field(
        description="true 表示命中 mailbox_id + message_id 已存在的任务，未新增记录"
    )
    created_at: datetime
    updated_at: datetime


class ReviewAction(str, enum.Enum):
    """人工审核动作。"""

    APPROVE = "approve"
    REJECT = "reject"
    TAKEOVER = "takeover"


class EmailTaskReviewRequest(BaseModel):
    """人工审核请求体。"""

    action: ReviewAction
    reviewed_by: ReviewerId = Field(
        description="审核人标识（演示值，由客户端自报，不代表真实身份）"
    )
    review_comment: str | None = Field(
        default=None, max_length=2000, description="审核备注（可选）"
    )


class EmailTaskDetail(BaseModel):
    """完整邮件任务详情。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    mailbox_id: str
    message_id: str
    subject: str
    body: str
    status: str
    category: str | None
    summary: str | None
    risk_level: str | None
    risk_reason: str | None
    draft_body: str | None
    requires_human: bool
    processed_at: datetime | None
    failure_reason: str | None
    review_action: str | None
    reviewed_by: str | None
    reviewed_at: datetime | None
    review_comment: str | None
    created_at: datetime
    updated_at: datetime
