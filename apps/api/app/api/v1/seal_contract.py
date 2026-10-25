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
from app.models.seal_contract import Seal, SealHandover, SealRequest, Contract
from app.models.workflow import WorkflowInstance
from app.core.seal_contract_service import SealContractService

router = APIRouter(tags=["Seal & Contract"])


# ==============================================================================
# Pydantic Schemas
# ==============================================================================
class SealCreate(BaseModel):
    company_id: str
    code: str
    name: str
    seal_type: str
    custodian_employee_id: str
    effective_from: date
    effective_to: Optional[date] = None


class SealHandoverRequest(BaseModel):
    from_custodian_id: str
    to_custodian_id: str
    reason: str
    handover_date: Optional[date] = None


class SealRequestCreate(BaseModel):
    company_id: str
    employee_id: str
    seal_id: str
    document_name: str
    purpose: str
    copies: int = 1
    document_version: str = "v1.0"
    attachment_url: Optional[str] = None
    contract_id: Optional[str] = None


class SealExecuteInput(BaseModel):
    sealed_copies: int
    final_sealed_document_url: Optional[str] = None


class ContractCreate(BaseModel):
    company_id: str
    employee_id: str
    counterparty_name: str
    title: str
    contract_type: str
    start_date: date
    end_date: Optional[date] = None
    currency: str = "TWD"
    exchange_rate: Decimal = Decimal("1.0000")
    amount: Decimal = Decimal("0.0000")
    responsible_department: Optional[str] = None
    auto_renew: bool = False
    needs_seal: bool = False
    attachment_url: Optional[str] = None
    renewed_from_contract_id: Optional[str] = None


class ContractSubmit(BaseModel):
    legal_window_employee_id: Optional[str] = None
    seal_custodian_employee_id: Optional[str] = None


class ContractApprovalAction(BaseModel):
    action: str = Field(description="APPROVE, REJECT, RETURN")
    comments: Optional[str] = None
    legal_opinion: Optional[str] = None


class ContractArchiveInput(BaseModel):
    signed_document_url: str


