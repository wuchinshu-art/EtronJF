from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, status, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from app.core.database import get_db
from app.core.errors import AppException
from app.api.deps import get_current_user
from app.models.auth import User
from app.models.hr import Employee
from app.models.travel import TravelRequest, TravelSettlement
from app.models.workflow import WorkflowInstance
from app.core.travel_service import TravelService

router = APIRouter(prefix="/travel", tags=["Travel"])


class TravelRequestCreate(BaseModel):
    company_id: str
    employee_id: str
    title: str
    destination: str
    start_date: date
    end_date: date
    estimated_days: Decimal = Decimal("1.00")
    transport_mode: str = "HSR"
    purpose: str
    deputy_employee_id: Optional[str] = None
    has_advance: bool = False
    advance_currency: str = "TWD"
    advance_amount: Decimal = Decimal("0.0000")
    
    # 標準出差申請單擴充欄位
    region_type: str = "DOMESTIC"
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    estimated_nights: int = 0
    transport_modes: Optional[List[str]] = None
    transport_other: Optional[str] = None
    needs_accommodation: bool = False
    accommodation_plan: Optional[str] = None
    companions: Optional[str] = None
    visiting_target: Optional[str] = None
    planned_agenda: Optional[str] = None
    expected_results: Optional[str] = None
    estimated_transport_cost: Decimal = Decimal("0.00")
    estimated_accommodation_cost: Decimal = Decimal("0.00")
    estimated_daily_cost: Decimal = Decimal("0.00")
    estimated_other_cost: Decimal = Decimal("0.00")
    estimated_total_cost: Decimal = Decimal("0.00")
    notes: Optional[str] = None


class TravelRequestSubmit(BaseModel):
    finance_window_employee_id: Optional[str] = None
    hr_window_employee_id: Optional[str] = None


class ExpenseItemInput(BaseModel):
    expense_category: str
    expense_date: date
    currency: str = "TWD"
    exchange_rate: Decimal = Decimal("1.0000")
    amount: Decimal
    invoice_number: Optional[str] = None
    description: str
    attachment_url: Optional[str] = None


class TravelSettlementCreate(BaseModel):
    company_id: str
    employee_id: str
    travel_request_id: str
    currency: str = "TWD"
    exchange_rate: Decimal = Decimal("1.0000")
    items: List[ExpenseItemInput]
    notes: Optional[str] = None


class TravelSettlementSubmit(BaseModel):
    finance_window_employee_id: Optional[str] = None


class PaymentConfirmRequest(BaseModel):
    paid_reference: str


class TravelApprovalActionRequest(BaseModel):
    action: str = Field(description="APPROVE, REJECT, RETURN")
    comments: Optional[str] = None


