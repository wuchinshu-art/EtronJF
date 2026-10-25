import uuid
from datetime import datetime, date, timezone
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Date,
    ForeignKey,
    Integer,
    Text,
    JSON,
    UniqueConstraint,
    Index,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ShiftAssignment(Base):
    """排班指派主檔 (Shift Assignments - 支援個別日期排班與跨夜班判定)"""
    __tablename__ = "shift_assignments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    shift_id = Column(String(50), ForeignKey("shifts.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_date = Column(Date, nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "employee_id", "work_date", name="uq_employee_work_date_shift"),
    )


class AttendanceImportBatch(Base):
    """出勤匯入批次主檔 (Attendance Import Batches)"""
    __tablename__ = "attendance_import_batches"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_no = Column(String(50), unique=True, nullable=False, index=True)
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    
    file_name = Column(String(255), nullable=False)
    file_hash = Column(String(64), nullable=False, index=True)  # SHA-256 防重複檔案誤匯
    file_format = Column(String(20), nullable=False)            # XLSX, CSV, TSV, TXT
    encoding = Column(String(30), nullable=False, default="UTF-8")  # UTF-8, UTF-8-SIG, CP950, Shift_JIS
    source_timezone = Column(String(50), nullable=False, default="Asia/Taipei")
    datetime_format = Column(String(50), nullable=False, default="%Y-%m-%d %H:%M:%S")

    # 批次狀態：PENDING_PREVIEW (已上傳待預覽), VALIDATED (已預覽驗證), COMMITTED (已確認入庫), FAILED (解析或入庫失敗)
    status = Column(String(20), default="PENDING_PREVIEW", nullable=False, index=True)
    
    total_rows = Column(Integer, default=0, nullable=False)
    valid_rows = Column(Integer, default=0, nullable=False)
    invalid_rows = Column(Integer, default=0, nullable=False)
    duplicate_rows = Column(Integer, default=0, nullable=False)
    committed_rows = Column(Integer, default=0, nullable=False)

    # 預覽版本校驗碼 (防止使用過期預覽快照提交入庫)
    preview_revision = Column(String(50), nullable=True)
    preview_data = Column(JSON, nullable=True)
    error_summary = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by = Column(String(36), nullable=False)
    committed_at = Column(DateTime(timezone=True), nullable=True)
    committed_by = Column(String(36), nullable=True)

    rows = relationship("AttendanceImportRow", back_populates="batch", cascade="all, delete-orphan")


class AttendanceImportRow(Base):
    """出勤匯入逐列明細 (Attendance Import Rows - 留存原始與正規化資料及錯誤碼)"""
    __tablename__ = "attendance_import_rows"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_id = Column(String(36), ForeignKey("attendance_import_batches.id", ondelete="CASCADE"), nullable=False, index=True)
    row_no = Column(Integer, nullable=False)

    raw_values = Column(JSON, nullable=False)
    normalized_values = Column(JSON, nullable=True)

    employee_no = Column(String(50), nullable=True, index=True)
    event_at_str = Column(String(50), nullable=True)
    event_type = Column(String(20), nullable=True)
    device_id = Column(String(50), nullable=True)
    source_event_id = Column(String(100), nullable=True)

    # 狀態：VALID, INVALID, SKIPPED_DUPLICATE, COMMITTED
    status = Column(String(20), default="VALID", nullable=False)
    error_codes = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    batch = relationship("AttendanceImportBatch", back_populates="rows")


class AttendanceEvent(Base):
    """出勤原始打卡事件 (Attendance Events - 不可覆寫，純追加紀錄)"""
    __tablename__ = "attendance_events"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # 打卡時間：UTC 時間戳與來源時區
    event_at = Column(DateTime(timezone=True), nullable=False, index=True)
    source_timezone = Column(String(50), nullable=False)
    raw_event_at_str = Column(String(50), nullable=False)

    # 打卡類型：CHECK_IN (上班), CHECK_OUT (下班), BREAK_START (外出/午休), BREAK_END (返回), OTHER (其他)
    event_type = Column(String(20), default="CHECK_IN", nullable=False)

    # 設備與來源事件編號
    device_id = Column(String(50), nullable=True, index=True)
    source_event_id = Column(String(100), nullable=True, index=True)
    row_hash = Column(String(64), nullable=True, index=True)

    # 歸屬工作日期 (跨夜班排班歸屬，非直接取 UTC 日期)
    work_date = Column(Date, nullable=False, index=True)
    is_overnight = Column(Boolean, default=False, nullable=False)

    batch_id = Column(String(36), ForeignKey("attendance_import_batches.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # 異常標記
    is_abnormal = Column(Boolean, default=False, nullable=False)
    abnormal_reason = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        Index("ix_attendance_event_natural", "company_id", "employee_id", "event_at", unique=True),
        Index("ix_attendance_event_device", "company_id", "device_id", "source_event_id"),
    )


class AttendanceCorrection(Base):
    """考勤打卡修正紀錄 (Attendance Corrections - 補打卡與時間調整審計留痕，不覆寫原始打卡)"""
    __tablename__ = "attendance_corrections"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    original_event_id = Column(String(36), ForeignKey("attendance_events.id", ondelete="SET NULL"), nullable=True, index=True)

    work_date = Column(Date, nullable=False, index=True)
    # 修正類型：SUPPLEMENT (補打卡), MODIFY (修改時間), VOID (作廢標記)
    correction_type = Column(String(20), nullable=False)
    
    corrected_event_at = Column(DateTime(timezone=True), nullable=False)
    event_type = Column(String(20), nullable=False)
    reason = Column(Text, nullable=False)

    # 審批狀態：APPROVED (核准生效), REJECTED (退回), CANCELLED (撤回)
    status = Column(String(20), default="APPROVED", nullable=False)
    approved_by = Column(String(36), nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class AttendanceDailySummary(Base):
    """每日考勤匯總 (Attendance Daily Summaries - 日常出勤匯總統計)"""
    __tablename__ = "attendance_daily_summaries"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    work_date = Column(Date, nullable=False, index=True)
    
    shift_id = Column(String(50), ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True)
    first_check_in = Column(DateTime(timezone=True), nullable=True)
    last_check_out = Column(DateTime(timezone=True), nullable=True)
    
    total_punches = Column(Integer, default=0, nullable=False)
    work_minutes = Column(Integer, default=0, nullable=False)

    # 狀態：NORMAL (正常), LATE (遲到), EARLY_LEAVE (早退), MISSING_PUNCH (缺卡), ABSENT (曠職), REST_DAY (休息日)
    status = Column(String(20), default="NORMAL", nullable=False)
    notes = Column(String(255), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("company_id", "employee_id", "work_date", name="uq_emp_daily_summary"),
    )
