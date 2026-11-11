"""服务层数据库辅助函数。"""

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db.models import EmailTask
from app.services.errors import DatabaseOperationError


def reload_task(db: Session, task_id: int) -> EmailTask | None:
    """重新读取任务；数据库异常转为 DatabaseOperationError。"""
    try:
        return db.scalar(select(EmailTask).where(EmailTask.id == task_id))
    except SQLAlchemyError as exc:
        raise DatabaseOperationError() from exc


def safe_current_status(db: Session, task_id: int) -> str | None:
    """尽力查询当前状态；查询失败返回 None，不掩盖原错误。"""
    try:
        return db.scalar(
            select(EmailTask.status).where(EmailTask.id == task_id)
        )
    except SQLAlchemyError:
        return None
