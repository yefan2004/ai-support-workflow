"""服务层领域异常。"""

from typing import Any


class ServiceError(Exception):
    """服务层基础异常。"""


class TaskNotFoundError(ServiceError):
    """邮件任务不存在。"""

    def __init__(self, task_id: int) -> None:
        self.task_id = task_id
        super().__init__(f"邮件任务 {task_id} 不存在")


class TaskStateConflictError(ServiceError):
    """任务当前状态不允许执行该操作。"""

    def __init__(
        self, current_status: str | None, message: str | None = None
    ) -> None:
        self.current_status = current_status
        if message is None:
            message = f"任务当前状态为 {current_status}，不能执行该操作"
        super().__init__(message)


class DatabaseOperationError(ServiceError):
    """数据库操作失败；任务状态可能不确定，不能声称未改变。"""

    def __init__(self, current_status: str | None = None) -> None:
        self.current_status = current_status
        message = "数据库操作失败，任务状态可能不确定，请重新查询任务状态"
        if current_status is not None:
            message += f"（最近查询到：{current_status}）"
        super().__init__(message)


class ProviderProcessingError(ServiceError):
    """Provider 预期错误或输出无效；任务已标记 failed。"""

    def __init__(self, message: str, task: Any | None = None) -> None:
        self.task = task
        super().__init__(message)
