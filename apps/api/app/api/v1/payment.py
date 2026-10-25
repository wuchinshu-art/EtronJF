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
from app.models.payment import Vendor, ExpenseClaim, ExpenseClaimItem, PaymentRequest
from app.models.workflow import WorkflowInstance
from app.core.payment_service import PaymentService

router = APIRouter(tags=["Payment & Expense"])


# ==============================================================================
# Pydantic Schemas
# ==============================================================================
class VendorCreate(BaseModel):
    company_id: str
    code: str
    name: str
    country: str = "TW"
    tax_id: Optional[str] = None
    address: Optional[str] = None
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    email: Optional[str] = None
    payment_terms: str = "NET30"
    bank_country: Optional[str] = None
    bank_name: Optional[str] = None
    bank_code: Optional[str] = None
    branch_name: Optional[str] = None
    branch_code: Optional[str] = None
    account_name: Optional[str] = None
    account_number: Optional[str] = None
    bank_currency: str = "TWD"
    swift_code: Optional[str] = None


class ExpenseClaimItemInput(BaseModel):
    category: str
    expense_date: date
    invoice_number: Optional[str] = None
    currency: str = "TWD"
    exchange_rate: Decimal = Decimal("1.0000")
    amount: Decimal
    description: str
    attachment_url: Optional[str] = None


class ExpenseClaimCreate(BaseModel):
    company_id: str
    employee_id: str
    title: str
    currency: str = "TWD"
    exchange_rate: Decimal = Decimal("1.0000")
    cost_center: Optional[str] = None
    tax_amount: Decimal = Decimal("0.0000")
    items: List[ExpenseClaimItemInput]
    notes: Optional[str] = None


class ExpenseClaimSubmit(BaseModel):
    finance_window_employee_id: Optional[str] = None


class PaymentRequestCreate(BaseModel):
    company_id: str
    employee_id: str
    vendor_id: str
    title: str
    currency: str = "TWD"
    exchange_rate: Decimal = Decimal("1.0000")
    amount: Decimal
    due_date: date
    payment_method: str = "WIRE"
    description: Optional[str] = None
    invoice_number: Optional[str] = None
    invoice_date: Optional[date] = None
    attachment_url: Optional[str] = None


class PaymentRequestSubmit(BaseModel):
    dept_manager_id: Optional[str] = None
    div_manager_id: Optional[str] = None
    gm_id: Optional[str] = None
    finance_window_employee_id: Optional[str] = None


class PaymentConfirmInput(BaseModel):
    paid_reference: str
    settlement_exchange_rate: Optional[Decimal] = None


class ApprovalActionInput(BaseModel):
    action: str = Field(description="APPROVE, REJECT, RETURN")
    comments: Optional[str] = None


