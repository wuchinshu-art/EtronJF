import uuid
from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    """使用者主檔 (Users)"""
    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    display_name = Column(String(100), nullable=False)
    
    # 員工關聯 (帳號與員工分離，員工尚未開通帳號時 employee_id 為空)
    employee_id = Column(String(36), nullable=True, index=True)
    primary_company_id = Column(String(50), nullable=False, index=True)  # 主要所屬公司 (例如 ETJ-TW / ETJ-JP)
    
    is_active = Column(Boolean, default=True, nullable=False)
    is_first_login = Column(Boolean, default=True, nullable=False)  # 首次登入需強制設定密碼
    version = Column(Integer, default=1, nullable=False)  # 樂觀鎖版本號
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    # 關聯
    sessions = relationship("Session", back_populates="user", cascade="all, delete-orphan")
    roles = relationship("UserRole", back_populates="user", cascade="all, delete-orphan")
    scopes = relationship("UserScope", back_populates="user", cascade="all, delete-orphan")


class Role(Base):
    """角色定義 (Roles)"""
    __tablename__ = "roles"

    id = Column(String(50), primary_key=True)  # 例如 ADMIN, EMPLOYEE, HR_MANAGER, FINANCE_OFFICER
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    company_id = Column(String(50), nullable=True)  # 全域角色為空，公司專用角色有 company_id
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    
    permissions = relationship("RolePermission", back_populates="role", cascade="all, delete-orphan")
    users = relationship("UserRole", back_populates="role", cascade="all, delete-orphan")


class Permission(Base):
    """權限碼定義 (Permissions)"""
    __tablename__ = "permissions"

    code = Column(String(100), primary_key=True)  # 例如 leave.create, hr.employee.manage
    name = Column(String(100), nullable=False)
    module = Column(String(50), nullable=False)  # 例如 LEAVE, HR, FINANCE
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    roles = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")


class RolePermission(Base):
    """角色與權限對應 (Role-Permission Mapping)"""
    __tablename__ = "role_permissions"

    role_id = Column(String(50), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_code = Column(String(100), ForeignKey("permissions.code", ondelete="CASCADE"), primary_key=True)

    role = relationship("Role", back_populates="permissions")
    permission = relationship("Permission", back_populates="roles")


class UserRole(Base):
    """使用者角色對應 (User-Role Mapping)"""
    __tablename__ = "user_roles"

    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role_id = Column(String(50), ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    company_id = Column(String(50), nullable=False, primary_key=True)  # 角色在特定公司生效

    user = relationship("User", back_populates="roles")
    role = relationship("Role", back_populates="users")


class UserScope(Base):
    """使用者資料存取範圍 (User Scopes - 公司/組織/本人層級)"""
    __tablename__ = "user_scopes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    company_id = Column(String(50), nullable=False, index=True)
    organization_id = Column(String(50), nullable=True, index=True)
    scope_type = Column(String(20), nullable=False)  # COMPANY, ORG, OWN

    user = relationship("User", back_populates="scopes")

    __table_args__ = (
        UniqueConstraint("user_id", "company_id", "organization_id", "scope_type", name="uq_user_scope"),
    )


class Session(Base):
    """工作階段 (Sessions - 伺服器端狀態保存，支援停用立即撤銷)"""
    __tablename__ = "sessions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_token_hash = Column(String(64), unique=True, nullable=False, index=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    active_company_id = Column(String(50), nullable=False)
    
    csrf_token = Column(String(64), nullable=False)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    expires_at = Column(DateTime(timezone=True), nullable=False)       # 絕對過期時間
    idle_expires_at = Column(DateTime(timezone=True), nullable=False)  # 閒置過期時間
    is_revoked = Column(Boolean, default=False, nullable=False)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    last_accessed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    user = relationship("User", back_populates="sessions")


class PasswordResetToken(Base):
    """密碼重設權杖 (限時一次性，雜湊儲存)"""
    __tablename__ = "password_reset_tokens"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    token_hash = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
