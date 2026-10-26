import uuid
from typing import Optional
from datetime import datetime, date, timezone
from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    Date,
    Time,
    ForeignKey,
    Integer,
    Text,
    JSON,
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Person(Base):
    """人員個資主檔 (Persons - 集團自然人主體，可跨多公司任職)"""
    __tablename__ = "persons"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    national_id = Column(String(50), nullable=True, index=True)  # 法定身分證字號 / 居留證號 / 個人番号 (集團自然人身分代號)
    full_name = Column(String(100), nullable=False)
    english_name = Column(String(100), nullable=True)
    birth_date = Column(Date, nullable=True)                      # 出生年月日
    gender = Column(String(20), default="NOT_SPECIFIED", nullable=False)  # MALE, FEMALE, OTHER, NOT_SPECIFIED
    nationality = Column(String(50), nullable=True)              # 國籍 (TW, JP, US)
    marital_status = Column(String(20), default="SINGLE", nullable=False)  # SINGLE, MARRIED

    # 生理與生活設定 (依標準新進員工基本資料表)
    blood_type = Column(String(10), nullable=True)               # 血型 (A, B, O, AB 等)
    military_service_status = Column(String(30), nullable=True)  # 役別 (免役, 役畢, 未役, 服役中)
    driving_licenses = Column(String(100), nullable=True)        # 持有駕照 (機車, 小客車等)
    transportation_modes = Column(String(100), nullable=True)    # 通勤交通工具 (機車、大眾運輸等)
    height_cm = Column(Integer, nullable=True)                   # 身高 (公分)
    weight_kg = Column(Integer, nullable=True)                   # 體重 (公斤)

    # 私人聯絡通訊
    contact_phone = Column(String(30), nullable=True)            # 市話/聯絡電話
    personal_email = Column(String(255), nullable=True)          # 私人 Email
    mobile_phone = Column(String(30), nullable=True)             # 行動電話
    residential_address = Column(String(255), nullable=True)     # 通訊居住地址
    permanent_address = Column(String(255), nullable=True)       # 戶籍法定地址

    # 緊急聯絡人
    emergency_contact_name = Column(String(50), nullable=True)
    emergency_contact_relationship = Column(String(30), nullable=True)
    emergency_contact_phone = Column(String(30), nullable=True)   # 緊急聯絡人市話
    emergency_contact_mobile = Column(String(30), nullable=True)  # 緊急聯絡人行動電話

    # 學歷與工作經歷 (結構化歷程)
    education_history = Column(JSON, nullable=True)              # 學歷清單 (學校名稱, 科系, 入校年份, 離校年份, 畢肄業)
    work_experience = Column(JSON, nullable=True)                # 工作經歷清單 (服務單位, 職稱, 工作說明, 年資)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    employments = relationship("Employee", back_populates="person")


class Company(Base):
    """公司主檔 (Companies - 台灣總部 ETJ-TW / 福岡支社 ETJ-JP)"""
    __tablename__ = "companies"

    id = Column(String(50), primary_key=True)  # ETJ-TW, ETJ-JP
    name = Column(String(100), nullable=False)
    tax_id = Column(String(50), nullable=True)  # 統一編號 / 法人番号 / 稅籍號
    representative_name = Column(String(100), nullable=True)  # 代表人 / 代表取締役
    registered_address = Column(String(255), nullable=True)  # 公司登記地址
    contact_phone = Column(String(50), nullable=True)  # 總機電話
    default_timezone = Column(String(50), nullable=False, default="Asia/Taipei")
    default_currency = Column(String(10), nullable=False, default="TWD")
    is_active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    organizations = relationship("Organization", back_populates="company", cascade="all, delete-orphan")
    employees = relationship("Employee", back_populates="company", cascade="all, delete-orphan")


