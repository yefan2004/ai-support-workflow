"""邮件任务的请求与响应模型。"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, Field, StringConstraints

MailboxId = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=255)
]
MessageId = Annotated[
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
    """邮件任务响应体。"""

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
