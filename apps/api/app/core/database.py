from typing import Generator
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.engine import Engine

from app.core.config import settings

# 建立 SQLAlchemy Engine
engine = create_engine(
    settings.sqlite_url,
    connect_args={"check_same_thread": False},
    echo=False,
    future=True,
)


@event.listens_for(Engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """
    配置 SQLite 連線 PRAGMA:
    1. 啟用外鍵約束 (Foreign Keys Enforcement)
    2. 啟用 WAL (Write-Ahead Logging) 提升並行讀寫效率
    3. 設定 synchronous = FULL 確保財務交易耐久性
    4. 設定 busy_timeout 防止寫入競爭鎖定超時
    """
    cursor = dbapi_connection.cursor()
    cursor.execute(f"PRAGMA journal_mode = {settings.SQLITE_JOURNAL_MODE};")
    cursor.execute("PRAGMA foreign_keys = ON;")
    cursor.execute(f"PRAGMA synchronous = {settings.SQLITE_SYNCHRONOUS};")
    cursor.execute(f"PRAGMA busy_timeout = {settings.SQLITE_BUSY_TIMEOUT_MS};")
    cursor.close()


SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    expire_on_commit=False,
    future=True,
)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """資料庫 Session 依賴注入 (Database Session Dependency)"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
