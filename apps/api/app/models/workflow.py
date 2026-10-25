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
    Index,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class WorkflowDefinition(Base):
    """流程定義 (Workflow Definitions - 例如 LEAVE, EXPENSE, PAYMENT 等)"""
    __tablename__ = "workflow_definitions"

    id = Column(String(50), primary_key=True)  # LEAVE, EXPENSE, PAYMENT, TRAVEL, SEAL, CONTRACT, OVERTIME
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    versions = relationship("WorkflowVersion", back_populates="definition", cascade="all, delete-orphan")


class WorkflowVersion(Base):
    """流程版本 (Workflow Versions - 簽核規則版本化)"""
    __tablename__ = "workflow_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    definition_id = Column(String(50), ForeignKey("workflow_definitions.id", ondelete="CASCADE"), nullable=False, index=True)
    version_num = Column(Integer, nullable=False)
    nodes_config = Column(JSON, nullable=False)  # 存放節點定義、門檻條件與受派規則
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    definition = relationship("WorkflowDefinition", back_populates="versions")

    __table_args__ = (
        UniqueConstraint("definition_id", "version_num", name="uq_wf_definition_version"),
    )


class WorkflowInstance(Base):
    """簽核實例 (Workflow Instances - 每一張申請單對應之簽核執行狀態)"""
    __tablename__ = "workflow_instances"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    company_id = Column(String(50), nullable=False, index=True)
    document_type = Column(String(50), nullable=False, index=True)  # LEAVE, EXPENSE, etc.
    document_id = Column(String(50), nullable=False, index=True)    # 業務單據 ID (例 LV-202610-001)
    
    applicant_employee_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    workflow_version_id = Column(String(36), ForeignKey("workflow_versions.id", ondelete="RESTRICT"), nullable=False)
    
    # 狀態機：DRAFT, SUBMITTED, IN_REVIEW, APPROVED, REJECTED, RETURNED, CANCELLED
    status = Column(String(20), default="SUBMITTED", nullable=False, index=True)
    current_node_index = Column(Integer, default=0, nullable=False)
    total_nodes = Column(Integer, nullable=False)
    
    # 送審時凍結快照 (Snapshot - 包含組織、主管鏈、金額門檻與幣別)，後續異動主檔不回溯影響既有單據！
    snapshot_data = Column(JSON, nullable=False)
    version = Column(Integer, default=1, nullable=False)  # 樂觀鎖防止重複推進
    
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    node_instances = relationship("WorkflowNodeInstance", back_populates="instance", cascade="all, delete-orphan")


class WorkflowNodeInstance(Base):
    """簽核節點實例快照 (Workflow Node Instances)"""
    __tablename__ = "workflow_node_instances"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    instance_id = Column(String(36), ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    node_index = Column(Integer, nullable=False)
    node_name = Column(String(100), nullable=False)
    node_type = Column(String(30), nullable=False)  # MANAGER_DIRECT, MANAGER_LEVEL2, HR_WINDOW, FINANCE_WINDOW, etc.
    
    # 節點狀態：PENDING (待執行), IN_PROGRESS (簽核中), APPROVED (通過), REJECTED (駁回), RETURNED (退回), SKIPPED (門檻略過)
    status = Column(String(20), default="PENDING", nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    instance = relationship("WorkflowInstance", back_populates="node_instances")
    assignments = relationship("ApprovalAssignment", back_populates="node_instance", cascade="all, delete-orphan")


class ApprovalAssignment(Base):
    """待辦受派任務 (Approval Assignments - 呈現在使用者收件匣 Inbox)"""
    __tablename__ = "approval_assignments"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    node_instance_id = Column(String(36), ForeignKey("workflow_node_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    instance_id = Column(String(36), ForeignKey("workflow_instances.id", ondelete="CASCADE"), nullable=False, index=True)
    
    assigned_employee_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    is_completed = Column(Boolean, default=False, nullable=False, index=True)
    
    assigned_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    node_instance = relationship("WorkflowNodeInstance", back_populates="assignments")
    actions = relationship("ApprovalAction", back_populates="assignment", cascade="all, delete-orphan")


class ApprovalAction(Base):
    """簽核動作審計歷程 (Approval Actions)"""
    __tablename__ = "approval_actions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    assignment_id = Column(String(36), ForeignKey("approval_assignments.id", ondelete="CASCADE"), nullable=False, index=True)
    operator_employee_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    
    # 動作：APPROVE (核准), REJECT (駁回), RETURN (退回修改)
    action = Column(String(20), nullable=False)
    comments = Column(Text, nullable=True)
    client_ip = Column(String(45), nullable=True)
    executed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

    assignment = relationship("ApprovalAssignment", back_populates="actions")


class Delegation(Base):
    """職務代理人設定 (Delegations - 職務代理與單據代理分開建模)"""
    __tablename__ = "delegations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    delegator_employee_id = Column(String(36), ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True)
    delegatee_employee_id = Column(String(36), ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True)
    company_id = Column(String(50), nullable=False, index=True)
    
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
