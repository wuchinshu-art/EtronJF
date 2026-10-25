from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, status, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from app.core.database import get_db
from app.core.errors import AppException
from app.api.deps import get_current_user
from app.models.auth import User
from app.models.hr import Employee
from app.models.overtime import OvertimeRequest
from app.models.workflow import WorkflowInstance
from app.core.overtime_calculator import calculate_overtime_minutes
from app.core.overtime_service import OvertimeService

router = APIRouter(prefix="/overtime", tags=["Overtime"])


class OvertimeCalculateRequest(BaseModel):
    employee_id: str
    start_time: datetime
    end_time: datetime
    rest_minutes: int = 0
    compensation_type: str = "COMPENSATORY_LEAVE"


class OvertimeCreateRequest(BaseModel):
    company_id: str
    employee_id: str
    start_time: datetime
    end_time: datetime
    reason: str
    rest_minutes: int = 0
    compensation_type: str = "COMPENSATORY_LEAVE"


class OvertimeSubmitRequest(BaseModel):
    hr_window_employee_id: Optional[str] = None


class OvertimeApprovalActionRequest(BaseModel):
    action: str = Field(description="APPROVE, REJECT, RETURN")
    comments: Optional[str] = None


@router.post("/calculate", status_code=status.HTTP_200_OK)
def calculate_overtime(
    req: OvertimeCalculateRequest,
    db: DbSession = Depends(get_db),
):
    """加班時數、級距與補休試算"""
    employee = db.get(Employee, req.employee_id)
    if not employee:
        raise AppException(code="EMPLOYEE_NOT_FOUND", message="找不到員工資料", status_code=404)

    result = calculate_overtime_minutes(
        db=db,
        employee=employee,
        start_time_utc=req.start_time,
        end_time_utc=req.end_time,
        rest_minutes=req.rest_minutes,
        compensation_type=req.compensation_type,
    )
    return {
        "status": "success",
        "employee_id": req.employee_id,
        "calculation": result,
    }


@router.post("/requests", status_code=status.HTTP_201_CREATED)
def create_overtime_request(
    req: OvertimeCreateRequest,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """建立加班申請單草稿"""
    operator_emp_id = current_user.employee_id or req.employee_id
    ot_req = OvertimeService.create_overtime_request(
        db=db,
        company_id=req.company_id,
        employee_id=operator_emp_id,
        start_time_utc=req.start_time,
        end_time_utc=req.end_time,
        reason=req.reason,
        rest_minutes=req.rest_minutes,
        compensation_type=req.compensation_type,
    )
    return {
        "status": "success",
        "request_id": ot_req.id,
        "request_number": ot_req.request_number,
        "total_minutes": ot_req.total_minutes,
        "comp_leave_minutes": ot_req.comp_leave_minutes,
        "day_type": ot_req.day_type,
        "overtime_status": ot_req.status,
    }


@router.post("/requests/{request_id}/submit", status_code=status.HTTP_200_OK)
def submit_overtime_request(
    request_id: str,
    req: OvertimeSubmitRequest,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """送審加班單，啟動直屬主管與人事窗口審批管線"""
    ot_req = db.get(OvertimeRequest, request_id)
    if not ot_req:
        raise AppException(code="OVERTIME_REQUEST_NOT_FOUND", message="找不到加班單", status_code=404)

    operator_emp_id = current_user.employee_id or ot_req.employee_id
    updated_req = OvertimeService.submit_overtime_request(
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
        "overtime_status": updated_req.status,
    }


@router.get("/requests/{request_id}", status_code=status.HTTP_200_OK)
def get_overtime_request_detail(
    request_id: str,
    db: DbSession = Depends(get_db),
):
    """取得加班單詳情與簽核實例狀態"""
    ot_req = db.get(OvertimeRequest, request_id)
    if not ot_req:
        raise AppException(code="OVERTIME_REQUEST_NOT_FOUND", message="找不到加班單", status_code=404)

    wf_instance = None
    if ot_req.workflow_instance_id:
        wf_instance = db.get(WorkflowInstance, ot_req.workflow_instance_id)

    return {
        "id": ot_req.id,
        "company_id": ot_req.company_id,
        "employee_id": ot_req.employee_id,
        "request_number": ot_req.request_number,
        "start_time": ot_req.start_time.isoformat(),
        "end_time": ot_req.end_time.isoformat(),
        "rest_minutes": ot_req.rest_minutes,
        "total_minutes": ot_req.total_minutes,
        "day_type": ot_req.day_type,
        "compensation_type": ot_req.compensation_type,
        "comp_leave_minutes": ot_req.comp_leave_minutes,
        "reason": ot_req.reason,
        "status": ot_req.status,
        "revision": ot_req.revision,
        "workflow_instance": {
            "id": wf_instance.id,
            "status": wf_instance.status,
            "current_node_index": wf_instance.current_node_index,
            "total_nodes": wf_instance.total_nodes,
            "snapshot_data": wf_instance.snapshot_data,
        } if wf_instance else None,
    }


@router.post("/requests/{request_id}/cancel", status_code=status.HTTP_200_OK)
def cancel_overtime_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """申請人抽單／撤回未核准加班單"""
    ot_req = db.get(OvertimeRequest, request_id)
    if not ot_req:
        raise AppException(code="OVERTIME_REQUEST_NOT_FOUND", message="找不到加班單", status_code=404)

    operator_emp_id = current_user.employee_id or ot_req.employee_id
    updated_req = OvertimeService.cancel_overtime_request(
        db=db,
        request_id=request_id,
        operator_employee_id=operator_emp_id,
    )
    return {
        "status": "success",
        "request_id": updated_req.id,
        "overtime_status": updated_req.status,
    }


@router.post("/assignments/{assignment_id}/action", status_code=status.HTTP_200_OK)
def process_overtime_approval_action(
    assignment_id: str,
    req: OvertimeApprovalActionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """加班單簽核動作推進（核准、駁回、退回）並連動補休假額入帳"""
    if not current_user.employee_id:
        raise AppException(code="USER_NOT_LINKED_EMPLOYEE", message="帳號未綁定員工身分", status_code=400)

    updated_req = OvertimeService.process_approval(
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
        "overtime_status": updated_req.status,
    }
