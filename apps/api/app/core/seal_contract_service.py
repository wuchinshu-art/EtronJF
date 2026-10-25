import random
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_

from app.core.errors import AppException
from app.models.hr import Employee, Company
from app.models.seal_contract import Seal, SealHandover, SealRequest, Contract
from app.models.workflow import WorkflowInstance, ApprovalAssignment
from app.core.workflow_engine import WorkflowEngine


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_seal_request_number() -> str:
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    rand_str = f"{random.randint(1000, 9999)}"
    return f"SEAL-{today_str}-{rand_str}"


def generate_contract_number() -> str:
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    rand_str = f"{random.randint(1000, 9999)}"
    return f"CTR-{today_str}-{rand_str}"


class SealContractService:
    """印鑑清冊、用印申請與合約審查領域服務 (Seal & Contract Domain Service)"""

    # --------------------------------------------------------------------------
    # 1. 印鑑主檔與交接紀錄 (Seal Registry & Handover)
    # --------------------------------------------------------------------------
    @staticmethod
    def create_seal(
        db: Session,
        company_id: str,
        code: str,
        name: str,
        seal_type: str,
        custodian_employee_id: str,
        effective_from: date,
        effective_to: Optional[date] = None,
    ) -> Seal:
        """建立印鑑清冊主檔"""
        existing = db.query(Seal).filter(Seal.company_id == company_id, Seal.code == code).first()
        if existing:
            raise AppException(code="SEAL_CODE_EXISTS", message=f"印鑑代碼 [{code}] 已存在", status_code=400)

        custodian = db.get(Employee, custodian_employee_id)
        if not custodian:
            raise AppException(code="CUSTODIAN_NOT_FOUND", message="找不到指定之保管人員工資料", status_code=404)

        seal = Seal(
            company_id=company_id,
            code=code,
            name=name,
            seal_type=seal_type,
            custodian_employee_id=custodian_employee_id,
            effective_from=effective_from,
            effective_to=effective_to,
            is_active=True,
            version=1,
        )
        db.add(seal)
        db.commit()
        db.refresh(seal)
        return seal

    @staticmethod
    def handover_seal(
        db: Session,
        seal_id: str,
        from_custodian_id: str,
        to_custodian_id: str,
        reason: str,
        handover_date: Optional[date] = None,
    ) -> Seal:
        """
        印鑑保管人更換交接作業：
        - 檢查原保管人是否相符
        - 更新印鑑保管人
        - 記錄交接留痕日誌 (SealHandover)
        """
        seal = db.get(Seal, seal_id)
        if not seal:
            raise AppException(code="SEAL_NOT_FOUND", message="找不到指定印鑑", status_code=404)

        if seal.custodian_employee_id != from_custodian_id:
            raise AppException(
                code="INVALID_FROM_CUSTODIAN",
                message="交接來源保管人與印鑑目前保管人不符",
                status_code=400,
            )

        new_custodian = db.get(Employee, to_custodian_id)
        if not new_custodian:
            raise AppException(code="CUSTODIAN_NOT_FOUND", message="找不到新接任保管人員工資料", status_code=404)

        h_date = handover_date or date.today()
        handover = SealHandover(
            seal_id=seal.id,
            from_custodian_id=from_custodian_id,
            to_custodian_id=to_custodian_id,
            handover_date=h_date,
            reason=reason,
        )
        db.add(handover)

        seal.custodian_employee_id = to_custodian_id
        seal.version += 1
        db.commit()
        db.refresh(seal)
        return seal

    @staticmethod
    def get_seal_handovers(db: Session, seal_id: str) -> List[SealHandover]:
        """查詢印鑑之歷史交接審計紀錄"""
        return (
            db.query(SealHandover)
            .filter(SealHandover.seal_id == seal_id)
            .order_by(SealHandover.created_at.desc())
            .all()
        )

    # --------------------------------------------------------------------------
    # 2. 用印申請與執行登記 (Seal Requests)
    # --------------------------------------------------------------------------
    @staticmethod
    def create_seal_request(
        db: Session,
        company_id: str,
        employee_id: str,
        seal_id: str,
        document_name: str,
        purpose: str,
        copies: int = 1,
        document_version: str = "v1.0",
        attachment_url: Optional[str] = None,
        contract_id: Optional[str] = None,
    ) -> SealRequest:
        employee = db.get(Employee, employee_id) if employee_id and employee_id != "EMP-DEFAULT" else None
        if not employee:
            employee = db.query(Employee).filter(Employee.company_id == company_id, Employee.status == "ACTIVE").first()
            if not employee:
                raise AppException(code="EMPLOYEE_NOT_FOUND", message="找不到申請員工資料", status_code=404)
            employee_id = employee.id

        seal = db.get(Seal, seal_id)
        if not seal or not seal.is_active:
            raise AppException(code="SEAL_INVALID", message="指定印鑑不存在或已停用", status_code=400)

        req_num = generate_seal_request_number()
        seal_req = SealRequest(
            company_id=company_id,
            employee_id=employee_id,
            seal_id=seal_id,
            request_number=req_num,
            document_name=document_name,
            document_version=document_version,
            purpose=purpose,
            copies=copies,
            attachment_url=attachment_url,
            contract_id=contract_id,
            status="DRAFT",
            execution_status="NOT_SEALED",
            revision=1,
        )
        db.add(seal_req)
        db.commit()
        db.refresh(seal_req)
        return seal_req

    @staticmethod
    def submit_seal_request(
        db: Session,
        request_id: str,
        operator_employee_id: str,
    ) -> SealRequest:
        """
        送審用印申請單：
        管線解析：直屬主管 (DIRECT_MANAGER) -> 印鑑保管人 (SEAL_CUSTODIAN)
        """
        seal_req = db.get(SealRequest, request_id)
        if not seal_req:
            raise AppException(code="SEAL_REQUEST_NOT_FOUND", message="找不到用印申請單", status_code=404)

        if seal_req.employee_id != operator_employee_id:
            raise AppException(code="UNAUTHORIZED_SUBMITTER", message="僅申請人本人可送審該用印單", status_code=403)

        if seal_req.status not in ("DRAFT", "RETURNED"):
            raise AppException(
                code="INVALID_STATUS_FOR_SUBMIT",
                message=f"用印單當前狀態為 {seal_req.status}，不可重複送審",
                status_code=400,
            )

        seal = db.get(Seal, seal_req.seal_id)
        context: Dict[str, Any] = {
            "seal_custodian_id": seal.custodian_employee_id if seal else None,
            "default_window_employee_id": seal.custodian_employee_id if seal else None,
        }

        wf_instance = WorkflowEngine.submit_document(
            db=db,
            company_id=seal_req.company_id,
            document_type="SEAL",
            document_id=seal_req.id,
            applicant_employee_id=seal_req.employee_id,
            context=context,
        )

        seal_req.workflow_instance_id = wf_instance.id
        seal_req.status = "IN_REVIEW"
        if seal_req.status == "RETURNED":
            seal_req.revision += 1

        db.commit()
        db.refresh(seal_req)
        return seal_req

    @staticmethod
    def process_seal_approval(
        db: Session,
        assignment_id: str,
        operator_employee_id: str,
        action: str,  # APPROVE, REJECT, RETURN
        comments: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> SealRequest:
        """推進用印簽核動作"""
        assignment = db.get(ApprovalAssignment, assignment_id)
        if not assignment:
            raise AppException(code="ASSIGNMENT_NOT_FOUND", message="找不到審核任務", status_code=404)

        wf_instance = db.get(WorkflowInstance, assignment.instance_id)
        if not wf_instance or wf_instance.document_type != "SEAL":
            raise AppException(code="INVALID_WORKFLOW_INSTANCE", message="簽核實例不匹配", status_code=400)

        seal_req = db.get(SealRequest, wf_instance.document_id)
        if not seal_req:
            raise AppException(code="SEAL_REQUEST_NOT_FOUND", message="找不到對應之用印單", status_code=404)

        WorkflowEngine.execute_action(
            db=db,
            assignment_id=assignment_id,
            operator_employee_id=operator_employee_id,
            action=action,
            comments=comments,
            client_ip=client_ip,
        )

        db.refresh(wf_instance)
        if wf_instance.status == "APPROVED":
            seal_req.status = "APPROVED"
        elif wf_instance.status == "REJECTED":
            seal_req.status = "REJECTED"
        elif wf_instance.status == "RETURNED":
            seal_req.status = "RETURNED"

        db.commit()
        db.refresh(seal_req)
        return seal_req

    @staticmethod
    def execute_seal(
        db: Session,
        request_id: str,
        operator_employee_id: str,
        sealed_copies: int,
        final_sealed_document_url: Optional[str] = None,
    ) -> SealRequest:
        """
        保管人執行實體用印登記：
        - 規範核心：簽核核准不等於已用印；保管人執行後記錄日期、份數與完成文件
        - 檢查單據必須處於 APPROVED 狀態
        - 檢查尚未執行用印，避免重複執行
        """
        seal_req = db.get(SealRequest, request_id)
        if not seal_req:
            raise AppException(code="SEAL_REQUEST_NOT_FOUND", message="找不到用印申請單", status_code=404)

        if seal_req.status != "APPROVED":
            raise AppException(
                code="NOT_APPROVED_FOR_SEAL",
                message=f"用印申請尚未完簽核准 (目前狀態: {seal_req.status})，無法執行實體用印",
                status_code=400,
            )

        if seal_req.execution_status == "SEALED":
            raise AppException(code="ALREADY_SEALED", message="該單據已執行用印完成，禁止重複登記", status_code=400)

        seal = db.get(Seal, seal_req.seal_id)
        # 驗證操作者為印鑑保管人
        if seal and seal.custodian_employee_id != operator_employee_id:
            raise AppException(code="FORBIDDEN_CUSTODIAN", message="僅指定之印鑑保管人可執行實體用印登記", status_code=403)

        seal_req.execution_status = "SEALED"
        seal_req.sealed_at = utc_now()
        seal_req.sealed_copies = sealed_copies
        seal_req.sealed_by_employee_id = operator_employee_id
        seal_req.final_sealed_document_url = final_sealed_document_url

        db.commit()
        db.refresh(seal_req)
        return seal_req

    # --------------------------------------------------------------------------
    # 3. 合約審查與生命週期 (Contracts)
    # --------------------------------------------------------------------------
    @staticmethod
    def create_contract(
        db: Session,
        company_id: str,
        employee_id: str,
        counterparty_name: str,
        title: str,
        contract_type: str,
        start_date: date,
        end_date: Optional[date] = None,
        currency: str = "TWD",
        exchange_rate: Decimal = Decimal("1.0000"),
        amount: Decimal = Decimal("0.0000"),
        responsible_department: Optional[str] = None,
        auto_renew: bool = False,
        needs_seal: bool = False,
        attachment_url: Optional[str] = None,
        renewed_from_contract_id: Optional[str] = None,
    ) -> Contract:
        """建立合約主檔審查草稿"""
        employee = db.get(Employee, employee_id) if employee_id and employee_id != "EMP-DEFAULT" else None
        if not employee:
            employee = db.query(Employee).filter(Employee.company_id == company_id, Employee.status == "ACTIVE").first()
            if not employee:
                raise AppException(code="EMPLOYEE_NOT_FOUND", message="找不到申請員工資料", status_code=404)
            employee_id = employee.id

        if end_date and start_date > end_date:
            raise AppException(code="INVALID_DATE_RANGE", message="合約生效起日不可晚於終止訖日", status_code=400)

        amount_twd = (amount * exchange_rate).quantize(Decimal("0.0001"))
        ctr_num = generate_contract_number()

        contract = Contract(
            company_id=company_id,
            employee_id=employee_id,
            contract_number=ctr_num,
            counterparty_name=counterparty_name,
            title=title,
            contract_type=contract_type,
            responsible_department=responsible_department,
            currency=currency,
            exchange_rate=exchange_rate,
            amount=amount,
            amount_twd=amount_twd,
            start_date=start_date,
            end_date=end_date,
            auto_renew=auto_renew,
            needs_seal=needs_seal,
            attachment_url=attachment_url,
            renewed_from_contract_id=renewed_from_contract_id,
            status="DRAFT",
            lifecycle_status="PENDING_APPROVAL",
            revision=1,
        )
        db.add(contract)
        db.commit()
        db.refresh(contract)
        return contract

    @staticmethod
    def submit_contract(
        db: Session,
        contract_id: str,
        operator_employee_id: str,
        legal_window_employee_id: Optional[str] = None,
        seal_custodian_employee_id: Optional[str] = None,
    ) -> Contract:
        """
        送審合約單：
        管線解析：直屬主管 -> 第二層主管 (>=5000) -> 第三層主管 (>=100000) -> 法務窗口 -> 印鑑保管人 (needs_seal==true)
        """
        contract = db.get(Contract, contract_id)
        if not contract:
            raise AppException(code="CONTRACT_NOT_FOUND", message="找不到合約", status_code=404)

        if contract.employee_id != operator_employee_id:
            raise AppException(code="UNAUTHORIZED_SUBMITTER", message="僅承辦人本人可送審該合約", status_code=403)

        if contract.status not in ("DRAFT", "RETURNED"):
            raise AppException(
                code="INVALID_STATUS_FOR_SUBMIT",
                message=f"合約當前狀態為 {contract.status}，不可重複送審",
                status_code=400,
            )

        context: Dict[str, Any] = {
            "amount": float(contract.amount_twd),
            "needs_seal": "true" if contract.needs_seal else "false",
        }
        if legal_window_employee_id:
            context["legal_window_id"] = legal_window_employee_id
            context["default_window_employee_id"] = legal_window_employee_id
        if seal_custodian_employee_id:
            context["seal_custodian_id"] = seal_custodian_employee_id

        wf_instance = WorkflowEngine.submit_document(
            db=db,
            company_id=contract.company_id,
            document_type="CONTRACT",
            document_id=contract.id,
            applicant_employee_id=contract.employee_id,
            context=context,
        )

        contract.workflow_instance_id = wf_instance.id
        contract.status = "IN_REVIEW"
        if contract.status == "RETURNED":
            contract.revision += 1

        db.commit()
        db.refresh(contract)
        return contract

    @staticmethod
    def process_contract_approval(
        db: Session,
        assignment_id: str,
        operator_employee_id: str,
        action: str,  # APPROVE, REJECT, RETURN
        comments: Optional[str] = None,
        legal_opinion: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> Contract:
        """推進合約簽核動作（支援法務意見寫入）"""
        assignment = db.get(ApprovalAssignment, assignment_id)
        if not assignment:
            raise AppException(code="ASSIGNMENT_NOT_FOUND", message="找不到審核任務", status_code=404)

        wf_instance = db.get(WorkflowInstance, assignment.instance_id)
        if not wf_instance or wf_instance.document_type != "CONTRACT":
            raise AppException(code="INVALID_WORKFLOW_INSTANCE", message="簽核實例不匹配", status_code=400)

        contract = db.get(Contract, wf_instance.document_id)
        if not contract:
            raise AppException(code="CONTRACT_NOT_FOUND", message="找不到對應之合約", status_code=404)

        if legal_opinion:
            contract.legal_opinion = legal_opinion

        WorkflowEngine.execute_action(
            db=db,
            assignment_id=assignment_id,
            operator_employee_id=operator_employee_id,
            action=action,
            comments=comments,
            client_ip=client_ip,
        )

        db.refresh(wf_instance)
        if wf_instance.status == "APPROVED":
            contract.status = "APPROVED"
            contract.lifecycle_status = "ACTIVE"
        elif wf_instance.status == "REJECTED":
            contract.status = "REJECTED"
        elif wf_instance.status == "RETURNED":
            contract.status = "RETURNED"

        db.commit()
        db.refresh(contract)
        return contract

    @staticmethod
    def archive_contract(
        db: Session,
        contract_id: str,
        signed_document_url: str,
    ) -> Contract:
        """合約完簽後歸檔作業 (上傳正式雙方簽署用印文件掃描件)"""
        contract = db.get(Contract, contract_id)
        if not contract:
            raise AppException(code="CONTRACT_NOT_FOUND", message="找不到合約", status_code=404)

        if contract.status != "APPROVED":
            raise AppException(code="NOT_APPROVED_FOR_ARCHIVE", message="未完簽合約不可執行歸檔", status_code=400)

        contract.signed_document_url = signed_document_url
        contract.archived_at = utc_now()
        db.commit()
        db.refresh(contract)
        return contract
