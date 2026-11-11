"""数据库引擎与会话。

连接串通过环境变量 DATABASE_URL（或 .env）提供，不提交真实密钥。
"""

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

settings = get_settings()

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI 依赖：为每个请求提供独立 Session。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
