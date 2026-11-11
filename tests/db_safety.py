"""测试数据库安全保护。

清理 fixture 在执行 TRUNCATE 前必须确认当前连接的是专用测试库，
避免误清空开发/演示数据库。
"""

TEST_DATABASE_NAME = "ai_support_test"


class DatabaseSafetyError(RuntimeError):
    """当前连接不是授权测试库时抛出。"""


def ensure_test_database(database_name: str) -> None:
    """仅允许对 ai_support_test 执行清理操作。"""
    if database_name != TEST_DATABASE_NAME:
        raise DatabaseSafetyError(
            "安全保护：当前连接的数据库是 "
            f"{database_name!r}，不是 {TEST_DATABASE_NAME!r}；"
            "已拒绝执行 TRUNCATE。请将 TEST_DATABASE_URL 指向独立测试库。"
        )
