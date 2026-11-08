"""工作階段 (Session) 查詢與撤銷共用服務。

帳號自助 (/auth/sessions) 與管理員 (/users/{id}/sessions) 共用同一套邏輯，
避免各模組自行實作 session 撤銷。
"""
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session as DbSession

from app.models.auth import Session as UserSession

USER_AGENT_DISPLAY_MAX = 200


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso_utc(dt: Optional[datetime]) -> Optional[str]:
    return _ensure_utc(dt).isoformat().replace("+00:00", "Z") if dt else None


def is_session_active(s: UserSession, now: datetime) -> bool:
    return (
        not s.is_revoked
        and _ensure_utc(s.expires_at) > now
        and _ensure_utc(s.idle_expires_at) > now
    )


def list_active_sessions(db: DbSession, user_id: str, now: datetime) -> List[UserSession]:
    """列出使用者未撤銷且未過期之工作階段 (最近存取優先)。

    SQLite 可能回傳 naive datetime，過期判斷於 Python 端以 UTC 處理。
    """
    stmt = (
        select(UserSession)
        .where(UserSession.user_id == user_id, UserSession.is_revoked == False)  # noqa: E712
        .order_by(UserSession.last_accessed_at.desc())
    )
    return [s for s in db.execute(stmt).scalars().all() if is_session_active(s, now)]


def serialize_session(s: UserSession, current_session_id: Optional[str]) -> dict:
    """Session 對外回應：不含 token hash 與 CSRF token；時間一律 UTC ISO-8601"""
    ua = s.user_agent or ""
    return {
        "id": s.id,
        "active_company_id": s.active_company_id,
        "ip_address": s.ip_address,
        "user_agent": ua[:USER_AGENT_DISPLAY_MAX],
        "created_at": _iso_utc(s.created_at),
        "last_accessed_at": _iso_utc(s.last_accessed_at),
        "expires_at": _iso_utc(s.expires_at),
        "idle_expires_at": _iso_utc(s.idle_expires_at),
        "is_current": s.id == current_session_id,
    }


def revoke_sessions(
    db: DbSession,
    user_id: str,
    now: datetime,
    exclude_session_id: Optional[str] = None,
) -> int:
    """撤銷使用者全部未撤銷 session (可排除一個)，回傳撤銷筆數；由呼叫端 commit"""
    stmt = update(UserSession).where(
        UserSession.user_id == user_id,
        UserSession.is_revoked == False,  # noqa: E712
    )
    if exclude_session_id:
        stmt = stmt.where(UserSession.id != exclude_session_id)
    result = db.execute(stmt.values(is_revoked=True, revoked_at=now))
    return result.rowcount or 0
