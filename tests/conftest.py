"""pytest 共享 fixture。

数据库测试使用真实 PostgreSQL（优先 TEST_DATABASE_URL）。
清理 fixture 带有安全保护：只有当前数据库名为 ai_support_test 时才允许
TRUNCATE，防止误清空开发/演示数据库。数据库不可用时相关测试会跳过；
数据库可用但未执行迁移时，测试会失败并提示先运行迁移。
"""

import os
from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker

from app.api.deps import get_ai_provider
from app.config import get_settings
from app.db.session import get_db
from app.main import app
from app.providers.ai.base import AIProvider
from tests.db_safety import DatabaseSafetyError, ensure_test_database


def _database_url() -> str:
    return os.getenv("TEST_DATABASE_URL") or get_settings().database_url


def _ensure_test_database_or_exit(connection) -> None:
    """在任何数据库查询/写入前确认库名为 ai_support_test。"""
    database_name = connection.execute(
        text("SELECT current_database()")
    ).scalar_one()
    try:
        ensure_test_database(str(database_name))
    except DatabaseSafetyError as exc:
        pytest.exit(str(exc), returncode=1)


@pytest.fixture(scope="session")
def db_engine() -> Generator[Engine, None, None]:
    """创建测试引擎；数据库不可用时跳过依赖它的测试。"""
    engine = create_engine(_database_url(), pool_pre_ping=True)

    try:
        with engine.connect() as connection:
            _ensure_test_database_or_exit(connection)
            connection.execute(text("SELECT 1"))
            email_tasks_table = connection.execute(
                text("SELECT to_regclass('public.email_tasks')")
            ).scalar_one_or_none()
    except OperationalError as exc:
        engine.dispose()
        pytest.skip(f"PostgreSQL 不可用，跳过数据库集成测试：{exc.orig}")

    if email_tasks_table is None:
        engine.dispose()
        pytest.fail("未找到 email_tasks 表，请先执行 `alembic upgrade head`")

    yield engine
    engine.dispose()


@pytest.fixture()
def clean_db(db_engine: Engine) -> Generator[None, None, None]:
    """每个用例前后清空 email_tasks，保证互不干扰。

    安全保护：TRUNCATE 之前读取 current_database()，不是 ai_support_test
    就立即终止会话，绝不执行清理。
    """

    def truncate() -> None:
        with db_engine.begin() as connection:
            _ensure_test_database_or_exit(connection)
            connection.execute(text("TRUNCATE TABLE email_tasks RESTART IDENTITY"))

    truncate()
    yield
    truncate()


@pytest.fixture()
def override_ai_provider() -> Generator[Callable[[AIProvider], None], None, None]:
    """在测试中覆盖 get_ai_provider 依赖。"""

    def _override(provider: AIProvider) -> None:
        app.dependency_overrides[get_ai_provider] = lambda: provider

    yield _override
    app.dependency_overrides.pop(get_ai_provider, None)


@pytest.fixture()
def api_client(
    db_engine: Engine, clean_db: None
) -> Generator[TestClient, None, None]:
    """覆盖 get_db，使 API 使用测试数据库会话。"""
    testing_session_factory = sessionmaker(
        bind=db_engine, autoflush=False, expire_on_commit=False
    )

    def override_get_db() -> Generator[Session, None, None]:
        db = testing_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.pop(get_db, None)