# ==============================================================================
# 1. 印鑑清冊主檔 API (Seals)
# ==============================================================================
@router.post("/seals", status_code=status.HTTP_201_CREATED)
def create_seal(
    req: SealCreate,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """建立印鑑主檔"""
    seal = SealContractService.create_seal(
        db=db,
        company_id=req.company_id,
        code=req.code,
        name=req.name,
        seal_type=req.seal_type,
        custodian_employee_id=req.custodian_employee_id,
        effective_from=req.effective_from,
        effective_to=req.effective_to,
    )
    return {
        "status": "success",
        "seal_id": seal.id,
        "code": seal.code,
        "name": seal.name,
    }


@router.get("/seals", status_code=status.HTTP_200_OK)
def list_seals(
    company_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """查詢印鑑清冊列表"""
    query = db.query(Seal)
    if company_id:
        query = query.filter(Seal.company_id == company_id)

    seals = query.order_by(Seal.created_at.desc()).all()
    
    # 預加載員工資料以取得保管人資訊
    custodian_ids = [s.custodian_employee_id for s in seals if s.custodian_employee_id]
    emp_map = {}
    if custodian_ids:
        employees = db.query(Employee).filter(Employee.id.in_(custodian_ids)).all()
        emp_map = {e.id: e for e in employees}

    return [
        {
            "id": s.id,
            "company_id": s.company_id,
            "code": s.code,
            "name": s.name,
            "seal_type": s.seal_type,
            "custodian_employee_id": s.custodian_employee_id,
            "custodian_name": emp_map[s.custodian_employee_id].full_name if s.custodian_employee_id in emp_map else s.custodian_employee_id,
            "custodian_employee_no": emp_map[s.custodian_employee_id].employee_no if s.custodian_employee_id in emp_map else "",
            "is_active": s.is_active,
            "effective_from": s.effective_from.isoformat() if s.effective_from else None,
            "effective_to": s.effective_to.isoformat() if s.effective_to else None,
        }
        for s in seals
    ]


@router.post("/seals/{seal_id}/handover", status_code=status.HTTP_200_OK)
def handover_seal(
    seal_id: str,
    req: SealHandoverRequest,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """印鑑保管人更換交接作業（審計留痕）"""
    updated_seal = SealContractService.handover_seal(
        db=db,
        seal_id=seal_id,
        from_custodian_id=req.from_custodian_id,
        to_custodian_id=req.to_custodian_id,
        reason=req.reason,
        handover_date=req.handover_date,
    )
    return {
        "status": "success",
        "seal_id": updated_seal.id,
        "new_custodian_id": updated_seal.custodian_employee_id,
        "version": updated_seal.version,
    }


@router.get("/seals/{seal_id}/handovers", status_code=status.HTTP_200_OK)
def list_seal_handovers(
    seal_id: str,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """查詢印鑑保管人交接歷史紀錄"""
    handovers = SealContractService.get_seal_handovers(db=db, seal_id=seal_id)
    return [
        {
            "id": h.id,
            "from_custodian_id": h.from_custodian_id,
            "to_custodian_id": h.to_custodian_id,
            "handover_date": h.handover_date.isoformat(),
            "reason": h.reason,
            "created_at": h.created_at.isoformat(),
        }
        for h in handovers
    ]


# ==============================================================================
# 2. 用印申請 API (Seal Requests)
# ==============================================================================
@router.post("/seal/requests", status_code=status.HTTP_201_CREATED)
def create_seal_request(
    req: SealRequestCreate,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """建立用印申請單草稿"""
    operator_emp_id = current_user.employee_id or req.employee_id
    seal_req = SealContractService.create_seal_request(
        db=db,
        company_id=req.company_id,
        employee_id=operator_emp_id,
        seal_id=req.seal_id,
        document_name=req.document_name,
        purpose=req.purpose,
        copies=req.copies,
        document_version=req.document_version,
        attachment_url=req.attachment_url,
        contract_id=req.contract_id,
    )
    return {
        "status": "success",
        "request_id": seal_req.id,
        "request_number": seal_req.request_number,
        "seal_status": seal_req.status,
        "execution_status": seal_req.execution_status,
    }


@router.get("/seal/requests", status_code=status.HTTP_200_OK)
def list_seal_requests(
    employee_id: Optional[str] = None,
    company_id: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """查詢用印申請單列表"""
    query = db.query(SealRequest)
    if employee_id:
        query = query.filter(SealRequest.employee_id == employee_id)
    if company_id:
        query = query.filter(SealRequest.company_id == company_id)
    if status:
        query = query.filter(SealRequest.status == status)

    requests = query.order_by(SealRequest.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "request_number": r.request_number,
            "document_name": r.document_name,
            "seal_id": r.seal_id,
            "copies": r.copies,
            "status": r.status,
            "execution_status": r.execution_status,
            "created_at": r.created_at.isoformat(),
        }
        for r in requests
    ]


@router.post("/seal/requests/{request_id}/submit", status_code=status.HTTP_200_OK)
def submit_seal_request(
    request_id: str,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """送審用印申請單 (直屬主管 -> 印鑑保管人)"""
    seal_req = db.get(SealRequest, request_id)
    if not seal_req:
        raise AppException(code="SEAL_REQUEST_NOT_FOUND", message="找不到用印單", status_code=404)

    operator_emp_id = current_user.employee_id or seal_req.employee_id
    updated_req = SealContractService.submit_seal_request(
        db=db,
        request_id=request_id,
        operator_employee_id=operator_emp_id,
    )
    return {
        "status": "success",
        "request_id": updated_req.id,
        "request_number": updated_req.request_number,
        "workflow_instance_id": updated_req.workflow_instance_id,
        "seal_status": updated_req.status,
    }


@router.get("/seal/requests/{request_id}", status_code=status.HTTP_200_OK)
def get_seal_request_detail(
    request_id: str,
    db: DbSession = Depends(get_db),
):
    """取得用印申請單詳情"""
    seal_req = db.get(SealRequest, request_id)
    if not seal_req:
        raise AppException(code="SEAL_REQUEST_NOT_FOUND", message="找不到用印單", status_code=404)

    wf_instance = None
    if seal_req.workflow_instance_id:
        wf_instance = db.get(WorkflowInstance, seal_req.workflow_instance_id)

    return {
        "id": seal_req.id,
        "request_number": seal_req.request_number,
        "employee_id": seal_req.employee_id,
        "seal_id": seal_req.seal_id,
        "document_name": seal_req.document_name,
        "document_version": seal_req.document_version,
        "purpose": seal_req.purpose,
        "copies": seal_req.copies,
        "contract_id": seal_req.contract_id,
        "status": seal_req.status,
        "execution_status": seal_req.execution_status,
        "sealed_at": seal_req.sealed_at.isoformat() if seal_req.sealed_at else None,
        "sealed_copies": seal_req.sealed_copies,
        "sealed_by_employee_id": seal_req.sealed_by_employee_id,
        "final_sealed_document_url": seal_req.final_sealed_document_url,
        "workflow_instance": {
            "id": wf_instance.id,
            "status": wf_instance.status,
            "snapshot_data": wf_instance.snapshot_data,
        } if wf_instance else None,
    }


@router.post("/seal/requests/{request_id}/execute", status_code=status.HTTP_200_OK)
def execute_seal_request(
    request_id: str,
    req: SealExecuteInput,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """保管人執行實體用印登記 (記錄份數與掃描件)"""
    if not current_user.employee_id:
        raise AppException(code="USER_NOT_LINKED_EMPLOYEE", message="帳號未綁定員工身分", status_code=400)

    updated_req = SealContractService.execute_seal(
        db=db,
        request_id=request_id,
        operator_employee_id=current_user.employee_id,
        sealed_copies=req.sealed_copies,
        final_sealed_document_url=req.final_sealed_document_url,
    )
    return {
        "status": "success",
        "request_id": updated_req.id,
        "execution_status": updated_req.execution_status,
        "sealed_at": updated_req.sealed_at.isoformat(),
        "sealed_copies": updated_req.sealed_copies,
    }


@router.post("/seal/assignments/{assignment_id}/action", status_code=status.HTTP_200_OK)
def process_seal_approval_action(
    assignment_id: str,
    req: ContractApprovalAction,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """用印簽核動作推進"""
    if not current_user.employee_id:
        raise AppException(code="USER_NOT_LINKED_EMPLOYEE", message="帳號未綁定員工身分", status_code=400)

    updated_req = SealContractService.process_seal_approval(
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
        "seal_status": updated_req.status,
    }


# ==============================================================================
# 3. 合約主檔與審查 API (Contracts)
# ==============================================================================
@router.post("/contracts", status_code=status.HTTP_201_CREATED)
def create_contract(
    req: ContractCreate,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """建立合約審查草稿"""
    operator_emp_id = current_user.employee_id or req.employee_id
    contract = SealContractService.create_contract(
        db=db,
        company_id=req.company_id,
        employee_id=operator_emp_id,
        counterparty_name=req.counterparty_name,
        title=req.title,
        contract_type=req.contract_type,
        start_date=req.start_date,
        end_date=req.end_date,
        currency=req.currency,
        exchange_rate=req.exchange_rate,
        amount=req.amount,
        responsible_department=req.responsible_department,
        auto_renew=req.auto_renew,
        needs_seal=req.needs_seal,
        attachment_url=req.attachment_url,
        renewed_from_contract_id=req.renewed_from_contract_id,
    )
    return {
        "status": "success",
        "contract_id": contract.id,
        "contract_number": contract.contract_number,
        "amount_twd": float(contract.amount_twd),
        "contract_status": contract.status,
    }


@router.get("/contracts", status_code=status.HTTP_200_OK)
def list_contracts(
    employee_id: Optional[str] = None,
    company_id: Optional[str] = None,
    contract_type: Optional[str] = None,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """查詢合約列表"""
    query = db.query(Contract)
    if employee_id:
        query = query.filter(Contract.employee_id == employee_id)
    if company_id:
        query = query.filter(Contract.company_id == company_id)
    if contract_type:
        query = query.filter(Contract.contract_type == contract_type)
    if status:
        query = query.filter(Contract.status == status)

    contracts = query.order_by(Contract.created_at.desc()).all()
    return [
        {
            "id": c.id,
            "contract_number": c.contract_number,
            "title": c.title,
            "counterparty_name": c.counterparty_name,
            "contract_type": c.contract_type,
            "amount": float(c.amount),
            "amount_twd": float(c.amount_twd),
            "currency": c.currency,
            "start_date": c.start_date.isoformat(),
            "end_date": c.end_date.isoformat() if c.end_date else None,
            "status": c.status,
            "lifecycle_status": c.lifecycle_status,
        }
        for c in contracts
    ]


@router.post("/contracts/{contract_id}/submit", status_code=status.HTTP_200_OK)
def submit_contract(
    contract_id: str,
    req: ContractSubmit,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """送審合約單（啟動金額門檻 + 法務 + 需用印時印鑑保管人管線）"""
    contract = db.get(Contract, contract_id)
    if not contract:
        raise AppException(code="CONTRACT_NOT_FOUND", message="找不到合約", status_code=404)

    operator_emp_id = current_user.employee_id or contract.employee_id
    updated_ctr = SealContractService.submit_contract(
        db=db,
        contract_id=contract_id,
        operator_employee_id=operator_emp_id,
        legal_window_employee_id=req.legal_window_employee_id,
        seal_custodian_employee_id=req.seal_custodian_employee_id,
    )
    return {
        "status": "success",
        "contract_id": updated_ctr.id,
        "contract_number": updated_ctr.contract_number,
        "workflow_instance_id": updated_ctr.workflow_instance_id,
        "contract_status": updated_ctr.status,
    }


@router.get("/contracts/{contract_id}", status_code=status.HTTP_200_OK)
def get_contract_detail(
    contract_id: str,
    db: DbSession = Depends(get_db),
):
    """取得合約詳情與法務意見"""
    contract = db.get(Contract, contract_id)
    if not contract:
        raise AppException(code="CONTRACT_NOT_FOUND", message="找不到合約", status_code=404)

    wf_instance = None
    if contract.workflow_instance_id:
        wf_instance = db.get(WorkflowInstance, contract.workflow_instance_id)

    return {
        "id": contract.id,
        "contract_number": contract.contract_number,
        "counterparty_name": contract.counterparty_name,
        "title": contract.title,
        "contract_type": contract.contract_type,
        "responsible_department": contract.responsible_department,
        "currency": contract.currency,
        "exchange_rate": float(contract.exchange_rate),
        "amount": float(contract.amount),
        "amount_twd": float(contract.amount_twd),
        "start_date": contract.start_date.isoformat(),
        "end_date": contract.end_date.isoformat() if contract.end_date else None,
        "auto_renew": contract.auto_renew,
        "needs_seal": contract.needs_seal,
        "legal_opinion": contract.legal_opinion,
        "status": contract.status,
        "lifecycle_status": contract.lifecycle_status,
        "signed_document_url": contract.signed_document_url,
        "archived_at": contract.archived_at.isoformat() if contract.archived_at else None,
        "workflow_instance": {
            "id": wf_instance.id,
            "status": wf_instance.status,
            "snapshot_data": wf_instance.snapshot_data,
        } if wf_instance else None,
    }


@router.post("/contracts/{contract_id}/archive", status_code=status.HTTP_200_OK)
def archive_contract(
    contract_id: str,
    req: ContractArchiveInput,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """合約完簽後歸檔（上傳正式雙方簽署用印掃描件）"""
    updated_ctr = SealContractService.archive_contract(
        db=db,
        contract_id=contract_id,
        signed_document_url=req.signed_document_url,
    )
    return {
        "status": "success",
        "contract_id": updated_ctr.id,
        "archived_at": updated_ctr.archived_at.isoformat(),
        "signed_document_url": updated_ctr.signed_document_url,
    }


@router.post("/contracts/assignments/{assignment_id}/action", status_code=status.HTTP_200_OK)
def process_contract_approval_action(
    assignment_id: str,
    req: ContractApprovalAction,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """合約簽核動作推進（支援法務意見錄入）"""
    if not current_user.employee_id:
        raise AppException(code="USER_NOT_LINKED_EMPLOYEE", message="帳號未綁定員工身分", status_code=400)

    updated_ctr = SealContractService.process_contract_approval(
        db=db,
        assignment_id=assignment_id,
        operator_employee_id=current_user.employee_id,
        action=req.action,
        comments=req.comments,
        legal_opinion=req.legal_opinion,
        client_ip=request.client.host if request.client else None,
    )
    return {
        "status": "success",
        "contract_id": updated_ctr.id,
        "contract_status": updated_ctr.status,
        "lifecycle_status": updated_ctr.lifecycle_status,
    }
