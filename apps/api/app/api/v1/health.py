import sqlite3
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.database import get_db

router = APIRouter(tags=["Health"])


@router.get("/health", status_code=status.HTTP_200_OK)
def check_health(db: Session = Depends(get_db)):
    """
    健康檢查端點 (Health Check Endpoint)
    驗證 API 服務可用性及 SQLite 資料庫連線狀態。
    """
    db_status = "healthy"
    sqlite_version = sqlite3.sqlite_version
    
    try:
        # 實測資料庫讀取
        result = db.execute(text("SELECT 1")).scalar()
        if result != 1:
            db_status = "unhealthy"
    except Exception as exc:
        db_status = f"unhealthy: {str(exc)}"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "database": {
            "status": db_status,
            "engine": "SQLite",
            "sqlite_version": sqlite_version,
        },
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/ready", status_code=status.HTTP_200_OK)
def check_ready(db: Session = Depends(get_db)):
    """
    就緒性檢查端點 (Readiness Check Endpoint)
    檢查 WAL 日誌模式、Foreign Keys 啟用狀態與系統資料庫讀寫就緒。
    """
    journal_mode = db.execute(text("PRAGMA journal_mode;")).scalar()
    fk_enabled = db.execute(text("PRAGMA foreign_keys;")).scalar()
    busy_timeout = db.execute(text("PRAGMA busy_timeout;")).scalar()

    is_ready = (str(journal_mode).upper() == "WAL" or str(journal_mode).upper() == "MEMORY") and (fk_enabled == 1)

    return {
        "status": "ready" if is_ready else "not_ready",
        "pragmas": {
            "journal_mode": journal_mode,
            "foreign_keys": bool(fk_enabled),
            "busy_timeout_ms": busy_timeout,
        },
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
