"""邮件任务状态与转换规则测试（不依赖数据库）。"""

import pytest

from app.core.email_status import (
    ALLOWED_TRANSITIONS,
    EmailTaskStatus,
    InvalidEmailTaskTransitionError,
    is_transition_allowed,
    validate_transition,
)

VALID_TRANSITIONS = [
    (EmailTaskStatus.RECEIVED, EmailTaskStatus.PROCESSING),
    (EmailTaskStatus.PROCESSING, EmailTaskStatus.AWAITING_REVIEW),
    (EmailTaskStatus.PROCESSING, EmailTaskStatus.HUMAN_TAKEOVER),
    (EmailTaskStatus.PROCESSING, EmailTaskStatus.FAILED),
    (EmailTaskStatus.AWAITING_REVIEW, EmailTaskStatus.APPROVED),
    (EmailTaskStatus.AWAITING_REVIEW, EmailTaskStatus.REJECTED),
    (EmailTaskStatus.AWAITING_REVIEW, EmailTaskStatus.HUMAN_TAKEOVER),
]

INVALID_TRANSITIONS = [
    (current, target)
    for current in EmailTaskStatus
    for target in EmailTaskStatus
    if (current, target) not in VALID_TRANSITIONS
]


@pytest.mark.parametrize(("current", "target"), VALID_TRANSITIONS)
def test_allowed_transition_passes_validation(
    current: EmailTaskStatus, target: EmailTaskStatus
) -> None:
    assert is_transition_allowed(current, target) is True
    validate_transition(current, target)  # 不应抛出异常


@pytest.mark.parametrize(("current", "target"), INVALID_TRANSITIONS)
def test_invalid_transition_is_rejected(
    current: EmailTaskStatus, target: EmailTaskStatus
) -> None:
    assert is_transition_allowed(current, target) is False
    with pytest.raises(InvalidEmailTaskTransitionError):
        validate_transition(current, target)


def test_status_values_match_specification() -> None:
    values = {status.value for status in EmailTaskStatus}

    assert values == {
        "received",
        "processing",
        "awaiting_review",
        "approved",
        "rejected",
        "human_takeover",
        "failed",
    }
    # 本阶段未实现发送功能，不应出现 sent / sending 状态
    assert "sent" not in values
    assert "sending" not in values


def test_transition_table_matches_specification() -> None:
    expected = {
        EmailTaskStatus.RECEIVED: {EmailTaskStatus.PROCESSING},
        EmailTaskStatus.PROCESSING: {
            EmailTaskStatus.AWAITING_REVIEW,
            EmailTaskStatus.HUMAN_TAKEOVER,
            EmailTaskStatus.FAILED,
        },
        EmailTaskStatus.AWAITING_REVIEW: {
            EmailTaskStatus.APPROVED,
            EmailTaskStatus.REJECTED,
            EmailTaskStatus.HUMAN_TAKEOVER,
        },
        EmailTaskStatus.APPROVED: set(),
        EmailTaskStatus.REJECTED: set(),
        EmailTaskStatus.HUMAN_TAKEOVER: set(),
        EmailTaskStatus.FAILED: set(),
    }

    assert {
        status: set(targets) for status, targets in ALLOWED_TRANSITIONS.items()
    } == expected


def test_invalid_transition_error_is_value_error() -> None:
    assert issubclass(InvalidEmailTaskTransitionError, ValueError)
