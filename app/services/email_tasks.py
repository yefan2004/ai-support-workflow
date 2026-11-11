"""邮件任务登记与去重服务。"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import EmailTask, EmailTaskStatus
from app.schemas.emails import EmailTaskCreate


@dataclass(frozen=True)
class RegistrationResult:
    """登记结果：task 为新建或已存在的任务，created 表示本次是否新增。"""

    task: EmailTask
    created: bool


def register_email_task(db: Session, payload: EmailTaskCreate) -> RegistrationResult:
    """登记邮件任务；按 mailbox_id + message_id 去重。

    先查询以减少无谓写入；若并发请求同时通过查询，
    数据库唯一约束会让其中一个插入失败，此时回滚并返回已提交的记录。
    """
    stmt = select(EmailTask).where(
        EmailTask.mailbox_id == payload.mailbox_id,
        EmailTask.message_id == payload.message_id,
    )

    existing = db.scalar(stmt)
    if existing is not None:
        return RegistrationResult(task=existing, created=False)

    task = EmailTask(
        mailbox_id=payload.mailbox_id,
        message_id=payload.message_id,
        subject=payload.subject,
        body=payload.body,
        status=EmailTaskStatus.RECEIVED.value,
    )
    db.add(task)

    try:
        db.commit()
    except IntegrityError:
        # 并发插入时唯一约束冲突：回滚后读取胜出的那条记录。
        db.rollback()
        existing = db.scalar(stmt)
        if existing is None:
            # 不是可解析为重复提交的约束冲突，按原错误上报。
            raise
        return RegistrationResult(task=existing, created=False)

    db.refresh(task)
    return RegistrationResult(task=task, created=True)
