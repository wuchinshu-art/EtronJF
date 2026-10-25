import random
from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_

from app.core.errors import AppException
from app.models.hr import Employee, Company, Organization
from app.models.payment import Vendor, ExpenseClaim, ExpenseClaimItem, PaymentRequest
from app.models.workflow import WorkflowInstance, ApprovalAssignment
from app.core.workflow_engine import WorkflowEngine


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_claim_number() -> str:
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    rand_str = f"{random.randint(1000, 9999)}"
    return f"EXP-{today_str}-{rand_str}"


def generate_payment_number() -> str:
    today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    rand_str = f"{random.randint(1000, 9999)}"
    return f"PAY-{today_str}-{rand_str}"


class PaymentService:
    """費用報支、供應商主檔與請款業務領域服務 (Expense & Payment Domain Service)"""

    # --------------------------------------------------------------------------
    # 1. 供應商主檔管理 (Vendor Management)
    # --------------------------------------------------------------------------
    @staticmethod
    def create_vendor(
        db: Session,
        company_id: str,
        code: str,
        name: str,
        country: str = "TW",
        tax_id: Optional[str] = None,
        address: Optional[str] = None,
        contact_name: Optional[str] = None,
        contact_phone: Optional[str] = None,
        email: Optional[str] = None,
        payment_terms: str = "NET30",
        bank_country: Optional[str] = None,
        bank_name: Optional[str] = None,
        bank_code: Optional[str] = None,
        branch_name: Optional[str] = None,
        branch_code: Optional[str] = None,
        account_name: Optional[str] = None,
        account_number: Optional[str] = None,
        bank_currency: str = "TWD",
        swift_code: Optional[str] = None,
    ) -> Vendor:
        """建立供應商主檔"""
        existing = db.query(Vendor).filter(Vendor.company_id == company_id, Vendor.code == code).first()
        if existing:
            raise AppException(code="VENDOR_CODE_EXISTS", message=f"供應商代碼 [{code}] 已存在", status_code=400)

        vendor = Vendor(
            company_id=company_id,
            code=code,
            name=name,
            country=country,
            tax_id=tax_id,
            address=address,
            contact_name=contact_name,
            contact_phone=contact_phone,
            email=email,
            payment_terms=payment_terms,
            bank_country=bank_country,
            bank_name=bank_name,
            bank_code=bank_code,
            branch_name=branch_name,
            branch_code=branch_code,
            account_name=account_name,
            account_number=account_number,
            bank_currency=bank_currency,
            swift_code=swift_code,
            is_active=True,
            version=1,
        )
        db.add(vendor)
        db.commit()
        db.refresh(vendor)
        return vendor

    @staticmethod
    def get_vendor(db: Session, vendor_id: str, mask_bank_info: bool = True) -> Dict[str, Any]:
        """查詢供應商詳情（支援銀行帳號安全遮罩）"""
        vendor = db.get(Vendor, vendor_id)
        if not vendor:
            raise AppException(code="VENDOR_NOT_FOUND", message="找不到指定供應商", status_code=404)

        acc_num = vendor.masked_account_number() if mask_bank_info else vendor.account_number
        return {
            "id": vendor.id,
            "company_id": vendor.company_id,
            "code": vendor.code,
            "name": vendor.name,
            "country": vendor.country,
            "tax_id": vendor.tax_id,
            "address": vendor.address,
            "contact_name": vendor.contact_name,
            "contact_phone": vendor.contact_phone,
            "email": vendor.email,
            "payment_terms": vendor.payment_terms,
            "is_active": vendor.is_active,
            "bank_country": vendor.bank_country,
            "bank_name": vendor.bank_name,
            "bank_code": vendor.bank_code,
            "branch_name": vendor.branch_name,
            "branch_code": vendor.branch_code,
            "account_name": vendor.account_name,
            "account_number": acc_num,
            "bank_currency": vendor.bank_currency,
            "swift_code": vendor.swift_code,
            "version": vendor.version,
        }

    # --------------------------------------------------------------------------
    # 2. 費用報銷單管理 (Expense Claims)
    # --------------------------------------------------------------------------
    @staticmethod
    def check_duplicate_invoices(
        db: Session,
        company_id: str,
        items_data: List[Dict[str, Any]],
        exclude_claim_id: Optional[str] = None,
    ) -> bool:
        """
        可能重複憑證警示 (Potential Duplicate Invoice Warning)
        檢驗同公司內其他非取消/駁回的單據中，是否存在相同發票號碼且相同金額之項目。
        """
        for item in items_data:
            inv_num = item.get("invoice_number")
            amt = Decimal(str(item["amount"]))
            if not inv_num:
                continue

            query = (
                db.query(ExpenseClaimItem)
                .join(ExpenseClaim, ExpenseClaimItem.expense_claim_id == ExpenseClaim.id)
                .filter(
                    ExpenseClaim.company_id == company_id,
                    ExpenseClaimItem.invoice_number == inv_num,
                    ExpenseClaimItem.amount == amt,
                    ExpenseClaim.status.notin_(["REJECTED", "CANCELLED"]),
                )
            )
            if exclude_claim_id:
                query = query.filter(ExpenseClaim.id != exclude_claim_id)

            if query.first():
                return True
        return False

    @staticmethod
    def create_expense_claim(
        db: Session,
        company_id: str,
        employee_id: str,
        title: str,
        currency: str,
        exchange_rate: Decimal,
        items_data: List[Dict[str, Any]],
        cost_center: Optional[str] = None,
        tax_amount: Decimal = Decimal("0.0000"),
        notes: Optional[str] = None,
    ) -> ExpenseClaim:
        employee = db.get(Employee, employee_id) if employee_id and employee_id != "EMP-DEFAULT" else None
        if not employee:
            employee = db.query(Employee).filter(Employee.company_id == company_id, Employee.status == "ACTIVE").first()
            if not employee:
                raise AppException(code="EMPLOYEE_NOT_FOUND", message="找不到申請員工資料", status_code=404)
            employee_id = employee.id

        if not items_data:
            raise AppException(code="EMPTY_EXPENSE_ITEMS", message="費用報銷單必須包含至少一筆明細項", status_code=400)

        # 檢驗重複憑證警示
        has_warning = PaymentService.check_duplicate_invoices(
            db=db,
            company_id=company_id,
            items_data=items_data,
        )

        total_amount = Decimal("0.0000")
        total_amount_twd = Decimal("0.0000")
        claim_items: List[ExpenseClaimItem] = []

        for item in items_data:
            item_amt = Decimal(str(item["amount"]))
            item_rate = Decimal(str(item.get("exchange_rate", exchange_rate)))
            item_twd = (item_amt * item_rate).quantize(Decimal("0.0001"))

            total_amount += item_amt
            total_amount_twd += item_twd

            exp_item = ExpenseClaimItem(
                category=item["category"],
                expense_date=item["expense_date"],
                invoice_number=item.get("invoice_number"),
                currency=item.get("currency", currency),
                exchange_rate=item_rate,
                amount=item_amt,
                amount_twd=item_twd,
                description=item.get("description", ""),
                attachment_url=item.get("attachment_url"),
            )
            claim_items.append(exp_item)

        claim_num = generate_claim_number()
        expense_claim = ExpenseClaim(
            company_id=company_id,
            employee_id=employee_id,
            claim_number=claim_num,
            title=title,
            cost_center=cost_center,
            currency=currency,
            exchange_rate=exchange_rate,
            total_amount=total_amount,
            total_amount_twd=total_amount_twd,
            tax_amount=tax_amount,
            status="DRAFT",
            payment_status="UNPAID",
            has_duplicate_warning=has_warning,
            notes=notes,
            revision=1,
        )
        db.add(expense_claim)
        db.flush()

        for exp_item in claim_items:
            exp_item.expense_claim_id = expense_claim.id
            db.add(exp_item)

        db.commit()
        db.refresh(expense_claim)
        return expense_claim

    @staticmethod
    def submit_expense_claim(
        db: Session,
        claim_id: str,
        operator_employee_id: str,
        finance_window_employee_id: Optional[str] = None,
    ) -> ExpenseClaim:
        """
        送審費用報銷單：
        管線解析：直屬主管 -> 第二層主管 (>=5000) -> 第三層主管 (>=100000) -> 會計窗口
        """
        claim = db.get(ExpenseClaim, claim_id)
        if not claim:
            raise AppException(code="EXPENSE_CLAIM_NOT_FOUND", message="找不到費用報銷單", status_code=404)

        if claim.employee_id != operator_employee_id:
            raise AppException(code="UNAUTHORIZED_SUBMITTER", message="僅申請人本人可送審該報銷單", status_code=403)

        if claim.status not in ("DRAFT", "RETURNED"):
            raise AppException(
                code="INVALID_STATUS_FOR_SUBMIT",
                message=f"報銷單當前狀態為 {claim.status}，不可重複送審",
                status_code=400,
            )

        context: Dict[str, Any] = {
            "amount": float(claim.total_amount_twd),
        }
        if finance_window_employee_id:
            context["finance_window_id"] = finance_window_employee_id
            context["default_window_employee_id"] = finance_window_employee_id

        wf_instance = WorkflowEngine.submit_document(
            db=db,
            company_id=claim.company_id,
            document_type="EXPENSE",
            document_id=claim.id,
            applicant_employee_id=claim.employee_id,
            context=context,
        )

        claim.workflow_instance_id = wf_instance.id
        claim.status = "IN_REVIEW"
        if claim.status == "RETURNED":
            claim.revision += 1

        db.commit()
        db.refresh(claim)
        return claim

    @staticmethod
    def process_expense_approval(
        db: Session,
        assignment_id: str,
        operator_employee_id: str,
        action: str,  # APPROVE, REJECT, RETURN
        comments: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> ExpenseClaim:
        """推進費用報銷審批動作"""
        assignment = db.get(ApprovalAssignment, assignment_id)
        if not assignment:
            raise AppException(code="ASSIGNMENT_NOT_FOUND", message="找不到審核任務", status_code=404)

        wf_instance = db.get(WorkflowInstance, assignment.instance_id)
        if not wf_instance or wf_instance.document_type != "EXPENSE":
            raise AppException(code="INVALID_WORKFLOW_INSTANCE", message="簽核實例不匹配", status_code=400)

        claim = db.get(ExpenseClaim, wf_instance.document_id)
        if not claim:
            raise AppException(code="EXPENSE_CLAIM_NOT_FOUND", message="找不到對應之報銷單", status_code=404)

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
            claim.status = "APPROVED"
        elif wf_instance.status == "REJECTED":
            claim.status = "REJECTED"
        elif wf_instance.status == "RETURNED":
            claim.status = "RETURNED"

        db.commit()
        db.refresh(claim)
        return claim

    @staticmethod
    def confirm_expense_payment(
        db: Session,
        claim_id: str,
        operator_employee_id: str,
        paid_reference: str,
        settlement_exchange_rate: Optional[Decimal] = None,
    ) -> ExpenseClaim:
        """
        會計確認費用付款結清：
        - 檢查狀態必須為 APPROVED 且 UNPAID
        - 支援月結 ERP 匯兌損益調整核算
        """
        claim = db.get(ExpenseClaim, claim_id)
        if not claim:
            raise AppException(code="EXPENSE_CLAIM_NOT_FOUND", message="找不到報銷單", status_code=404)

        if claim.status != "APPROVED":
            raise AppException(code="NOT_APPROVED_FOR_PAYMENT", message="未審核核准之報銷單不可執行付款", status_code=400)

        if claim.payment_status == "PAID":
            raise AppException(code="ALREADY_PAID", message="該報銷單已完成付款結清，禁止重複確認", status_code=400)

        # 匯兌損益核算：amount * (settlement_exchange_rate - exchange_rate)
        if settlement_exchange_rate is not None and claim.currency != "TWD":
            diff_rate = settlement_exchange_rate - claim.exchange_rate
            gain_loss = (claim.total_amount * diff_rate).quantize(Decimal("0.0001"))
            claim.settlement_exchange_rate = settlement_exchange_rate
            claim.exchange_gain_loss = gain_loss

        claim.payment_status = "PAID"
        claim.paid_at = utc_now()
        claim.paid_reference = paid_reference

        db.commit()
        db.refresh(claim)
        return claim

    # --------------------------------------------------------------------------
    # 3. 供應商請款單管理 (Payment Requests)
    # --------------------------------------------------------------------------
    @staticmethod
    def create_payment_request(
        db: Session,
        company_id: str,
        employee_id: str,
        vendor_id: str,
        title: str,
        currency: str,
        exchange_rate: Decimal,
        amount: Decimal,
        due_date: date,
        payment_method: str = "WIRE",
        description: Optional[str] = None,
        invoice_number: Optional[str] = None,
        invoice_date: Optional[date] = None,
        attachment_url: Optional[str] = None,
    ) -> PaymentRequest:
        """
        建立供應商請款單：
        - 關聯供應商
        - **即刻建立供應商主檔與受款銀行資料不可變快照 (vendor_snapshot)**
        """
        employee = db.get(Employee, employee_id) if employee_id and employee_id != "EMP-DEFAULT" else None
        if not employee:
            employee = db.query(Employee).filter(Employee.company_id == company_id, Employee.status == "ACTIVE").first()
            if not employee:
                raise AppException(code="EMPLOYEE_NOT_FOUND", message="找不到申請員工資料", status_code=404)
            employee_id = employee.id

        vendor = db.get(Vendor, vendor_id)
        if not vendor or not vendor.is_active:
            raise AppException(code="VENDOR_INVALID", message="指定供應商不存在或已被停用", status_code=400)

        # 建立不可變快照 (Snapshot 不受主檔後續異動影響)
        vendor_snapshot = {
            "vendor_id": vendor.id,
            "code": vendor.code,
            "name": vendor.name,
            "tax_id": vendor.tax_id,
            "payment_terms": vendor.payment_terms,
            "bank_country": vendor.bank_country,
            "bank_name": vendor.bank_name,
            "bank_code": vendor.bank_code,
            "branch_name": vendor.branch_name,
            "branch_code": vendor.branch_code,
            "account_name": vendor.account_name,
            "account_number": vendor.account_number,
            "bank_currency": vendor.bank_currency,
            "swift_code": vendor.swift_code,
            "snapshot_at": utc_now().isoformat(),
        }

        amount_twd = (amount * exchange_rate).quantize(Decimal("0.0001"))
        pay_num = generate_payment_number()

        payment_req = PaymentRequest(
            company_id=company_id,
            employee_id=employee_id,
            vendor_id=vendor_id,
            payment_number=pay_num,
            title=title,
            description=description,
            vendor_snapshot=vendor_snapshot,
            currency=currency,
            exchange_rate=exchange_rate,
            amount=amount,
            amount_twd=amount_twd,
            due_date=due_date,
            payment_method=payment_method,
            invoice_number=invoice_number,
            invoice_date=invoice_date,
            attachment_url=attachment_url,
            status="DRAFT",
            payment_status="UNPAID",
            revision=1,
        )
        db.add(payment_req)
        db.commit()
        db.refresh(payment_req)
        return payment_req

    @staticmethod
    def submit_payment_request(
        db: Session,
        payment_id: str,
        operator_employee_id: str,
        dept_manager_id: Optional[str] = None,
        div_manager_id: Optional[str] = None,
        gm_id: Optional[str] = None,
        finance_window_employee_id: Optional[str] = None,
    ) -> PaymentRequest:
        """
        送審供應商請款單：
        管線解析：直屬主管 -> 部級主管 (>=5000) -> 處級主管 (>=100000) -> 總經理 (>=500000) -> 會計窗口
        """
        pay_req = db.get(PaymentRequest, payment_id)
        if not pay_req:
            raise AppException(code="PAYMENT_REQUEST_NOT_FOUND", message="找不到供應商請款單", status_code=404)

        if pay_req.employee_id != operator_employee_id:
            raise AppException(code="UNAUTHORIZED_SUBMITTER", message="僅申請人本人可送審該請款單", status_code=403)

        if pay_req.status not in ("DRAFT", "RETURNED"):
            raise AppException(
                code="INVALID_STATUS_FOR_SUBMIT",
                message=f"請款單當前狀態為 {pay_req.status}，不可重複送審",
                status_code=400,
            )

        context: Dict[str, Any] = {
            "amount": float(pay_req.amount_twd),
        }
        if dept_manager_id:
            context["org_dept_head_id"] = dept_manager_id
        if div_manager_id:
            context["org_div_head_id"] = div_manager_id
        if gm_id:
            context["gm_id"] = gm_id
        if finance_window_employee_id:
            context["finance_window_id"] = finance_window_employee_id
            context["default_window_employee_id"] = finance_window_employee_id

        wf_instance = WorkflowEngine.submit_document(
            db=db,
            company_id=pay_req.company_id,
            document_type="PAYMENT",
            document_id=pay_req.id,
            applicant_employee_id=pay_req.employee_id,
            context=context,
        )

        pay_req.workflow_instance_id = wf_instance.id
        pay_req.status = "IN_REVIEW"
        if pay_req.status == "RETURNED":
            pay_req.revision += 1

        db.commit()
        db.refresh(pay_req)
        return pay_req

    @staticmethod
    def process_payment_approval(
        db: Session,
        assignment_id: str,
        operator_employee_id: str,
        action: str,  # APPROVE, REJECT, RETURN
        comments: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> PaymentRequest:
        """推進供應商請款審批動作"""
        assignment = db.get(ApprovalAssignment, assignment_id)
        if not assignment:
            raise AppException(code="ASSIGNMENT_NOT_FOUND", message="找不到審核任務", status_code=404)

        wf_instance = db.get(WorkflowInstance, assignment.instance_id)
        if not wf_instance or wf_instance.document_type != "PAYMENT":
            raise AppException(code="INVALID_WORKFLOW_INSTANCE", message="簽核實例不匹配", status_code=400)

        pay_req = db.get(PaymentRequest, wf_instance.document_id)
        if not pay_req:
            raise AppException(code="PAYMENT_REQUEST_NOT_FOUND", message="找不到對應之請款單", status_code=404)

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
            pay_req.status = "APPROVED"
        elif wf_instance.status == "REJECTED":
            pay_req.status = "REJECTED"
        elif wf_instance.status == "RETURNED":
            pay_req.status = "RETURNED"

        db.commit()
        db.refresh(pay_req)
        return pay_req

    @staticmethod
    def confirm_vendor_payment(
        db: Session,
        payment_id: str,
        operator_employee_id: str,
        paid_reference: str,
        settlement_exchange_rate: Optional[Decimal] = None,
    ) -> PaymentRequest:
        """
        會計確認供應商款項支付／結清：
        - 檢查狀態必須為 APPROVED 且 UNPAID
        - 支援月結 ERP 匯兌損益調整核算
        """
        pay_req = db.get(PaymentRequest, payment_id)
        if not pay_req:
            raise AppException(code="PAYMENT_REQUEST_NOT_FOUND", message="找不到請款單", status_code=404)

        if pay_req.status != "APPROVED":
            raise AppException(code="NOT_APPROVED_FOR_PAYMENT", message="未審核核准之請款單不可執行付款", status_code=400)

        if pay_req.payment_status == "PAID":
            raise AppException(code="ALREADY_PAID", message="該請款單已完成付款結清，禁止重複確認", status_code=400)

        # 匯兌損益核算：amount * (settlement_exchange_rate - exchange_rate)
        if settlement_exchange_rate is not None and pay_req.currency != "TWD":
            diff_rate = settlement_exchange_rate - pay_req.exchange_rate
            gain_loss = (pay_req.amount * diff_rate).quantize(Decimal("0.0001"))
            pay_req.settlement_exchange_rate = settlement_exchange_rate
            pay_req.exchange_gain_loss = gain_loss

        pay_req.payment_status = "PAID"
        pay_req.paid_at = utc_now()
        pay_req.paid_reference = paid_reference

        db.commit()
        db.refresh(pay_req)
        return pay_req
