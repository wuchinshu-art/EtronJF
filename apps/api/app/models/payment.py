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


class Vendor(Base):
    """
    供應商主檔 (Vendors)
    - 銀行資訊限權、遮罩與異動留痕
    - 支援台日跨國供應商銀行與 SWIFT 欄位
    """
    __tablename__ = "vendors"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(50), nullable=False, index=True)
    name = Column(String(200), nullable=False)
    country = Column(String(10), nullable=False, default="TW")  # TW, JP, US 等
    tax_id = Column(String(50), nullable=True)  # 統一編號 / 法人番號 / Tax ID
    address = Column(String(255), nullable=True)
    contact_name = Column(String(100), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    email = Column(String(255), nullable=True)
    payment_terms = Column(String(50), default="NET30", nullable=False)  # NET30, NET60, COD, EOM
    is_active = Column(Boolean, default=True, nullable=False)

    # 銀行受款帳戶資訊 (限權與遮罩)
    bank_country = Column(String(10), nullable=True)
    bank_name = Column(String(100), nullable=True)
    bank_code = Column(String(20), nullable=True)
    branch_name = Column(String(100), nullable=True)
    branch_code = Column(String(20), nullable=True)
    account_name = Column(String(100), nullable=True)
    account_number = Column(String(50), nullable=True)
    bank_currency = Column(String(10), default="TWD", nullable=False)
    swift_code = Column(String(20), nullable=True)

    version = Column(Integer, default=1, nullable=False)  # 樂觀鎖版本
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    payment_requests = relationship("PaymentRequest", back_populates="vendor")

    def masked_account_number(self) -> str:
        """遮罩銀行帳號 (末4碼顯示，其餘星號)"""
        if not self.account_number:
            return ""
        if len(self.account_number) <= 4:
            return "****"
        return "*" * (len(self.account_number) - 4) + self.account_number[-4:]


class ExpenseClaim(Base):
    """
    費用報銷單主表 (Expense Claims - 員工一般費用報支)
    簽核管線：直屬主管 -> 第二層主管 (>=5000) -> 第三層主管 (>=100000) -> 會計窗口
    """
    __tablename__ = "expense_claims"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    claim_number = Column(String(50), unique=True, nullable=False, index=True)  # EXP-YYYYMMDD-XXXX

    title = Column(String(200), nullable=False)
    cost_center = Column(String(50), nullable=True)
    currency = Column(String(10), default="TWD", nullable=False)
    exchange_rate = Column(Numeric(14, 4), default=Decimal("1.0000"), nullable=False)

    total_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    total_amount_twd = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    tax_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)

    # 狀態機：DRAFT, IN_REVIEW, APPROVED, REJECTED, RETURNED, CANCELLED
    status = Column(String(20), default="DRAFT", nullable=False, index=True)
    # 付款狀態：UNPAID, PAID
    payment_status = Column(String(20), default="UNPAID", nullable=False, index=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    paid_reference = Column(String(100), nullable=True)

    # 匯兌損益與 ERP 總帳拋轉支援 (Exchange Gain/Loss & GL Ready)
    settlement_exchange_rate = Column(Numeric(14, 4), nullable=True)
    exchange_gain_loss = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    gl_posted = Column(Boolean, default=False, nullable=False)
    gl_posted_at = Column(DateTime(timezone=True), nullable=True)

    has_duplicate_warning = Column(Boolean, default=False, nullable=False)
    notes = Column(Text, nullable=True)
    workflow_instance_id = Column(String(36), ForeignKey("workflow_instances.id", ondelete="SET NULL"), nullable=True)
    revision = Column(Integer, default=1, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    items = relationship("ExpenseClaimItem", back_populates="expense_claim", cascade="all, delete-orphan")


class ExpenseClaimItem(Base):
    """費用報銷明細項 (Expense Claim Items)"""
    __tablename__ = "expense_claim_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    expense_claim_id = Column(String(36), ForeignKey("expense_claims.id", ondelete="CASCADE"), nullable=False, index=True)

    category = Column(String(50), nullable=False)  # MEAL, TRANSPORT, OFFICE, TRAVEL, MISC
    expense_date = Column(Date, nullable=False)
    invoice_number = Column(String(100), nullable=True, index=True)  # 發票/收據號碼
    currency = Column(String(10), default="TWD", nullable=False)
    exchange_rate = Column(Numeric(14, 4), default=Decimal("1.0000"), nullable=False)

    amount = Column(Numeric(14, 4), nullable=False)
    amount_twd = Column(Numeric(14, 4), nullable=False)
    description = Column(String(255), nullable=False)
    attachment_url = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    expense_claim = relationship("ExpenseClaim", back_populates="items")


class PaymentRequest(Base):
    """
    供應商請款單 (Payment Requests - 應付請款)
    簽核管線：直屬主管 -> 部級主管 (>=5000) -> 處級主管 (>=100000) -> 總經理 (>=500000) -> 會計窗口
    保存送簽當下之供應商與銀行受款資料快照，防範主檔竄改。
    """
    __tablename__ = "payment_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    vendor_id = Column(String(36), ForeignKey("vendors.id", ondelete="RESTRICT"), nullable=False, index=True)
    payment_number = Column(String(50), unique=True, nullable=False, index=True)  # PAY-YYYYMMDD-XXXX

    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # 送簽時供應商與銀行受款快照 (Snapshot 不可變性保證)
    vendor_snapshot = Column(JSON, nullable=False)

    currency = Column(String(10), default="TWD", nullable=False)
    exchange_rate = Column(Numeric(14, 4), default=Decimal("1.0000"), nullable=False)
    amount = Column(Numeric(14, 4), nullable=False)
    amount_twd = Column(Numeric(14, 4), nullable=False)

    due_date = Column(Date, nullable=False)  # 預計付款日
    payment_method = Column(String(20), default="WIRE", nullable=False)  # WIRE 匯款, CHECK 支票

    invoice_number = Column(String(100), nullable=True, index=True)
    invoice_date = Column(Date, nullable=True)
    attachment_url = Column(String(500), nullable=True)

    # 狀態機：DRAFT, IN_REVIEW, APPROVED, REJECTED, RETURNED, CANCELLED
    status = Column(String(20), default="DRAFT", nullable=False, index=True)
    # 付款狀態：UNPAID, PAID
    payment_status = Column(String(20), default="UNPAID", nullable=False, index=True)
    paid_at = Column(DateTime(timezone=True), nullable=True)
    paid_reference = Column(String(100), nullable=True)

    # 匯兌損益與 ERP 總帳拋轉支援 (Exchange Gain/Loss & GL Ready)
    settlement_exchange_rate = Column(Numeric(14, 4), nullable=True)
    exchange_gain_loss = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    gl_posted = Column(Boolean, default=False, nullable=False)
    gl_posted_at = Column(DateTime(timezone=True), nullable=True)

    workflow_instance_id = Column(String(36), ForeignKey("workflow_instances.id", ondelete="SET NULL"), nullable=True)
    revision = Column(Integer, default=1, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    vendor = relationship("Vendor", back_populates="payment_requests")
