from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, status, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.errors import AppException
from app.api.deps import get_current_user, get_current_session
from app.models.auth import User, Session as UserSession
from app.models.hr import Employee
from app.models.workflow import (
    WorkflowInstance,
    WorkflowNodeInstance,
    ApprovalAssignment,
    ApprovalAction,
)
from app.core.workflow_engine import WorkflowEngine

router = APIRouter(prefix="/workflows", tags=["Workflows"])


class WorkflowSubmitRequest(BaseModel):
    company_id: str
    document_type: str  # LEAVE, EXPENSE, PAYMENT, TRAVEL, SEAL, CONTRACT, OVERTIME
    document_id: str
    context: Dict[str, Any]  # 例如 {"days": 4, "amount": 12000, "agent_employee_id": "...", ...}


class WorkflowActionRequest(BaseModel):
    action: str = Field(description="APPROVE, REJECT, RETURN")
    comments: Optional[str] = None


@router.post("/submit", status_code=status.HTTP_201_CREATED)
def submit_workflow(
    req: WorkflowSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """送審單據，產生流程快照並進入審核"""
    if not current_user.employee_id:
        raise AppException(
            code="USER_NOT_LINKED_EMPLOYEE",
            message="當前帳號未綁定員工身分，無法作為申請人送審",
            status_code=400,
        )

    instance = WorkflowEngine.submit_document(
        db=db,
        company_id=req.company_id,
        document_type=req.document_type,
        document_id=req.document_id,
        applicant_employee_id=current_user.employee_id,
        context=req.context,
    )
    return {
        "status": "success",
        "instance_id": instance.id,
        "document_id": instance.document_id,
        "workflow_status": instance.status,
        "total_nodes": instance.total_nodes,
    }


@router.get("/inbox")
def get_user_inbox(
    current_user: User = Depends(get_current_user),
    session: UserSession = Depends(get_current_session),
    db: DbSession = Depends(get_db),
):
    """查詢當前登入使用者的待簽收件匣 (Inbox)"""
    if not current_user.employee_id:
        return []

    stmt = (
        select(ApprovalAssignment, WorkflowInstance, WorkflowNodeInstance)
        .join(WorkflowInstance, WorkflowInstance.id == ApprovalAssignment.instance_id)
        .join(WorkflowNodeInstance, WorkflowNodeInstance.id == ApprovalAssignment.node_instance_id)
        .where(
            ApprovalAssignment.assigned_employee_id == current_user.employee_id,
            ApprovalAssignment.is_completed == False,
            WorkflowInstance.company_id == session.active_company_id,
        )
        .order_by(ApprovalAssignment.assigned_at.desc())
    )
    results = db.execute(stmt).all()

    inbox_items = []
    for assign, inst, node in results:
        inbox_items.append({
            "assignment_id": assign.id,
            "instance_id": inst.id,
            "document_type": inst.document_type,
            "document_id": inst.document_id,
            "node_name": node.node_name,
            "assigned_at": assign.assigned_at.isoformat(),
            "snapshot_summary": inst.snapshot_data.get("context", {}),
        })

    return inbox_items


@router.get("/instances/{instance_id}")
def get_workflow_instance(
    instance_id: str,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """查詢單一簽核實例、節點歷程與動作審計"""
    instance = db.get(WorkflowInstance, instance_id)
    if not instance:
        raise AppException(code="INSTANCE_NOT_FOUND", message="找不到指定簽核實例", status_code=404)

    nodes = (
        db.execute(
            select(WorkflowNodeInstance)
            .where(WorkflowNodeInstance.instance_id == instance.id)
            .order_by(WorkflowNodeInstance.node_index.asc())
        )
        .scalars()
        .all()
    )

    node_list = []
    for n in nodes:
        node_list.append({
            "node_index": n.node_index,
            "node_name": n.node_name,
            "node_type": n.node_type,
            "status": n.status,
            "completed_at": n.completed_at.isoformat() if n.completed_at else None,
        })

    return {
        "id": instance.id,
        "company_id": instance.company_id,
        "document_type": instance.document_type,
        "document_id": instance.document_id,
        "applicant_employee_id": instance.applicant_employee_id,
        "status": instance.status,
        "current_node_index": instance.current_node_index,
        "total_nodes": instance.total_nodes,
        "nodes": node_list,
        "snapshot_data": instance.snapshot_data,
        "version": instance.version,
    }


@router.post("/assignments/{assignment_id}/actions")
def execute_workflow_action(
    assignment_id: str,
    req: WorkflowActionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """執行簽核動作 (核准 APPROVE / 駁回 REJECT / 退回 RETURN)"""
    if not current_user.employee_id:
        raise AppException(
            code="USER_NOT_LINKED_EMPLOYEE",
            message="當前帳號未綁定員工身分，無法執行審核",
            status_code=403,
        )

    client_ip = request.client.host if request.client else None

    instance = WorkflowEngine.execute_action(
        db=db,
        assignment_id=assignment_id,
        operator_employee_id=current_user.employee_id,
        action=req.action,
        comments=req.comments,
        client_ip=client_ip,
    )

    return {
        "status": "success",
        "instance_id": instance.id,
        "workflow_status": instance.status,
        "current_node_index": instance.current_node_index,
        "total_nodes": instance.total_nodes,
    }
