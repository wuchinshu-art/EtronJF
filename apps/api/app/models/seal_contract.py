import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional, List
from sqlalchemy import (
    Column,
    String,
    Text,
    Boolean,
    Integer,
    Numeric,
    Date,
    DateTime,
    ForeignKey,
    JSON,
    Index,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Seal(Base):
    """
    印鑑清冊主檔 (Seals - 名稱、類型、所屬公司、保管人、生效／失效、交接紀錄留痕)
    """
    __tablename__ = "seals"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(50), nullable=False, index=True)  # SEAL-001
    name = Column(String(100), nullable=False)  # 公司大印、董事長私章、合約專用章
    seal_type = Column(String(50), nullable=False)  # COMPANY_SEAL, LEGAL_REP, CONTRACT_SEAL, FINANCE_SEAL
    custodian_employee_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)

    is_active = Column(Boolean, default=True, nullable=False)
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)

    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    handovers = relationship("SealHandover", back_populates="seal", cascade="all, delete-orphan")
    seal_requests = relationship("SealRequest", back_populates="seal")


class SealHandover(Base):
    """印鑑保管人交接紀錄 (Seal Handovers - 更換保管人完整留痕)"""
    __tablename__ = "seal_handovers"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    seal_id = Column(String(36), ForeignKey("seals.id", ondelete="CASCADE"), nullable=False, index=True)
    from_custodian_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False)
    to_custodian_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False)
    handover_date = Column(Date, nullable=False)
    reason = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    seal = relationship("Seal", back_populates="handovers")


class SealRequest(Base):
    """
    用印申請單 (Seal Requests)
    - 簽核管線：直屬主管 -> 印鑑保管人
    - 簽核核准不等於已用印；保管人執行後記錄實際日期、份數與完成掃描件。
    """
    __tablename__ = "seal_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    seal_id = Column(String(36), ForeignKey("seals.id", ondelete="RESTRICT"), nullable=False, index=True)
    request_number = Column(String(50), unique=True, nullable=False, index=True)  # SEAL-YYYYMMDD-XXXX

    document_name = Column(String(200), nullable=False)
    document_version = Column(String(50), default="v1.0", nullable=False)
    purpose = Column(Text, nullable=False)
    copies = Column(Integer, default=1, nullable=False)
    attachment_url = Column(String(500), nullable=True)

    # 關聯之合約 (若為合約關聯用印)
    contract_id = Column(String(36), ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True, index=True)

    # 簽核狀態：DRAFT, IN_REVIEW, APPROVED, REJECTED, RETURNED, CANCELLED
    status = Column(String(20), default="DRAFT", nullable=False, index=True)

    # 用印執行狀態：NOT_SEALED, SEALED
    execution_status = Column(String(20), default="NOT_SEALED", nullable=False, index=True)
    sealed_at = Column(DateTime(timezone=True), nullable=True)
    sealed_copies = Column(Integer, nullable=True)
    sealed_by_employee_id = Column(String(36), ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    final_sealed_document_url = Column(String(500), nullable=True)

    workflow_instance_id = Column(String(36), ForeignKey("workflow_instances.id", ondelete="SET NULL"), nullable=True)
    revision = Column(Integer, default=1, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    seal = relationship("Seal", back_populates="seal_requests")
    contract = relationship("Contract", back_populates="seal_requests", foreign_keys=[contract_id])


class Contract(Base):
    """
    合約主檔與審查 (Contracts)
    - 簽核管線：直屬主管 -> 第二層主管 (>=5000) -> 第三層主管 (>=100000) -> 法務窗口 -> 印鑑保管人 (需用印)
    - 支援無金額合約、框架額度、期限、到期提醒與續約關聯
    """
    __tablename__ = "contracts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    contract_number = Column(String(50), unique=True, nullable=False, index=True)  # CTR-YYYYMMDD-XXXX

    counterparty_name = Column(String(200), nullable=False)  # 立約相對人/客戶/供應商
    title = Column(String(200), nullable=False)
    contract_type = Column(String(50), nullable=False)  # NDA, PURCHASE, SALES, SERVICE, LEASE, FRAMEWORK
    responsible_department = Column(String(100), nullable=True)  # 責任部門

    currency = Column(String(10), default="TWD", nullable=False)
    exchange_rate = Column(Numeric(14, 4), default=Decimal("1.0000"), nullable=False)
    amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)  # 0 代表無金額合約 (如 NDA)
    amount_twd = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)  # 為空代表無固定終止日
    auto_renew = Column(Boolean, default=False, nullable=False)
    needs_seal = Column(Boolean, default=False, nullable=False)  # 是否需要用印

    attachment_url = Column(String(500), nullable=True)
    legal_opinion = Column(Text, nullable=True)  # 法務意見紀錄

    # 狀態機：DRAFT, IN_REVIEW, APPROVED, REJECTED, RETURNED, CANCELLED
    status = Column(String(20), default="DRAFT", nullable=False, index=True)
    # 生命週期狀態：PENDING_APPROVAL, ACTIVE, EXPIRED, TERMINATED
    lifecycle_status = Column(String(20), default="PENDING_APPROVAL", nullable=False, index=True)

    signed_document_url = Column(String(500), nullable=True)
    archived_at = Column(DateTime(timezone=True), nullable=True)

    # 續約關聯
    renewed_from_contract_id = Column(String(36), ForeignKey("contracts.id", ondelete="SET NULL"), nullable=True)

    workflow_instance_id = Column(String(36), ForeignKey("workflow_instances.id", ondelete="SET NULL"), nullable=True)
    revision = Column(Integer, default=1, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    seal_requests = relationship("SealRequest", back_populates="contract", foreign_keys=[SealRequest.contract_id])