# ==============================================================================
# 1. 供應商管理 API (Vendors)
# ==============================================================================
@router.post("/vendors", status_code=status.HTTP_201_CREATED)
def create_vendor(
    req: VendorCreate,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """建立供應商主檔"""
    vendor = PaymentService.create_vendor(
        db=db,
        company_id=req.company_id,
        code=req.code,
        name=req.name,
        country=req.country,
        tax_id=req.tax_id,
        address=req.address,
        contact_name=req.contact_name,
        contact_phone=req.contact_phone,
        email=req.email,
        payment_terms=req.payment_terms,
        bank_country=req.bank_country,
        bank_name=req.bank_name,
        bank_code=req.bank_code,
        branch_name=req.branch_name,
        branch_code=req.branch_code,
        account_name=req.account_name,
        account_number=req.account_number,
        bank_currency=req.bank_currency,
        swift_code=req.swift_code,
    )
    return {
        "status": "success",
        "vendor_id": vendor.id,
        "code": vendor.code,
        "name": vendor.name,
    }


@router.get("/vendors", status_code=status.HTTP_200_OK)
def list_vendors(
    company_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """查詢供應商列表（自動遮罩銀行帳號保護隱私）"""
    query = db.query(Vendor)
    if company_id:
        query = query.filter(Vendor.company_id == company_id)

    vendors = query.order_by(Vendor.created_at.desc()).all()
    return [
        {
            "id": v.id,
            "company_id": v.company_id,
            "code": v.code,
            "name": v.name,
            "country": v.country,
            "tax_id": v.tax_id,
            "account_number_masked": v.masked_account_number(),
            "bank_name": v.bank_name,
            "is_active": v.is_active,
        }
        for v in vendors
    ]


@router.get("/vendors/{vendor_id}", status_code=status.HTTP_200_OK)
def get_vendor(
    vendor_id: str,
    mask_bank_info: bool = True,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """取得單一供應商詳情（可選是否遮罩帳號）"""
    return PaymentService.get_vendor(db=db, vendor_id=vendor_id, mask_bank_info=mask_bank_info)


# ==============================================================================
# 2. 費用報銷單 API (Expense Claims)
# ==============================================================================
@router.post("/expense/claims", status_code=status.HTTP_201_CREATED)
def create_expense_claim(
    req: ExpenseClaimCreate,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """建立費用報銷單草稿（檢驗重複憑證警示）"""
    operator_emp_id = current_user.employee_id or req.employee_id
    items_dicts = [item.model_dump() for item in req.items]
    claim = PaymentService.create_expense_claim(
        db=db,
        company_id=req.company_id,
        employee_id=operator_emp_id,
        title=req.title,
        currency=req.currency,
        exchange_rate=req.exchange_rate,
        items_data=items_dicts,
        cost_center=req.cost_center,
        tax_amount=req.tax_amount,
        notes=req.notes,
    )
    return {
        "status": "success",
        "claim_id": claim.id,
        "claim_number": claim.claim_number,
        "total_amount_twd": float(claim.total_amount_twd),
        "has_duplicate_warning": claim.has_duplicate_warning,
        "claim_status": claim.status,
    }


@router.get("/expense/claims", status_code=status.HTTP_200_OK)
def list_expense_claims(
    employee_id: Optional[str] = None,
    company_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """查詢費用報銷單列表"""
    query = db.query(ExpenseClaim)
    if employee_id:
        query = query.filter(ExpenseClaim.employee_id == employee_id)
    if company_id:
        query = query.filter(ExpenseClaim.company_id == company_id)
    if status:
        query = query.filter(ExpenseClaim.status == status)

    claims = query.order_by(ExpenseClaim.created_at.desc()).all()
    return [
        {
            "id": c.id,
            "claim_number": c.claim_number,
            "title": c.title,
            "total_amount": float(c.total_amount),
            "total_amount_twd": float(c.total_amount_twd),
            "currency": c.currency,
            "status": c.status,
            "payment_status": c.payment_status,
            "has_duplicate_warning": c.has_duplicate_warning,
            "created_at": c.created_at.isoformat(),
        }
        for c in claims
    ]


@router.post("/expense/claims/{claim_id}/submit", status_code=status.HTTP_200_OK)
def submit_expense_claim(
    claim_id: str,
    req: ExpenseClaimSubmit,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """送審費用報銷單（依金額啟動主管鏈門檻）"""
    claim = db.get(ExpenseClaim, claim_id)
    if not claim:
        raise AppException(code="EXPENSE_CLAIM_NOT_FOUND", message="找不到報銷單", status_code=404)

    operator_emp_id = current_user.employee_id or claim.employee_id
    updated_claim = PaymentService.submit_expense_claim(
        db=db,
        claim_id=claim_id,
        operator_employee_id=operator_emp_id,
        finance_window_employee_id=req.finance_window_employee_id,
    )
    return {
        "status": "success",
        "claim_id": updated_claim.id,
        "claim_number": updated_claim.claim_number,
        "workflow_instance_id": updated_claim.workflow_instance_id,
        "claim_status": updated_claim.status,
    }


@router.get("/expense/claims/{claim_id}", status_code=status.HTTP_200_OK)
def get_expense_claim_detail(
    claim_id: str,
    db: DbSession = Depends(get_db),
):
    """取得費用報銷單詳情與明細"""
    claim = db.get(ExpenseClaim, claim_id)
    if not claim:
        raise AppException(code="EXPENSE_CLAIM_NOT_FOUND", message="找不到報銷單", status_code=404)

    wf_instance = None
    if claim.workflow_instance_id:
        wf_instance = db.get(WorkflowInstance, claim.workflow_instance_id)

    return {
        "id": claim.id,
        "claim_number": claim.claim_number,
        "employee_id": claim.employee_id,
        "title": claim.title,
        "currency": claim.currency,
        "exchange_rate": float(claim.exchange_rate),
        "total_amount": float(claim.total_amount),
        "total_amount_twd": float(claim.total_amount_twd),
        "tax_amount": float(claim.tax_amount),
        "status": claim.status,
        "payment_status": claim.payment_status,
        "has_duplicate_warning": claim.has_duplicate_warning,
        "paid_at": claim.paid_at.isoformat() if claim.paid_at else None,
        "paid_reference": claim.paid_reference,
        "exchange_gain_loss": float(claim.exchange_gain_loss),
        "items": [
            {
                "id": item.id,
                "category": item.category,
                "expense_date": item.expense_date.isoformat(),
                "invoice_number": item.invoice_number,
                "amount": float(item.amount),
                "amount_twd": float(item.amount_twd),
                "description": item.description,
            }
            for item in claim.items
        ],
        "workflow_instance": {
            "id": wf_instance.id,
            "status": wf_instance.status,
            "snapshot_data": wf_instance.snapshot_data,
        } if wf_instance else None,
    }


@router.post("/expense/claims/{claim_id}/confirm-payment", status_code=status.HTTP_200_OK)
def confirm_expense_payment(
    claim_id: str,
    req: PaymentConfirmInput,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """會計確認費用付款結清（支援匯兌損益調整）"""
    if not current_user.employee_id:
        raise AppException(code="USER_NOT_LINKED_EMPLOYEE", message="帳號未綁定員工身分", status_code=400)

    updated_claim = PaymentService.confirm_expense_payment(
        db=db,
        claim_id=claim_id,
        operator_employee_id=current_user.employee_id,
        paid_reference=req.paid_reference,
        settlement_exchange_rate=req.settlement_exchange_rate,
    )
    return {
        "status": "success",
        "claim_id": updated_claim.id,
        "payment_status": updated_claim.payment_status,
        "paid_reference": updated_claim.paid_reference,
        "exchange_gain_loss": float(updated_claim.exchange_gain_loss),
    }


@router.post("/expense/assignments/{assignment_id}/action", status_code=status.HTTP_200_OK)
def process_expense_approval_action(
    assignment_id: str,
    req: ApprovalActionInput,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """費用報銷簽核動作推進"""
    if not current_user.employee_id:
        raise AppException(code="USER_NOT_LINKED_EMPLOYEE", message="帳號未綁定員工身分", status_code=400)

    updated_claim = PaymentService.process_expense_approval(
        db=db,
        assignment_id=assignment_id,
        operator_employee_id=current_user.employee_id,
        action=req.action,
        comments=req.comments,
        client_ip=request.client.host if request.client else None,
    )
    return {
        "status": "success",
        "claim_id": updated_claim.id,
        "claim_status": updated_claim.status,
    }


# ==============================================================================
# 3. 供應商請款單 API (Payment Requests)
# ==============================================================================
@router.post("/payment/requests", status_code=status.HTTP_201_CREATED)
def create_payment_request(
    req: PaymentRequestCreate,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """建立供應商請款單草稿（自動保存供應商受款不可變快照）"""
    operator_emp_id = current_user.employee_id or req.employee_id
    pay_req = PaymentService.create_payment_request(
        db=db,
        company_id=req.company_id,
        employee_id=operator_emp_id,
        vendor_id=req.vendor_id,
        title=req.title,
        currency=req.currency,
        exchange_rate=req.exchange_rate,
        amount=req.amount,
        due_date=req.due_date,
        payment_method=req.payment_method,
        description=req.description,
        invoice_number=req.invoice_number,
        invoice_date=req.invoice_date,
        attachment_url=req.attachment_url,
    )
    return {
        "status": "success",
        "payment_id": pay_req.id,
        "payment_number": pay_req.payment_number,
        "amount_twd": float(pay_req.amount_twd),
        "payment_status": pay_req.status,
    }


@router.get("/payment/requests", status_code=status.HTTP_200_OK)
def list_payment_requests(
    employee_id: Optional[str] = None,
    company_id: Optional[str] = None,
    vendor_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """查詢請款單列表"""
    query = db.query(PaymentRequest)
    if employee_id:
        query = query.filter(PaymentRequest.employee_id == employee_id)
    if company_id:
        query = query.filter(PaymentRequest.company_id == company_id)
    if vendor_id:
        query = query.filter(PaymentRequest.vendor_id == vendor_id)
    if status:
        query = query.filter(PaymentRequest.status == status)

    requests = query.order_by(PaymentRequest.created_at.desc()).all()
    return [
        {
            "id": p.id,
            "payment_number": p.payment_number,
            "title": p.title,
            "vendor_id": p.vendor_id,
            "amount": float(p.amount),
            "amount_twd": float(p.amount_twd),
            "currency": p.currency,
            "due_date": p.due_date.isoformat(),
            "status": p.status,
            "payment_status": p.payment_status,
        }
        for p in requests
    ]


@router.post("/payment/requests/{payment_id}/submit", status_code=status.HTTP_200_OK)
def submit_payment_request(
    payment_id: str,
    req: PaymentRequestSubmit,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """送審供應商請款單（依金額啟動主管/部/處/GM/會計管線）"""
    pay_req = db.get(PaymentRequest, payment_id)
    if not pay_req:
        raise AppException(code="PAYMENT_REQUEST_NOT_FOUND", message="找不到請款單", status_code=404)

    operator_emp_id = current_user.employee_id or pay_req.employee_id
    updated_pay = PaymentService.submit_payment_request(
        db=db,
        payment_id=payment_id,
        operator_employee_id=operator_emp_id,
        dept_manager_id=req.dept_manager_id,
        div_manager_id=req.div_manager_id,
        gm_id=req.gm_id,
        finance_window_employee_id=req.finance_window_employee_id,
    )
    return {
        "status": "success",
        "payment_id": updated_pay.id,
        "payment_number": updated_pay.payment_number,
        "workflow_instance_id": updated_pay.workflow_instance_id,
        "payment_status": updated_pay.status,
    }


@router.get("/payment/requests/{payment_id}", status_code=status.HTTP_200_OK)
def get_payment_request_detail(
    payment_id: str,
    db: DbSession = Depends(get_db),
):
    """取得請款單詳情與供應商受款快照"""
    pay_req = db.get(PaymentRequest, payment_id)
    if not pay_req:
        raise AppException(code="PAYMENT_REQUEST_NOT_FOUND", message="找不到請款單", status_code=404)

    wf_instance = None
    if pay_req.workflow_instance_id:
        wf_instance = db.get(WorkflowInstance, pay_req.workflow_instance_id)

    return {
        "id": pay_req.id,
        "payment_number": pay_req.payment_number,
        "vendor_id": pay_req.vendor_id,
        "title": pay_req.title,
        "description": pay_req.description,
        "vendor_snapshot": pay_req.vendor_snapshot,
        "currency": pay_req.currency,
        "exchange_rate": float(pay_req.exchange_rate),
        "amount": float(pay_req.amount),
        "amount_twd": float(pay_req.amount_twd),
        "due_date": pay_req.due_date.isoformat(),
        "payment_method": pay_req.payment_method,
        "invoice_number": pay_req.invoice_number,
        "status": pay_req.status,
        "payment_status": pay_req.payment_status,
        "paid_at": pay_req.paid_at.isoformat() if pay_req.paid_at else None,
        "paid_reference": pay_req.paid_reference,
        "exchange_gain_loss": float(pay_req.exchange_gain_loss),
        "workflow_instance": {
            "id": wf_instance.id,
            "status": wf_instance.status,
            "snapshot_data": wf_instance.snapshot_data,
        } if wf_instance else None,
    }


@router.post("/payment/requests/{payment_id}/confirm-payment", status_code=status.HTTP_200_OK)
def confirm_vendor_payment(
    payment_id: str,
    req: PaymentConfirmInput,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """會計確認供應商款項支付／結清（支援匯兌損益調整）"""
    if not current_user.employee_id:
        raise AppException(code="USER_NOT_LINKED_EMPLOYEE", message="帳號未綁定員工身分", status_code=400)

    updated_pay = PaymentService.confirm_vendor_payment(
        db=db,
        payment_id=payment_id,
        operator_employee_id=current_user.employee_id,
        paid_reference=req.paid_reference,
        settlement_exchange_rate=req.settlement_exchange_rate,
    )
    return {
        "status": "success",
        "payment_id": updated_pay.id,
        "payment_status": updated_pay.payment_status,
        "paid_reference": updated_pay.paid_reference,
        "exchange_gain_loss": float(updated_pay.exchange_gain_loss),
    }


@router.post("/payment/assignments/{assignment_id}/action", status_code=status.HTTP_200_OK)
def process_payment_approval_action(
    assignment_id: str,
    req: ApprovalActionInput,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """供應商請款簽核動作推進"""
    if not current_user.employee_id:
        raise AppException(code="USER_NOT_LINKED_EMPLOYEE", message="帳號未綁定員工身分", status_code=400)

    updated_pay = PaymentService.process_payment_approval(
        db=db,
        assignment_id=assignment_id,
        operator_employee_id=current_user.employee_id,
        action=req.action,
        comments=req.comments,
        client_ip=request.client.host if request.client else None,
    )
    return {
        "status": "success",
        "payment_id": updated_pay.id,
        "payment_status": updated_pay.status,
    }
