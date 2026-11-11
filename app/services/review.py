"""人工审核状态更新。

审核通过必须同时满足：
- 任务状态为 awaiting_review；
- draft_body 非 NULL 且去除空白后非空。

reject / takeover 对异常的无草稿记录仍然允许，便于人工处理异常数据。
"""

from sqlalchemy import func, select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.email_status import EmailTaskStatus, validate_transition
from app.db.models import EmailTask
from app.schemas.emails import ReviewAction
from app.services.db_utils import reload_task, safe_current_status
from app.services.errors import (
    DatabaseOperationError,
    TaskNotFoundError,
    TaskStateConflictError,
)

_TARGET_STATUS = {
    ReviewAction.APPROVE: EmailTaskStatus.APPROVED,
    ReviewAction.REJECT: EmailTaskStatus.REJECTED,
    ReviewAction.TAKEOVER: EmailTaskStatus.HUMAN_TAKEOVER,
}


def apply_review(
    db: Session,
    task_id: int,
    action: ReviewAction,
    reviewed_by: str,
    review_comment: str | None,
) -> EmailTask:
    """执行审核动作；approve 额外要求非空草稿。"""
    target_status = _TARGET_STATUS[action]
    validate_transition(EmailTaskStatus.AWAITING_REVIEW, target_status)

    conditions = [
        EmailTask.id == task_id,
        EmailTask.status == EmailTaskStatus.AWAITING_REVIEW.value,
    ]
    if action is ReviewAction.APPROVE:
        conditions.extend(
            [
                EmailTask.draft_body.is_not(None),
                func.regexp_replace(
                    EmailTask.draft_body, r"\s", "", "g"
                )
                != "",
            ]
        )

    comment = review_comment.strip() if review_comment else None
    try:
        statement = (
            update(EmailTask)
            .where(*conditions)
            .values(
                status=target_status.value,
                review_action=action.value,
                reviewed_by=reviewed_by,
                reviewed_at=func.now(),
                review_comment=comment,
                updated_at=func.now(),
            )
            .returning(EmailTask)
        )
        task = db.execute(statement).scalar_one_or_none()
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseOperationError(
            safe_current_status(db, task_id)
        ) from exc

    if task is None:
        db.rollback()
        current = reload_task(db, task_id)
        if current is None:
            raise TaskNotFoundError(task_id)
        if current.status != EmailTaskStatus.AWAITING_REVIEW.value:
            raise TaskStateConflictError(
                current.status,
                f"任务当前状态为 {current.status}，不能执行审核",
            )
        if action is ReviewAction.APPROVE:
            raise TaskStateConflictError(
                current.status, "任务没有可审核的草稿，不能批准"
            )
        raise TaskStateConflictError(
            current.status, "审核未生效，请刷新任务状态后重试"
        )

    try:
        db.commit()
        db.refresh(task)
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseOperationError(
            safe_current_status(db, task_id)
        ) from exc

    return task
