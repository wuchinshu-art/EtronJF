from datetime import datetime, timezone
import uuid
from sqlalchemy import (
    Column,
    String,
    DateTime,
    Integer,
    Text,
    ForeignKey,
    UniqueConstraint,
    Index,
)
from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class OvertimeRequest(Base):
    __tablename__ = "overtime_requests"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    request_number = Column(String(64), nullable=False, index=True)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    rest_minutes = Column(Integer, nullable=False, default=0)
    total_minutes = Column(Integer, nullable=False, default=0)
    day_type = Column(String(20), nullable=False, default="REGULAR")  # REGULAR, REST_DAY, REGULAR_HOLIDAY, NATIONAL_HOLIDAY
    compensation_type = Column(String(20), nullable=False, default="COMPENSATORY_LEAVE")  # COMPENSATORY_LEAVE, PAY
    comp_leave_minutes = Column(Integer, nullable=False, default=0)
    reason = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="DRAFT", index=True)
    workflow_instance_id = Column(String(36), ForeignKey("workflow_instances.id", ondelete="SET NULL"), nullable=True, index=True)
    revision = Column(Integer, nullable=False, default=1)
    created_at = Column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = Column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    __table_args__ = (
        UniqueConstraint("company_id", "request_number", name="uq_overtime_requests_company_req_no"),
        Index("ix_overtime_requests_employee_status", "employee_id", "status"),
        Index("ix_overtime_requests_company_created", "company_id", "created_at"),
    )
