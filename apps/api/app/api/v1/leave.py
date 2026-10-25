from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, status, Request
from pydantic import BaseModel, Field
from decimal import Decimal
from sqlalchemy.orm import Session as DbSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.errors import AppException
from app.api.deps import get_current_user
from app.models.auth import User
from app.models.hr import Employee
from app.models.leave import LeaveRequest
from app.models.workflow import WorkflowInstance, ApprovalAssignment
from app.core.leave_calculator import calculate_leave_minutes_and_days, check_leave_overlap
from app.core.leave_service import LeaveService

router = APIRouter(prefix="/leave", tags=["Leave"])


class LeaveCalculateRequest(BaseModel):
    employee_id: str
    start_time: datetime
    end_time: datetime


class LeaveCreateRequest(BaseModel):
    company_id: str
    employee_id: str
    leave_type_id: str
    start_time: datetime
    end_time: datetime
    reason: str
    deputy_employee_id: Optional[str] = None
    attachment_url: Optional[str] = None


class LeaveSubmitRequest(BaseModel):
    hr_window_employee_id: Optional[str] = None


class LeaveApprovalActionRequest(BaseModel):
    action: str = Field(description="APPROVE, REJECT, RETURN")
    comments: Optional[str] = None


@router.post("/calculate", status_code=status.HTTP_200_OK)
def calculate_leave(
    req: LeaveCalculateRequest,
    db: DbSession = Depends(get_db),
):
    """請假工時試算：跳過休息時間、例假日與非工作日"""
    employee = db.get(Employee, req.employee_id)
    if not employee:
        raise AppException(code="EMPLOYEE_NOT_FOUND", message="找不到員工資料", status_code=404)

    total_minutes, calculated_days = calculate_leave_minutes_and_days(
        db=db,
        employee=employee,
        start_time_utc=req.start_time,
        end_time_utc=req.end_time,
    )
    return {
        "status": "success",
        "employee_id": req.employee_id,
        "total_minutes": total_minutes,
        "calculated_days": float(calculated_days),
    }


