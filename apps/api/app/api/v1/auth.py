from datetime import datetime, timedelta, timezone, date
from typing import List, Optional
from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession
from sqlalchemy import select, or_

from app.core.config import settings
from app.core.database import get_db
from app.core.security import (
    verify_password,
    hash_password,
    generate_session_token,
    generate_csrf_token,
    hash_token,
)
from app.core.errors import AppException
from app.models.auth import User, Session as UserSession, UserRole, UserScope, RolePermission
from app.models.hr import Employee, ManagerRelation, Organization
from app.api.deps import get_current_session, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class LoginRequest(BaseModel):
    username: str
    password: str
    company_id: Optional[str] = None  # 若未指定則使用使用者的 primary_company_id


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8)


class FirstTimePasswordRequest(BaseModel):
    new_password: str = Field(min_length=8)


class UserProfileResponse(BaseModel):
    id: str
    username: str
    email: str
    display_name: str
    primary_company_id: str
    active_company_id: str
    is_first_login: bool
    roles: List[str]
    permissions: List[str]
    csrf_token: str
    employee_id: Optional[str] = None
    employee_no: Optional[str] = None
    department_id: Optional[str] = None
    department_name: Optional[str] = None
    manager_id: Optional[str] = None
    manager_name: Optional[str] = None
    manager_no: Optional[str] = None


@router.post("/login", status_code=status.HTTP_200_OK)
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession = Depends(get_db),
):
    """使用者登入：支援帳號代碼、員工工號、電子信箱或信箱前綴驗證密碼，建立伺服器端 Session"""
    login_id = req.username.strip()
    stmt = select(User).where(
        or_(
            User.username == login_id,
            User.email == login_id,
            User.email.ilike(f"{login_id}@%"),
        )
    )
    user = db.execute(stmt).scalars().first()

    if not user or not verify_password(req.password, user.hashed_password):
        raise AppException(
            code="INVALID_CREDENTIALS",
            message="帳號或密碼錯誤",
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        raise AppException(
            code="USER_SUSPENDED",
            message="此帳號已被停用，請聯絡系統管理員",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # 決定當前登入的公司 (Active Company)
    active_company = req.company_id or user.primary_company_id

    # 產生 Session Token 與 CSRF Token
    raw_session_token = generate_session_token()
    session_hash = hash_token(raw_session_token)
    csrf_tok = generate_csrf_token()

    now = utc_now()
    expires_at = now + timedelta(seconds=settings.SESSION_MAX_AGE_SECONDS)
    idle_expires_at = now + timedelta(minutes=30)

    new_session = UserSession(
        session_token_hash=session_hash,
        user_id=user.id,
        active_company_id=active_company,
        csrf_token=csrf_tok,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        expires_at=expires_at,
        idle_expires_at=idle_expires_at,
        created_at=now,
        last_accessed_at=now,
    )
    db.add(new_session)
    db.commit()

    # 設置 HttpOnly / SameSite / Secure Session Cookie
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=raw_session_token,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,  # 開發環境相容 http://localhost，正式部署啟用 Secure
        path="/",
    )

    return {
        "status": "success",
        "message": "登入成功",
        "is_first_login": user.is_first_login,
        "csrf_token": csrf_tok,
        "active_company_id": active_company,
    }


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(
    response: Response,
    session: UserSession = Depends(get_current_session),
    db: DbSession = Depends(get_db),
):
    """登出：伺服器端標記 Session 為已撤銷，並清除前端 Cookie"""
    session.is_revoked = True
    session.revoked_at = utc_now()
    db.commit()

    response.delete_cookie(
        key=settings.SESSION_COOKIE_NAME,
        path="/",
    )

    return {"status": "success", "message": "已成功登出並撤銷工作階段"}


@router.get("/me", response_model=UserProfileResponse)
def get_my_profile(
    user: User = Depends(get_current_user),
    session: UserSession = Depends(get_current_session),
    db: DbSession = Depends(get_db),
):
    """查詢當前登入者資訊、角色、權限碼及 CSRF Token"""
    # 查詢活動公司角色
    role_stmt = select(UserRole.role_id).where(
        UserRole.user_id == user.id,
        UserRole.company_id == session.active_company_id,
    )
    roles = list(db.execute(role_stmt).scalars().all())

    # 查詢權限碼
    perm_stmt = (
        select(RolePermission.permission_code)
        .join(UserRole, UserRole.role_id == RolePermission.role_id)
        .where(
            UserRole.user_id == user.id,
            UserRole.company_id == session.active_company_id,
        )
    )
    permissions = list(db.execute(perm_stmt).scalars().all())

    employee_id = user.employee_id
    employee_no = None
    department_id = None
    department_name = None
    manager_id = None
    manager_name = None
    manager_no = None

    emp = None
    if employee_id:
        emp = db.get(Employee, employee_id)
    if not emp and user.email:
        emp = db.execute(select(Employee).where(Employee.email == user.email)).scalar_one_or_none()

    if emp:
        employee_id = emp.id
        employee_no = emp.employee_no
        department_id = emp.organization_id
        if emp.organization:
            department_name = emp.organization.name
        elif emp.organization_id:
            org = db.get(Organization, emp.organization_id)
            if org:
                department_name = org.name

        # 查詢目前直屬主管 (DIRECT)
        today = date.today()
        mgr_stmt = (
            select(ManagerRelation)
            .where(
                ManagerRelation.employee_id == emp.id,
                ManagerRelation.relation_type == "DIRECT",
                (ManagerRelation.effective_to == None) | (ManagerRelation.effective_to >= today),
            )
        )
        direct_mgr_rel = db.execute(mgr_stmt).scalar_one_or_none()
        if direct_mgr_rel:
            mgr = db.get(Employee, direct_mgr_rel.manager_id)
            if mgr:
                manager_id = mgr.id
                manager_no = mgr.employee_no
                manager_name = mgr.full_name

    return UserProfileResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        primary_company_id=user.primary_company_id,
        active_company_id=session.active_company_id,
        is_first_login=user.is_first_login,
        roles=roles,
        permissions=permissions,
        csrf_token=session.csrf_token,
        employee_id=employee_id,
        employee_no=employee_no,
        department_id=department_id,
        department_name=department_name,
        manager_id=manager_id,
        manager_name=manager_name,
        manager_no=manager_no,
    )


@router.post("/first-time-password", status_code=status.HTTP_200_OK)
def set_first_time_password(
    req: FirstTimePasswordRequest,
    user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """首次登入強制設定新密碼"""
    if not user.is_first_login:
        raise AppException(
            code="NOT_FIRST_LOGIN",
            message="該帳號非首次登入，請使用一般變更密碼功能",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user.hashed_password = hash_password(req.new_password)
    user.is_first_login = False
    user.updated_at = utc_now()
    user.version += 1
    db.commit()

    return {"status": "success", "message": "密碼初始化設定成功"}


@router.post("/change-password", status_code=status.HTTP_200_OK)
def change_password(
    req: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    session: UserSession = Depends(get_current_session),
    db: DbSession = Depends(get_db),
):
    """登入狀態變更密碼：需驗證舊密碼"""
    if not verify_password(req.old_password, user.hashed_password):
        raise AppException(
            code="OLD_PASSWORD_MISMATCH",
            message="目前輸入之舊密碼不正確",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    user.hashed_password = hash_password(req.new_password)
    user.updated_at = utc_now()
    user.version += 1
    db.commit()

    return {"status": "success", "message": "密碼變更成功"}
