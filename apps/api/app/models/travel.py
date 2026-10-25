from datetime import datetime, date, timezone
import uuid
from decimal import Decimal
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Date,
    Integer,
    Numeric,
    Text,
    JSON,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TravelRequest(Base):
    """出差申請單主檔 (Travel Requests)"""
    __tablename__ = "travel_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    request_number = Column(String(64), nullable=False, index=True)
    
    title = Column(String(200), nullable=False)
    destination = Column(String(200), nullable=False)
    region_type = Column(String(20), default="DOMESTIC", nullable=False)  # DOMESTIC 國內, OVERSEAS 國外
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    start_time = Column(String(10), nullable=True)  # 例如 "09:00"
    end_time = Column(String(10), nullable=True)    # 例如 "18:00"
    estimated_days = Column(Numeric(5, 2), nullable=False, default=Decimal("1.00"))
    estimated_nights = Column(Integer, default=0, nullable=False)
    
    transport_mode = Column(String(50), nullable=False)  # 主要交通方式 (相容性保留)
    transport_modes = Column(JSON, nullable=True)        # 複選交通方式清單 ["COMPANY_CAR", "HSR", "AIRPLANE", ...]
    transport_other = Column(String(100), nullable=True) # 其他交通方式補充
    
    # 住宿需求與同行、拜訪
    needs_accommodation = Column(Boolean, default=False, nullable=False)
    accommodation_plan = Column(String(200), nullable=True)  # 預計住宿飯店或說明
    companions = Column(String(255), nullable=True)          # 同行人員
    visiting_target = Column(String(200), nullable=True)     # 拜訪對象／單位
    planned_agenda = Column(Text, nullable=True)             # 預定工作內容
    expected_results = Column(Text, nullable=True)           # 預期成果
    
    # 預估費用明細 (Estimated Expenses)
    estimated_transport_cost = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    estimated_accommodation_cost = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    estimated_daily_cost = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    estimated_other_cost = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    estimated_total_cost = Column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    notes = Column(Text, nullable=True)                      # 備註
    
    purpose = Column(Text, nullable=False)
    
    deputy_employee_id = Column(String(36), ForeignKey("employees.id", ondelete="SET NULL"), nullable=True)
    
    # 預支款設定 (Pre-advance Cash/Fund)
    has_advance = Column(Boolean, default=False, nullable=False)
    advance_currency = Column(String(10), default="TWD", nullable=False)
    advance_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)
    
    status = Column(String(32), default="DRAFT", nullable=False, index=True)  # DRAFT, IN_REVIEW, APPROVED, REJECTED, CANCELLED, RETURNED
    settlement_status = Column(String(32), default="UNSETTLED", nullable=False, index=True)  # UNSETTLED, SETTLING, SETTLED
    workflow_instance_id = Column(String(36), ForeignKey("workflow_instances.id", ondelete="SET NULL"), nullable=True, index=True)
    revision = Column(Integer, default=1, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    settlements = relationship("TravelSettlement", back_populates="travel_request", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("company_id", "request_number", name="uq_travel_requests_company_req_no"),
        Index("ix_travel_requests_employee_status", "employee_id", "status"),
    )


class TravelSettlement(Base):
    """出差請款／結報單 (Travel Settlements)"""
    __tablename__ = "travel_settlements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    travel_request_id = Column(String(36), ForeignKey("travel_requests.id", ondelete="RESTRICT"), nullable=False, index=True)
    settlement_number = Column(String(64), nullable=False, index=True)
    
    # 幣別與匯率快照
    currency = Column(String(10), default="TWD", nullable=False)
    exchange_rate = Column(Numeric(10, 4), default=Decimal("1.0000"), nullable=False)
    
    # 金額核算 (非浮點數，全部採高精度 Numeric)
    total_actual_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)  # 實際支出原幣總額
    total_actual_twd = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)     # 實際支出本位幣總額
    advance_offset_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False) # 沖銷預支款金額
    net_payable_amount = Column(Numeric(14, 4), default=Decimal("0.0000"), nullable=False)    # 應補發(正數) / 應繳回(負數)
    
    notes = Column(Text, nullable=True)
    receipt_count = Column(Integer, default=0, nullable=False)
    
    status = Column(String(32), default="DRAFT", nullable=False, index=True)  # DRAFT, IN_REVIEW, APPROVED, REJECTED, CANCELLED, RETURNED
    workflow_instance_id = Column(String(36), ForeignKey("workflow_instances.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # 會計付款與沖銷紀錄
    payment_status = Column(String(32), default="UNPAID", nullable=False, index=True)  # UNPAID, PAID
    paid_at = Column(DateTime(timezone=True), nullable=True)
    paid_reference = Column(String(100), nullable=True)  # 銀行傳票或交易批號
    revision = Column(Integer, default=1, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    travel_request = relationship("TravelRequest", back_populates="settlements")
    items = relationship("TravelExpenseItem", back_populates="settlement", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("company_id", "settlement_number", name="uq_travel_settlements_company_set_no"),
        Index("ix_travel_settlements_employee_status", "employee_id", "status"),
    )


class TravelExpenseItem(Base):
    """出差結報費用明細項 (Travel Expense Items)"""
    __tablename__ = "travel_expense_items"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    settlement_id = Column(String(36), ForeignKey("travel_settlements.id", ondelete="CASCADE"), nullable=False, index=True)
    
    expense_category = Column(String(50), nullable=False)  # TRANSPORT 交通費, LODGING 住宿費, MEAL 膳雜費, OTHER 其他
    expense_date = Column(Date, nullable=False)
    currency = Column(String(10), default="TWD", nullable=False)
    exchange_rate = Column(Numeric(10, 4), default=Decimal("1.0000"), nullable=False)
    amount = Column(Numeric(14, 4), nullable=False)
    amount_twd = Column(Numeric(14, 4), nullable=False)
    
    invoice_number = Column(String(100), nullable=True)
    description = Column(String(255), nullable=False)
    attachment_url = Column(String(512), nullable=True)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    settlement = relationship("TravelSettlement", back_populates="items")