@router.post("/requests", status_code=status.HTTP_201_CREATED)
def create_leave_request(
    req: LeaveCreateRequest,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """建立請假申請單草稿"""
    operator_emp_id = current_user.employee_id or req.employee_id
    leave_req = LeaveService.create_leave_request(
        db=db,
        company_id=req.company_id,
        employee_id=operator_emp_id,
        leave_type_id=req.leave_type_id,
        start_time_utc=req.start_time,
        end_time_utc=req.end_time,
        reason=req.reason,
        deputy_employee_id=req.deputy_employee_id,
        attachment_url=req.attachment_url,
    )
    return {
        "status": "success",
        "request_id": leave_req.id,
        "request_number": leave_req.request_number,
        "total_minutes": leave_req.total_minutes,
        "calculated_days": float(leave_req.calculated_days),
        "leave_status": leave_req.status,
    }


@router.post("/requests/{request_id}/submit", status_code=status.HTTP_200_OK)
def submit_leave_request(
    request_id: str,
    req: LeaveSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """送審請假單：假額預占 (HOLD) + 主管鏈簽核啟動"""
    leave_req = db.get(LeaveRequest, request_id)
    if not leave_req:
        raise AppException(code="LEAVE_REQUEST_NOT_FOUND", message="找不到請假單", status_code=404)

    operator_emp_id = current_user.employee_id or leave_req.employee_id

    updated_req = LeaveService.submit_leave_request(
        db=db,
        request_id=request_id,
        operator_employee_id=operator_emp_id,
        hr_window_employee_id=req.hr_window_employee_id,
    )
    return {
        "status": "success",
        "request_id": updated_req.id,
        "request_number": updated_req.request_number,
        "workflow_instance_id": updated_req.workflow_instance_id,
        "leave_status": updated_req.status,
    }


@router.get("/requests/{request_id}", status_code=status.HTTP_200_OK)
def get_leave_request_detail(
    request_id: str,
    db: DbSession = Depends(get_db),
):
    """取得請假單詳細資訊與簽核實例狀態"""
    leave_req = db.get(LeaveRequest, request_id)
    if not leave_req:
        raise AppException(code="LEAVE_REQUEST_NOT_FOUND", message="找不到請假單", status_code=404)

    wf_instance = None
    if leave_req.workflow_instance_id:
        wf_instance = db.get(WorkflowInstance, leave_req.workflow_instance_id)

    return {
        "id": leave_req.id,
        "company_id": leave_req.company_id,
        "employee_id": leave_req.employee_id,
        "leave_type_id": leave_req.leave_type_id,
        "request_number": leave_req.request_number,
        "start_time": leave_req.start_time.isoformat(),
        "end_time": leave_req.end_time.isoformat(),
        "total_minutes": leave_req.total_minutes,
        "calculated_days": float(leave_req.calculated_days),
        "reason": leave_req.reason,
        "deputy_employee_id": leave_req.deputy_employee_id,
        "attachment_url": leave_req.attachment_url,
        "status": leave_req.status,
        "revision": leave_req.revision,
        "workflow_instance": {
            "id": wf_instance.id,
            "status": wf_instance.status,
            "current_node_index": wf_instance.current_node_index,
            "total_nodes": wf_instance.total_nodes,
            "snapshot_data": wf_instance.snapshot_data,
        } if wf_instance else None,
    }


@router.post("/requests/{request_id}/cancel", status_code=status.HTTP_200_OK)
def cancel_leave_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """申請人抽單／撤回未核准假單，釋放假額預占"""
    leave_req = db.get(LeaveRequest, request_id)
    if not leave_req:
        raise AppException(code="LEAVE_REQUEST_NOT_FOUND", message="找不到請假單", status_code=404)

    operator_emp_id = current_user.employee_id or leave_req.employee_id
    updated_req = LeaveService.cancel_leave_request(
        db=db,
        request_id=request_id,
        operator_employee_id=operator_emp_id,
    )
    return {
        "status": "success",
        "request_id": updated_req.id,
        "leave_status": updated_req.status,
    }


@router.post("/assignments/{assignment_id}/action", status_code=status.HTTP_200_OK)
def process_leave_approval_action(
    assignment_id: str,
    req: LeaveApprovalActionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """
    請假單簽核動作推進（核准、駁回、退回）並連動假額帳本
    """
    if not current_user.employee_id:
        raise AppException(code="USER_NOT_LINKED_EMPLOYEE", message="帳號未綁定員工身分", status_code=400)

    updated_req = LeaveService.process_approval(
        db=db,
        assignment_id=assignment_id,
        operator_employee_id=current_user.employee_id,
        action=req.action,
        comments=req.comments,
        client_ip=request.client.host if request.client else None,
    )
    return {
        "status": "success",
        "request_id": updated_req.id,
        "leave_status": updated_req.status,
    }


@router.get("/requests", status_code=status.HTTP_200_OK)
def list_leave_requests(
    company_id: Optional[str] = None,
    employee_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """查詢請假申請單清單"""
    query = db.query(LeaveRequest)
    if company_id:
        query = query.filter(LeaveRequest.company_id == company_id)
    if employee_id:
        query = query.filter(LeaveRequest.employee_id == employee_id)
    if status:
        query = query.filter(LeaveRequest.status == status)

    results = query.order_by(LeaveRequest.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "company_id": r.company_id,
            "employee_id": r.employee_id,
            "leave_type_id": r.leave_type_id,
            "request_number": r.request_number,
            "start_time": r.start_time.isoformat(),
            "end_time": r.end_time.isoformat(),
            "total_minutes": r.total_minutes,
            "calculated_days": float(r.calculated_days),
            "reason": r.reason,
            "deputy_employee_id": r.deputy_employee_id,
            "status": r.status,
            "created_at": r.created_at.isoformat(),
        }
        for r in results
    ]

