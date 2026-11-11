"""邮件任务状态与允许的状态转换。

集中定义状态值，避免后续业务代码散落字符串。
本阶段仅在 Python 层校验状态；数据库 status 列仍是普通字符串，
直接写库可以绕过校验（已知限制）。
"""

import enum
from typing import Final


class EmailTaskStatus(str, enum.Enum):
    """邮件任务状态。"""

    RECEIVED = "received"
    PROCESSING = "processing"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    HUMAN_TAKEOVER = "human_takeover"
    FAILED = "failed"


class InvalidEmailTaskTransitionError(ValueError):
    """非法的邮件任务状态转换。"""


ALLOWED_TRANSITIONS: Final[dict[EmailTaskStatus, frozenset[EmailTaskStatus]]] = {
    EmailTaskStatus.RECEIVED: frozenset({EmailTaskStatus.PROCESSING}),
    EmailTaskStatus.PROCESSING: frozenset(
        {
            EmailTaskStatus.AWAITING_REVIEW,
            EmailTaskStatus.HUMAN_TAKEOVER,
            EmailTaskStatus.FAILED,
        }
    ),
    EmailTaskStatus.AWAITING_REVIEW: frozenset(
        {
            EmailTaskStatus.APPROVED,
            EmailTaskStatus.REJECTED,
            EmailTaskStatus.HUMAN_TAKEOVER,
        }
    ),
    EmailTaskStatus.APPROVED: frozenset(),
    EmailTaskStatus.REJECTED: frozenset(),
    EmailTaskStatus.HUMAN_TAKEOVER: frozenset(),
    EmailTaskStatus.FAILED: frozenset(),
}


def is_transition_allowed(
    current: EmailTaskStatus, target: EmailTaskStatus
) -> bool:
    """返回 current -> target 是否为允许的状态转换。"""
    return target in ALLOWED_TRANSITIONS.get(current, frozenset())


def validate_transition(
    current: EmailTaskStatus, target: EmailTaskStatus
) -> None:
    """校验状态转换；非法时抛出 InvalidEmailTaskTransitionError。"""
    if not is_transition_allowed(current, target):
        raise InvalidEmailTaskTransitionError(
            f"不允许的状态转换：{current.value} -> {target.value}"
        )
