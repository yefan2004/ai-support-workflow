"""邮件任务处理编排：规则检查 → Mock AI → 结果持久化。

处理流程只通过条件 UPDATE 认领和写回状态：
- 认领：WHERE status='received'；
- 写回：WHERE status='processing'。

调用规则/Provider 时不持有数据库行锁。未预期编程错误不会被伪装成
Provider 故障；数据库异常会回滚并报告状态可能不确定。
"""

from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy import func, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.email_status import EmailTaskStatus
from app.core.triage_types import AllowedCategory, RiskLevel
from app.db.models import EmailTask
from app.providers.ai.base import AIProvider, AIProviderError, ClassificationResult
from app.services.db_utils import reload_task, safe_current_status
from app.services.errors import (
    DatabaseOperationError,
    ProviderProcessingError,
    TaskNotFoundError,
    TaskStateConflictError,
)
from app.services.rules import evaluate_rules

_IMMEDIATE_HANDOFF_CATEGORIES = frozenset(
    {AllowedCategory.REFUND_REQUEST, AllowedCategory.COMPLAINT}
)


@dataclass(frozen=True)
class ProcessOutcome:
    """process 结果。"""

    task: EmailTask
    reused_existing: bool = False


def _claim_task(
    db: Session, task_id: int
) -> tuple[EmailTask | None, EmailTask | None]:
    """原子认领任务；返回 (claim 成功的任务, 已存在任务)。

    仅 received 可以认领；已 awaiting_review 的任务直接返回现有结果，
    其他状态由调用方转换为 409。
    """
    try:
        statement = (
            update(EmailTask)
            .where(
                EmailTask.id == task_id,
                EmailTask.status == EmailTaskStatus.RECEIVED.value,
            )
            .values(
                status=EmailTaskStatus.PROCESSING.value,
                failure_reason=None,
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
        if current.status == EmailTaskStatus.AWAITING_REVIEW.value:
            return None, current
        if current.status == EmailTaskStatus.PROCESSING.value:
            raise TaskStateConflictError(
                current.status, "任务正在处理中，不能重复处理"
            )
        raise TaskStateConflictError(
            current.status, f"任务当前状态为 {current.status}，不能重复处理"
        )

    try:
        db.commit()
        db.refresh(task)
    except SQLAlchemyError as exc:
        db.rollback()
        raise DatabaseOperationError(
            safe_current_status(db, task_id)
        ) from exc

    return task, None


def _finalize(
    db: Session,
    task_id: int,
    target_status: EmailTaskStatus,
    values: dict[str, object],
) -> EmailTask:
    """以 processing 为前提写回最终状态；未命中不得视为成功。"""
    final_values: dict[str, object] = {
        **values,
        "status": target_status.value,
        "processed_at": func.now(),
        "updated_at": func.now(),
    }

    try:
        statement = (
            update(EmailTask)
            .where(
                EmailTask.id == task_id,
                EmailTask.status == EmailTaskStatus.PROCESSING.value,
            )
            .values(**final_values)
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
        raise TaskStateConflictError(
            current.status, "任务状态已变化，处理结果未保存"
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


def _failure_reason(prefix: str, exc: BaseException) -> str:
    """只记录安全的错误类别，不保存正文、密钥或堆栈。"""
    return f"{prefix}：{type(exc).__name__}"[:500]


def _rule_handoff_values(
    category: AllowedCategory | None,
    risk_level: RiskLevel | None,
    risk_reason: str,
) -> dict[str, object]:
    return {
        "category": category.value if category is not None else None,
        "summary": None,
        "risk_level": risk_level.value if risk_level is not None else None,
        "risk_reason": risk_reason,
        "draft_body": None,
        "requires_human": True,
        "failure_reason": None,
    }


def _classification_values(
    classification: ClassificationResult,
    *,
    draft_body: str | None,
    risk_reason: str | None = None,
) -> dict[str, object]:
    return {
        "category": classification.category.value,
        "summary": classification.summary,
        "risk_level": classification.risk_level.value,
        "risk_reason": (
            risk_reason
            if risk_reason is not None
            else classification.risk_reason
        ),
        "draft_body": draft_body,
        "requires_human": True,
        "failure_reason": None,
    }


def _failed_values(reason: str) -> dict[str, object]:
    return {
        "category": None,
        "summary": None,
        "risk_level": None,
        "risk_reason": None,
        "draft_body": None,
        "requires_human": True,
        "failure_reason": reason,
    }


def process_email_task(
    db: Session, task_id: int, provider: AIProvider
) -> ProcessOutcome:
    """执行规则检查与 Mock AI 分流，并持久化最终状态。"""
    task, existing = _claim_task(db, task_id)
    if existing is not None:
        return ProcessOutcome(task=existing, reused_existing=True)

    assert task is not None

    rule_result = evaluate_rules(task.subject, task.body)
    if rule_result.requires_immediate_handoff:
        final_task = _finalize(
            db,
            task_id,
            EmailTaskStatus.HUMAN_TAKEOVER,
            _rule_handoff_values(
                rule_result.suggested_category,
                rule_result.risk_level,
                rule_result.risk_reason,
            ),
        )
        return ProcessOutcome(task=final_task)

    try:
        raw_result = provider.classify(task.subject, task.body)
        classification = ClassificationResult.model_validate(raw_result)
    except (AIProviderError, ValidationError) as exc:
        reason = _failure_reason("AI Provider 调用或输出校验失败", exc)
        failed_task = _finalize(
            db,
            task_id,
            EmailTaskStatus.FAILED,
            _failed_values(reason),
        )
        raise ProviderProcessingError(
            f"AI Provider 处理失败（{type(exc).__name__}），任务已标记 failed",
            task=failed_task,
        ) from exc

    draft_body = classification.draft_body
    has_usable_draft = draft_body is not None and bool(draft_body.strip())

    if (
        classification.risk_level is RiskLevel.HIGH
        or classification.category in _IMMEDIATE_HANDOFF_CATEGORIES
    ):
        final_task = _finalize(
            db,
            task_id,
            EmailTaskStatus.HUMAN_TAKEOVER,
            _classification_values(classification, draft_body=None),
        )
        return ProcessOutcome(task=final_task)

    if not has_usable_draft:
        handoff_reason = "Provider 未生成可审核草稿，需立即转人工处理。"
        existing_reason = classification.risk_reason.strip()
        risk_reason = (
            f"{existing_reason}；{handoff_reason}"
            if existing_reason
            else handoff_reason
        )
        final_task = _finalize(
            db,
            task_id,
            EmailTaskStatus.HUMAN_TAKEOVER,
            _classification_values(
                classification,
                draft_body=None,
                risk_reason=risk_reason,
            ),
        )
        return ProcessOutcome(task=final_task)

    final_task = _finalize(
        db,
        task_id,
        EmailTaskStatus.AWAITING_REVIEW,
        _classification_values(classification, draft_body=draft_body),
    )
    return ProcessOutcome(task=final_task)
