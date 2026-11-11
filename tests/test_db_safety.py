"""测试数据库清理保护逻辑测试（不连接数据库）。"""

import pytest

from tests.db_safety import DatabaseSafetyError, ensure_test_database


def test_guard_rejects_non_test_database() -> None:
    with pytest.raises(DatabaseSafetyError, match="ai_support_test"):
        ensure_test_database("ai_support")


def test_guard_rejects_similar_database_name() -> None:
    with pytest.raises(DatabaseSafetyError):
        ensure_test_database("ai_support_test_backup")


def test_guard_allows_test_database() -> None:
    ensure_test_database("ai_support_test")