@router.post("/requests", status_code=status.HTTP_201_CREATED)
def create_travel_request(
    req: TravelRequestCreate,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """建立出差申請單草稿"""
    operator_emp_id = current_user.employee_id or req.employee_id
    travel_req = TravelService.create_travel_request(
        db=db,
        company_id=req.company_id,
        employee_id=operator_emp_id,
        title=req.title,
        destination=req.destination,
        start_date=req.start_date,
        end_date=req.end_date,
        estimated_days=req.estimated_days,
        transport_mode=req.transport_mode,
        purpose=req.purpose,
        deputy_employee_id=req.deputy_employee_id,
        has_advance=req.has_advance,
        advance_currency=req.advance_currency,
        advance_amount=req.advance_amount,
        region_type=req.region_type,
        start_time=req.start_time,
        end_time=req.end_time,
        estimated_nights=req.estimated_nights,
        transport_modes=req.transport_modes,
        transport_other=req.transport_other,
        needs_accommodation=req.needs_accommodation,
        accommodation_plan=req.accommodation_plan,
        companions=req.companions,
        visiting_target=req.visiting_target,
        planned_agenda=req.planned_agenda,
        expected_results=req.expected_results,
        estimated_transport_cost=req.estimated_transport_cost,
        estimated_accommodation_cost=req.estimated_accommodation_cost,
        estimated_daily_cost=req.estimated_daily_cost,
        estimated_other_cost=req.estimated_other_cost,
        estimated_total_cost=req.estimated_total_cost,
        notes=req.notes,
    )
    return {
        "status": "success",
        "request_id": travel_req.id,
        "request_number": travel_req.request_number,
        "has_advance": travel_req.has_advance,
        "advance_amount": float(travel_req.advance_amount),
        "travel_status": travel_req.status,
    }


@router.post("/requests/{request_id}/submit", status_code=status.HTTP_200_OK)
def submit_travel_request(
    request_id: str,
    req: TravelRequestSubmit,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """送審出差申請單（有預支款則啟動會計窗口）"""
    travel_req = db.get(TravelRequest, request_id)
    if not travel_req:
        raise AppException(code="TRAVEL_REQUEST_NOT_FOUND", message="找不到出差單", status_code=404)

    operator_emp_id = current_user.employee_id or travel_req.employee_id
    updated_req = TravelService.submit_travel_request(
        db=db,
        request_id=request_id,
        operator_employee_id=operator_emp_id,
        finance_window_employee_id=req.finance_window_employee_id,
        hr_window_employee_id=req.hr_window_employee_id,
    )
    return {
        "status": "success",
        "request_id": updated_req.id,
        "request_number": updated_req.request_number,
        "workflow_instance_id": updated_req.workflow_instance_id,
        "travel_status": updated_req.status,
    }


@router.get("/requests", status_code=status.HTTP_200_OK)
def list_travel_requests(
    employee_id: Optional[str] = None,
    company_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """查詢出差申請單列表"""
    query = db.query(TravelRequest)
    if employee_id:
        query = query.filter(TravelRequest.employee_id == employee_id)
    if company_id:
        query = query.filter(TravelRequest.company_id == company_id)
    if status:
        query = query.filter(TravelRequest.status == status)

    results = query.order_by(TravelRequest.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "company_id": r.company_id,
            "employee_id": r.employee_id,
            "request_number": r.request_number,
            "title": r.title,
            "destination": r.destination,
            "start_date": r.start_date.isoformat(),
            "end_date": r.end_date.isoformat(),
            "status": r.status,
            "settlement_status": r.settlement_status,
        }
        for r in results
    ]


@router.get("/requests/{request_id}", status_code=status.HTTP_200_OK)
def get_travel_request_detail(
    request_id: str,
    db: DbSession = Depends(get_db),
):
    """取得出差申請單詳情"""
    travel_req = db.get(TravelRequest, request_id)
    if not travel_req:
        raise AppException(code="TRAVEL_REQUEST_NOT_FOUND", message="找不到出差單", status_code=404)

    wf_instance = None
    if travel_req.workflow_instance_id:
        wf_instance = db.get(WorkflowInstance, travel_req.workflow_instance_id)

    return {
        "id": travel_req.id,
        "company_id": travel_req.company_id,
        "employee_id": travel_req.employee_id,
        "request_number": travel_req.request_number,
        "title": travel_req.title,
        "destination": travel_req.destination,
        "start_date": travel_req.start_date.isoformat(),
        "end_date": travel_req.end_date.isoformat(),
        "start_time": travel_req.start_time,
        "end_time": travel_req.end_time,
        "estimated_days": float(travel_req.estimated_days),
        "estimated_nights": travel_req.estimated_nights,
        "region_type": travel_req.region_type,
        "transport_mode": travel_req.transport_mode,
        "transport_modes": travel_req.transport_modes,
        "transport_other": travel_req.transport_other,
        "needs_accommodation": travel_req.needs_accommodation,
        "accommodation_plan": travel_req.accommodation_plan,
        "companions": travel_req.companions,
        "visiting_target": travel_req.visiting_target,
        "planned_agenda": travel_req.planned_agenda,
        "expected_results": travel_req.expected_results,
        "estimated_transport_cost": float(travel_req.estimated_transport_cost or 0),
        "estimated_accommodation_cost": float(travel_req.estimated_accommodation_cost or 0),
        "estimated_daily_cost": float(travel_req.estimated_daily_cost or 0),
        "estimated_other_cost": float(travel_req.estimated_other_cost or 0),
        "estimated_total_cost": float(travel_req.estimated_total_cost or 0),
        "notes": travel_req.notes,
        "purpose": travel_req.purpose,
        "deputy_employee_id": travel_req.deputy_employee_id,
        "has_advance": travel_req.has_advance,
        "advance_currency": travel_req.advance_currency,
        "advance_amount": float(travel_req.advance_amount),
        "status": travel_req.status,
        "settlement_status": travel_req.settlement_status,
        "workflow_instance": {
            "id": wf_instance.id,
            "status": wf_instance.status,
            "current_node_index": wf_instance.current_node_index,
            "total_nodes": wf_instance.total_nodes,
            "snapshot_data": wf_instance.snapshot_data,
        } if wf_instance else None,
    }


@router.post("/settlements", status_code=status.HTTP_201_CREATED)
def create_travel_settlement(
    req: TravelSettlementCreate,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """建立出差結報單（驗證已完簽出差單、防重複結報、折算匯率與抵扣預支）"""
    operator_emp_id = current_user.employee_id or req.employee_id
    items_dicts = [item.model_dump() for item in req.items]
    settlement = TravelService.create_travel_settlement(
        db=db,
        company_id=req.company_id,
        employee_id=operator_emp_id,
        travel_request_id=req.travel_request_id,
        currency=req.currency,
        exchange_rate=req.exchange_rate,
        items_data=items_dicts,
        notes=req.notes,
    )
    return {
        "status": "success",
        "settlement_id": settlement.id,
        "settlement_number": settlement.settlement_number,
        "total_actual_twd": float(settlement.total_actual_twd),
        "advance_offset_amount": float(settlement.advance_offset_amount),
        "net_payable_amount": float(settlement.net_payable_amount),
        "settlement_status": settlement.status,
    }


@router.post("/settlements/{settlement_id}/submit", status_code=status.HTTP_200_OK)
def submit_travel_settlement(
    settlement_id: str,
    req: TravelSettlementSubmit,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """送審出差結報單 (直屬主管 -> 會計窗口)"""
    settlement = db.get(TravelSettlement, settlement_id)
    if not settlement:
        raise AppException(code="SETTLEMENT_NOT_FOUND", message="找不到出差結報單", status_code=404)

    operator_emp_id = current_user.employee_id or settlement.employee_id
    updated_settlement = TravelService.submit_travel_settlement(
        db=db,
        settlement_id=settlement_id,
        operator_employee_id=operator_emp_id,
        finance_window_employee_id=req.finance_window_employee_id,
    )
    return {
        "status": "success",
        "settlement_id": updated_settlement.id,
        "settlement_number": updated_settlement.settlement_number,
        "workflow_instance_id": updated_settlement.workflow_instance_id,
        "settlement_status": updated_settlement.status,
    }


@router.get("/settlements/{settlement_id}", status_code=status.HTTP_200_OK)
def get_travel_settlement_detail(
    settlement_id: str,
    db: DbSession = Depends(get_db),
):
    """取得出差結報單詳情與費用明細"""
    settlement = db.get(TravelSettlement, settlement_id)
    if not settlement:
        raise AppException(code="SETTLEMENT_NOT_FOUND", message="找不到出差結報單", status_code=404)

    wf_instance = None
    if settlement.workflow_instance_id:
        wf_instance = db.get(WorkflowInstance, settlement.workflow_instance_id)

    return {
        "id": settlement.id,
        "settlement_number": settlement.settlement_number,
        "travel_request_id": settlement.travel_request_id,
        "currency": settlement.currency,
        "exchange_rate": float(settlement.exchange_rate),
        "total_actual_twd": float(settlement.total_actual_twd),
        "advance_offset_amount": float(settlement.advance_offset_amount),
        "net_payable_amount": float(settlement.net_payable_amount),
        "status": settlement.status,
        "payment_status": settlement.payment_status,
        "paid_at": settlement.paid_at.isoformat() if settlement.paid_at else None,
        "paid_reference": settlement.paid_reference,
        "items": [
            {
                "id": item.id,
                "category": item.expense_category,
                "date": item.expense_date.isoformat(),
                "currency": item.currency,
                "amount": float(item.amount),
                "amount_twd": float(item.amount_twd),
                "description": item.description,
            }
            for item in settlement.items
        ],
        "workflow_instance": {
            "id": wf_instance.id,
            "status": wf_instance.status,
            "snapshot_data": wf_instance.snapshot_data,
        } if wf_instance else None,
    }


@router.post("/settlements/{settlement_id}/confirm-payment", status_code=status.HTTP_200_OK)
def confirm_settlement_payment(
    settlement_id: str,
    req: PaymentConfirmRequest,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """會計窗口確認款項已完成支付／沖銷"""
    if not current_user.employee_id:
        raise AppException(code="USER_NOT_LINKED_EMPLOYEE", message="帳號未綁定員工身分", status_code=400)

    updated_settlement = TravelService.confirm_payment(
        db=db,
        settlement_id=settlement_id,
        operator_employee_id=current_user.employee_id,
        paid_reference=req.paid_reference,
    )
    return {
        "status": "success",
        "settlement_id": updated_settlement.id,
        "payment_status": updated_settlement.payment_status,
        "paid_reference": updated_settlement.paid_reference,
    }


@router.post("/assignments/{assignment_id}/travel-action", status_code=status.HTTP_200_OK)
def process_travel_approval_action(
    assignment_id: str,
    req: TravelApprovalActionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """出差申請單簽核動作推進"""
    if not current_user.employee_id:
        raise AppException(code="USER_NOT_LINKED_EMPLOYEE", message="帳號未綁定員工身分", status_code=400)

    updated_req = TravelService.process_travel_approval(
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
        "travel_status": updated_req.status,
    }


@router.post("/assignments/{assignment_id}/settlement-action", status_code=status.HTTP_200_OK)
def process_settlement_approval_action(
    assignment_id: str,
    req: TravelApprovalActionRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """出差結報單簽核動作推進"""
    if not current_user.employee_id:
        raise AppException(code="USER_NOT_LINKED_EMPLOYEE", message="帳號未綁定員工身分", status_code=400)

    updated_settlement = TravelService.process_settlement_approval(
        db=db,
        assignment_id=assignment_id,
        operator_employee_id=current_user.employee_id,
        action=req.action,
        comments=req.comments,
        client_ip=request.client.host if request.client else None,
    )
    return {
        "status": "success",
        "settlement_id": updated_settlement.id,
        "settlement_status": updated_settlement.status,
        "payment_status": updated_settlement.payment_status,
    }
