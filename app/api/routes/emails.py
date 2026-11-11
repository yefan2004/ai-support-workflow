"""邮件任务接口。"""

from fastapi import APIRouter, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.deps import get_ai_provider
from app.db.models import EmailTask
from app.db.session import get_db
from app.providers.ai.base import AIProvider
from app.schemas.emails import (
    EmailTaskCreate,
    EmailTaskDetail,
    EmailTaskResponse,
    EmailTaskReviewRequest,
)
from app.services.email_tasks import register_email_task
from app.services.errors import (
    DatabaseOperationError,
    ProviderProcessingError,
    TaskNotFoundError,
    TaskStateConflictError,
)
from app.services.review import apply_review
from app.services.triage import process_email_task

router = APIRouter(prefix="/api/v1", tags=["emails"])


def _to_response(task: EmailTask, *, duplicate: bool) -> EmailTaskResponse:
    return EmailTaskResponse(
        id=task.id,
        mailbox_id=task.mailbox_id,
        message_id=task.message_id,
        subject=task.subject,
        body=task.body,
        status=task.status,
        duplicate=duplicate,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _to_detail(task: EmailTask) -> EmailTaskDetail:
    return EmailTaskDetail.model_validate(task)


@router.post(
    "/emails",
    response_model=EmailTaskResponse,
    status_code=status.HTTP_201_CREATED,
    summary="登记邮件任务（按 mailbox_id + message_id 去重）",
    responses={
        200: {"description": "重复提交，返回已存在的任务"},
        201: {"description": "首次提交，创建任务（status=received）"},
    },
)
def create_email_task(
    payload: EmailTaskCreate,
    response: Response,
    db: Session = Depends(get_db),
) -> EmailTaskResponse:
    """登记一封邮件。

    - 首次提交：创建任务，初始状态 ``received``，返回 201。
    - 相同 ``mailbox_id + message_id``：不新增记录，返回已有任务与
      ``duplicate=true``，返回 200。
    - 本接口不会调用 AI、不会发送任何邮件。
    """
    result = register_email_task(db, payload)
    if not result.created:
        response.status_code = status.HTTP_200_OK
    return _to_response(result.task, duplicate=not result.created)


@router.get(
    "/emails/{task_id}",
    response_model=EmailTaskDetail,
    summary="获取邮件任务详情",
    responses={
        404: {"description": "任务不存在"},
        503: {"description": "数据库操作失败"},
    },
)
def get_email_task(
    task_id: int,
    db: Session = Depends(get_db),
) -> EmailTaskDetail:
    """读取任务当前状态与分流/审核字段。"""
    try:
        task = db.get(EmailTask, task_id)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="数据库操作失败，请稍后重试",
        ) from exc

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"邮件任务 {task_id} 不存在",
        )
    return _to_detail(task)


@router.post(
    "/emails/{task_id}/process",
    response_model=EmailTaskDetail,
    summary="处理邮件任务（规则检查 + Mock AI 分流）",
    responses={
        404: {"description": "任务不存在"},
        409: {"description": "任务状态不允许处理"},
        500: {"description": "未预期内部错误"},
        502: {"description": "Provider 失败或输出无效，任务已标记 failed"},
        503: {"description": "数据库操作失败，状态可能不确定"},
    },
)
def process_email(
    task_id: int,
    db: Session = Depends(get_db),
    provider: AIProvider = Depends(get_ai_provider),
) -> EmailTaskDetail:
    """执行规则检查；规则未命中时调用 Mock Provider 并持久化结果。"""
    try:
        outcome = process_email_task(db, task_id, provider)
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except TaskStateConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except ProviderProcessingError as exc:
        content: dict[str, object] = {"detail": str(exc)}
        if exc.task is not None:
            content["task"] = EmailTaskDetail.model_validate(
                exc.task
            ).model_dump(mode="json")
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY, content=content
        )
    except DatabaseOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="处理过程中发生未预期错误",
        ) from exc

    return _to_detail(outcome.task)


@router.post(
    "/emails/{task_id}/review",
    response_model=EmailTaskDetail,
    summary="人工审核邮件任务",
    responses={
        404: {"description": "任务不存在"},
        409: {"description": "任务状态不允许审核，或 approve 时没有草稿"},
        422: {"description": "请求字段校验失败"},
        503: {"description": "数据库操作失败，状态可能不确定"},
    },
)
def review_email_task(
    task_id: int,
    payload: EmailTaskReviewRequest,
    db: Session = Depends(get_db),
) -> EmailTaskDetail:
    """approve / reject / takeover；approve 要求存在非空草稿。"""
    try:
        task = apply_review(
            db,
            task_id,
            payload.action,
            payload.reviewed_by,
            payload.review_comment,
        )
    except TaskNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except TaskStateConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except DatabaseOperationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="审核过程中发生未预期错误",
        ) from exc

    return _to_detail(task)
