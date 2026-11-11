"""邮件任务接口。"""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.db.models import EmailTask
from app.db.session import get_db
from app.schemas.emails import EmailTaskCreate, EmailTaskResponse
from app.services.email_tasks import register_email_task

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
