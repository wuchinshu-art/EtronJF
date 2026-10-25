from datetime import datetime, timezone, timedelta
from typing import List, Optional, Callable
from fastapi import Request, Depends, HTTPException, status
from sqlalchemy.orm import Session as DbSession
from sqlalchemy import select

from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_token
from app.core.errors import AppException
from app.models.auth import User, Session as UserSession, UserRole, RolePermission, UserScope


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def get_current_session(
    request: Request,
    db: DbSession = Depends(get_db),
) -> UserSession:
    token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not token:
        raise AppException(
            code="UNAUTHENTICATED",
            message="使用者未登入或工作階段已逾時，請重新登入",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    token_hash = hash_token(token)
    stmt = (
        select(UserSession)
        .where(UserSession.session_token_hash == token_hash)
    )
    user_session = db.execute(stmt).scalar_one_or_none()

    if not user_session:
        raise AppException(
            code="INVALID_SESSION",
            message="無效的工作階段",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    now = utc_now()

    # 檢查是否已撤銷
    if user_session.is_revoked:
        raise AppException(
            code="SESSION_REVOKED",
            message="工作階段已被撤銷，請重新登入",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # 檢查是否過期 (支援 SQLite naive datetime 安全轉換)
    if ensure_utc(user_session.expires_at) <= now or ensure_utc(user_session.idle_expires_at) <= now:
        user_session.is_revoked = True
        user_session.revoked_at = now
        db.commit()
        raise AppException(
            code="SESSION_EXPIRED",
            message="工作階段已過期，請重新登入",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    # 檢查使用者帳號狀態
    user = db.get(User, user_session.user_id)
    if not user or not user.is_active:
        user_session.is_revoked = True
        user_session.revoked_at = now
        db.commit()
        raise AppException(
            code="USER_INACTIVE",
            message="該帳號已停用或不存在，工作階段已立即失效",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # CSRF Token 檢查 (針對非安全 HTTP 方法)
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        csrf_header = request.headers.get("X-CSRF-Token")
        if not csrf_header or csrf_header != user_session.csrf_token:
            raise AppException(
                code="CSRF_VERIFICATION_FAILED",
                message="CSRF 權杖驗證失敗，請求被拒絕",
                status_code=status.HTTP_403_FORBIDDEN,
            )

    # 滑動更新最後存取時間與閒置過期時間 (30 分鐘閒置寬限)
    user_session.last_accessed_at = now
    user_session.idle_expires_at = now + timedelta(minutes=30)
    db.commit()

    return user_session


def get_current_user(
    session: UserSession = Depends(get_current_session),
    db: DbSession = Depends(get_db),
) -> User:
    """取得當前已驗證的使用者實體"""
    user = db.get(User, session.user_id)
    if not user:
        raise AppException(
            code="USER_NOT_FOUND",
            message="找不到使用者",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    return user


def require_permissions(*required_permissions: str) -> Callable:
    """權限碼檢查裝飾依賴 (RBAC Permission Dependency)"""
    def permission_checker(
        session: UserSession = Depends(get_current_session),
        db: DbSession = Depends(get_db),
    ) -> UserSession:
        # 查詢使用者在當前活動公司 (active_company_id) 擁有的所有權限碼
        stmt = (
            select(RolePermission.permission_code)
            .join(UserRole, UserRole.role_id == RolePermission.role_id)
            .where(
                UserRole.user_id == session.user_id,
                UserRole.company_id == session.active_company_id,
            )
        )
        user_perms = set(db.execute(stmt).scalars().all())

        # 平台管理員若有 ADMIN 角色亦視為具備全權限
        admin_check = (
            select(UserRole)
            .where(
                UserRole.user_id == session.user_id,
                UserRole.role_id == "ADMIN",
            )
        )
        is_admin = db.execute(admin_check).scalar_one_or_none() is not None

        if not is_admin:
            for req in required_permissions:
                if req not in user_perms:
                    raise AppException(
                        code="PERMISSION_DENIED",
                        message=f"權限不足：缺少必要權限碼 [{req}]",
                        status_code=status.HTTP_403_FORBIDDEN,
                    )
        return session

    return permission_checker


def require_company_scope(target_company_id: str):
    """
    公司資料範圍檢查 (Company Scope Enforcement - 防跨公司 IDOR 核心)
    驗證使用者是否有權限存取指定的 target_company_id
    """
    def scope_checker(
        session: UserSession = Depends(get_current_session),
        db: DbSession = Depends(get_db),
    ) -> None:
        # 使用者僅能在其擁有 scope 的公司範圍內操作
        stmt = (
            select(UserScope)
            .where(
                UserScope.user_id == session.user_id,
                UserScope.company_id == target_company_id,
            )
        )
        has_scope = db.execute(stmt).scalar_one_or_none() is not None
        
        # 或身為目前 session 作用的公司且身分一致
        if not has_scope and session.active_company_id != target_company_id:
            raise AppException(
                code="CROSS_COMPANY_FORBIDDEN",
                message=f"跨公司存取遭拒：無權存取公司 [{target_company_id}] 之業務資源",
                status_code=status.HTTP_403_FORBIDDEN,
            )

    return scope_checker
