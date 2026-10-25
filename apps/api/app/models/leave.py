from datetime import datetime, timezone
import uuid
from decimal import Decimal
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Numeric,
    Text,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from app.core.database import Base


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(36), ForeignKey("companies.id"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id"), nullable=False, index=True)
    leave_type_id = Column(String(36), ForeignKey("leave_types.id"), nullable=False, index=True)
    request_number = Column(String(64), nullable=False, index=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    total_minutes = Column(Integer, nullable=False, default=0)
    calculated_days = Column(Numeric(5, 2), nullable=False, default=Decimal("0.00"))
    reason = Column(Text, nullable=False)
    deputy_employee_id = Column(String(36), ForeignKey("employees.id"), nullable=True)
    attachment_url = Column(String(512), nullable=True)
    status = Column(String(32), nullable=False, default="DRAFT", index=True)
    workflow_instance_id = Column(String(36), ForeignKey("workflow_instances.id"), nullable=True, index=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint("company_id", "request_number", name="uq_leave_requests_company_req_no"),
        Index("ix_leave_requests_employee_status", "employee_id", "status"),
        Index("ix_leave_requests_company_created", "company_id", "created_at"),
    )
