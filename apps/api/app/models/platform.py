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
    JSON,
    Index,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Attachment(Base):
    """平台附件管理 (Attachments - 隔離於 web root 外隨機 storage key 儲存，下載重新驗證權限)"""
    __tablename__ = "attachments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    original_file_name = Column(String(255), nullable=False)
    storage_key = Column(String(100), unique=True, nullable=False, index=True)  # 隨機高熵儲存識別碼
    content_type = Column(String(100), nullable=False)                         # MIME 類型驗證
    file_size_bytes = Column(Integer, nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)                 # SHA-256 完整性雜湊
    
    uploaded_by = Column(String(36), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class AuditLog(Base):
    """系統安全稽核日誌 (Audit Logs - 僅追加紀錄，記錄前後狀態遮罩、操作者與 UTC 時間戳)"""
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), nullable=False, index=True)
    actor_id = Column(String(36), nullable=False, index=True)
    
    action = Column(String(50), nullable=False, index=True)          # LOGIN, LOGOUT, APPROVE, REJECT, EXPORT, BACKUP
    object_type = Column(String(50), nullable=False, index=True)     # USER, LEAVE, PAYMENT, CONTRACT, ATTENDANCE, SYSTEM
    object_id = Column(String(50), nullable=False, index=True)
    
    before_state = Column(JSON, nullable=True)                      # 遮罩敏感密碼與銀行帳號
    after_state = Column(JSON, nullable=True)                       # 遮罩敏感密碼與銀行帳號
    reason = Column(String(255), nullable=True)
    request_id = Column(String(36), nullable=True, index=True)
    ip_address = Column(String(45), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