class Organization(Base):
    """組織階層主檔 (Organizations - 部、處、課，禁止循環階層)"""
    __tablename__ = "organizations"

    id = Column(String(50), primary_key=True)  # 例如 ORG-RD-01
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    parent_id = Column(String(50), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=True, index=True)
    level = Column(String(20), nullable=False, default="DEPARTMENT")  # CHAIRMAN 董事長, CEO 執行長, GM 總經理, CENTER 中心, DIVISION 處, DEPARTMENT 部, SECTION 課, TEAM 組
    effective_date = Column(Date, nullable=True)  # 生效起始日期 (Effective Date)
    expiry_date = Column(Date, nullable=True)  # 失效截止日期 (Expiry Date, None 表示永久有效)
    manager_id = Column(String(36), ForeignKey("employees.id", ondelete="SET NULL", use_alter=True), nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    company = relationship("Company", back_populates="organizations")
    parent = relationship("Organization", remote_side=[id], backref="children")
    employees = relationship("Employee", back_populates="organization", foreign_keys="Employee.organization_id")
    manager = relationship("Employee", foreign_keys=[manager_id], post_update=True)

    @property
    def manager_name(self) -> Optional[str]:
        return self.manager.full_name if self.manager else None

    @property
    def manager_no(self) -> Optional[str]:
        return self.manager.employee_no if self.manager else None

    __table_args__ = (
        UniqueConstraint("company_id", "code", name="uq_company_org_code"),
    )


class Employee(Base):
    """員工主檔 (Employees - 帳號與員工分離設計)"""
    __tablename__ = "employees"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    person_id = Column(String(36), ForeignKey("persons.id", ondelete="RESTRICT"), nullable=True, index=True)
    employee_no = Column(String(50), nullable=False, index=True)  # 公司內部員工工號 (例如 TW001, JP001)
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    organization_id = Column(String(50), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    full_name = Column(String(100), nullable=False)
    english_name = Column(String(100), nullable=True)
    national_id = Column(String(50), nullable=True, index=True)  # 法定身分證字號 / 居留證號 / 個人番号 (敏感個資)
    birth_date = Column(Date, nullable=True)                      # 出生年月日 (Date-only)
    gender = Column(String(20), default="NOT_SPECIFIED", nullable=False)  # MALE, FEMALE, OTHER, NOT_SPECIFIED
    nationality = Column(String(50), nullable=True)              # 國籍 (例如 TW, JP, US)
    marital_status = Column(String(20), default="SINGLE", nullable=False)  # SINGLE, MARRIED

    # 聯絡與通訊資訊
    email = Column(String(255), nullable=False)                  # 公務 Email
    personal_email = Column(String(255), nullable=True)          # 私人 Email
    mobile_phone = Column(String(30), nullable=True)             # 行動電話
    residential_address = Column(String(255), nullable=True)     # 通訊居住地址
    permanent_address = Column(String(255), nullable=True)       # 戶籍法定地址

    # 緊急聯絡人
    emergency_contact_name = Column(String(50), nullable=True)
    emergency_contact_relationship = Column(String(30), nullable=True)
    emergency_contact_phone = Column(String(30), nullable=True)

    # 職務與聘僱
    job_title = Column(String(100), nullable=True)               # 職稱 (例如 高級工程師)
    job_grade = Column(String(20), nullable=True)                # 職等職級 (例如 P3, M2)
    employment_type = Column(String(20), default="REGULAR", nullable=False)  # REGULAR, CONTRACT, INTERN, PART_TIME
    default_shift_id = Column(String(50), ForeignKey("shifts.id", ondelete="SET NULL"), nullable=True)

    # 生命週期日期
    hire_date = Column(Date, nullable=False)
    probation_end_date = Column(Date, nullable=True)             # 試用期滿日
    resign_date = Column(Date, nullable=True)
    
    status = Column(String(20), default="ACTIVE", nullable=False)  # ACTIVE, ON_LEAVE, RESIGNED
    version = Column(Integer, default=1, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    company = relationship("Company", back_populates="employees")
    organization = relationship("Organization", back_populates="employees", foreign_keys=[organization_id])
    person = relationship("Person", back_populates="employments")
    default_shift = relationship("Shift", foreign_keys=[default_shift_id])
    manager_relations = relationship("ManagerRelation", foreign_keys="ManagerRelation.employee_id", back_populates="employee", cascade="all, delete-orphan")
    changes = relationship("EmployeeChange", back_populates="employee", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("company_id", "employee_no", name="uq_company_employee_no"),
    )


class ManagerRelation(Base):
    """主管關係鏈 (Manager Relations - 禁止循環與利益衝突)"""
    __tablename__ = "manager_relations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id = Column(String(36), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    manager_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    relation_type = Column(String(20), default="DIRECT", nullable=False)  # DIRECT (直屬主管), SECOND_LEVEL (第二層), THIRD_LEVEL (第三層)
    
    effective_from = Column(Date, nullable=False)
    effective_to = Column(Date, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    employee = relationship("Employee", foreign_keys=[employee_id], back_populates="manager_relations")
    manager = relationship("Employee", foreign_keys=[manager_id])


class EmployeeChange(Base):
    """員工異動紀錄 (Employee Changes - 報到、調職、離職生效歷程)"""
    __tablename__ = "employee_changes"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    employee_id = Column(String(36), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    change_type = Column(String(20), nullable=False)  # ONBOARD 報到, TRANSFER 調職, PROMOTION 晉升, RESIGN 離職
    effective_date = Column(Date, nullable=False)
    
    before_organization_id = Column(String(50), nullable=True)
    after_organization_id = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    employee = relationship("Employee", back_populates="changes")


class Shift(Base):
    """班別主檔 (Shifts)"""
    __tablename__ = "shifts"

    id = Column(String(50), primary_key=True)  # 例如 SHIFT-STANDARD-8H
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    code = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    
    work_start_time = Column(String(5), nullable=False)  # HH:mm, 例如 "09:00"
    work_end_time = Column(String(5), nullable=False)    # HH:mm, 例如 "18:00"
    break_start_time = Column(String(5), nullable=True)  # HH:mm, 例如 "12:00"
    break_end_time = Column(String(5), nullable=True)    # HH:mm, 例如 "13:00"
    break_minutes = Column(Integer, default=60, nullable=False)
    daily_standard_minutes = Column(Integer, default=480, nullable=False)  # 8小時 = 480分鐘
    flex_minutes = Column(Integer, default=0, nullable=False)              # 彈性工時分鐘數 (例如 30 分鐘)
    is_overnight = Column(Boolean, default=False, nullable=False)         # 是否跨夜班
    timezone = Column(String(50), default="Asia/Taipei", nullable=False)   # 班別適用時區 (例如 Asia/Taipei, Asia/Tokyo)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=True)


class CalendarDay(Base):
    """工作日曆 (Calendar Days - 依公司與時區獨立設定，date-only)"""
    __tablename__ = "calendar_days"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    calendar_date = Column(Date, nullable=False, index=True)  # Date-only, 不被時區偏移污染
    is_working_day = Column(Boolean, default=True, nullable=False)
    holiday_name = Column(String(100), nullable=True)
    day_type = Column(String(20), default="REGULAR", nullable=False)  # REGULAR 一般工作日, WEEKEND 例假, NATIONAL_HOLIDAY 國定假日

    __table_args__ = (
        UniqueConstraint("company_id", "calendar_date", name="uq_company_calendar_date"),
    )


class LeaveType(Base):
    """假別主檔 (Leave Types - 全域通用不分公司)"""
    __tablename__ = "leave_types"

    id = Column(String(50), primary_key=True)  # 例如 ANNUAL 特別休假, SICK 普通傷病假, PERSONAL 事假
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True, index=True)
    code = Column(String(50), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)
    unit = Column(String(10), default="MINUTES", nullable=False)  # MINUTES 或 DAYS
    requires_attachment = Column(Boolean, default=False, nullable=False)
    is_paid = Column(Boolean, default=True, nullable=False)
    paid_type = Column(String(10), default="FULL", nullable=False)  # FULL (全薪), HALF (半薪), UNPAID (不給薪)
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    __table_args__ = (
        UniqueConstraint("code", name="uq_leave_types_code"),
    )


class LeaveLedger(Base):
    """假額不可變帳本 (Leave Ledger - 僅追加紀錄，不直接覆寫剩餘值)"""
    __tablename__ = "leave_ledger"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    employee_id = Column(String(36), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    leave_type_id = Column(String(50), ForeignKey("leave_types.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 帳本交易類型：GRANT (給予假額), HOLD (申請中預占), COMMIT (簽核核准扣抵), RELEASE (退回/撤銷釋放預占), CANCEL (已核准假單註銷沖銷)
    entry_type = Column(String(20), nullable=False)
    
    # 異動分鐘數 (GRANT 為正數，COMMIT/HOLD 為負數，RELEASE 為正數)
    amount_minutes = Column(Integer, nullable=False)
    balance_after_minutes = Column(Integer, nullable=False)
    
    reference_doc_id = Column(String(50), nullable=True, index=True)  # 關聯請假申請單號或給假批號
    valid_from = Column(Date, nullable=False)
    valid_to = Column(Date, nullable=False)
    
    notes = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    created_by = Column(String(36), nullable=False)
