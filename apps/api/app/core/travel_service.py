from datetime import datetime, date, timezone
from decimal import Decimal
import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session

from app.core.errors import AppException
from app.models.hr import Employee, Company
from app.models.travel import TravelRequest, TravelSettlement, TravelExpenseItem
from app.models.workflow import WorkflowInstance, ApprovalAssignment
from app.core.workflow_engine import WorkflowEngine


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def generate_travel_request_number() -> str:
    """產生唯一出差申請單號：TR-YYYYMMDD-UUID8"""
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_uuid = uuid.uuid4().hex[:8].upper()
    return f"TR-{now_str}-{short_uuid}"


def generate_settlement_number() -> str:
    """產生唯一出差結報單號：TS-YYYYMMDD-UUID8"""
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_uuid = uuid.uuid4().hex[:8].upper()
    return f"TS-{now_str}-{short_uuid}"


class TravelService:
    @staticmethod
    def create_travel_request(
        db: Session,
        company_id: str,
        employee_id: str,
        title: str,
        destination: str,
        start_date: date,
        end_date: date,
        estimated_days: Decimal,
        transport_mode: str,
        purpose: str,
        deputy_employee_id: Optional[str] = None,
        has_advance: bool = False,
        advance_currency: str = "TWD",
        advance_amount: Decimal = Decimal("0.0000"),
        region_type: str = "DOMESTIC",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        estimated_nights: int = 0,
        transport_modes: Optional[List[str]] = None,
        transport_other: Optional[str] = None,
        needs_accommodation: bool = False,
        accommodation_plan: Optional[str] = None,
        companions: Optional[str] = None,
        visiting_target: Optional[str] = None,
        planned_agenda: Optional[str] = None,
        expected_results: Optional[str] = None,
        estimated_transport_cost: Decimal = Decimal("0.00"),
        estimated_accommodation_cost: Decimal = Decimal("0.00"),
        estimated_daily_cost: Decimal = Decimal("0.00"),
        estimated_other_cost: Decimal = Decimal("0.00"),
        estimated_total_cost: Decimal = Decimal("0.00"),
        notes: Optional[str] = None,
    ) -> TravelRequest:
        employee = db.get(Employee, employee_id) if employee_id and employee_id != "EMP-DEFAULT" else None
        if not employee:
            employee = db.query(Employee).filter(Employee.company_id == company_id, Employee.status == "ACTIVE").first()
            if not employee:
                raise AppException(code="EMPLOYEE_NOT_FOUND", message="找不到申請員工資料", status_code=404)
            employee_id = employee.id

        if start_date > end_date:
            raise AppException(code="INVALID_TRAVEL_DATE_RANGE", message="出差起日不可晚於訖日", status_code=400)

        if deputy_employee_id:
            deputy = db.get(Employee, deputy_employee_id)
            if not deputy:
                raise AppException(code="DEPUTY_NOT_FOUND", message="找不到指定的代理人資料", status_code=404)
            if deputy_employee_id == employee_id:
                raise AppException(code="CANNOT_DEPUTIZE_SELF", message="申請人不可指定自己為職務代理人", status_code=400)

        req_number = generate_travel_request_number()
        travel_req = TravelRequest(
            company_id=company_id,
            employee_id=employee_id,
            request_number=req_number,
            title=title,
            destination=destination,
            region_type=region_type,
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            estimated_days=estimated_days,
            estimated_nights=estimated_nights,
            transport_mode=transport_mode,
            transport_modes=transport_modes,
            transport_other=transport_other,
            needs_accommodation=needs_accommodation,
            accommodation_plan=accommodation_plan,
            companions=companions,
            visiting_target=visiting_target,
            planned_agenda=planned_agenda,
            expected_results=expected_results,
            estimated_transport_cost=estimated_transport_cost,
            estimated_accommodation_cost=estimated_accommodation_cost,
            estimated_daily_cost=estimated_daily_cost,
            estimated_other_cost=estimated_other_cost,
            estimated_total_cost=estimated_total_cost,
            notes=notes,
            purpose=purpose,
            deputy_employee_id=deputy_employee_id,
            has_advance=has_advance,
            advance_currency=advance_currency,
            advance_amount=advance_amount,
            status="DRAFT",
            settlement_status="UNSETTLED",
            revision=1,
        )
        db.add(travel_req)
        db.commit()
        db.refresh(travel_req)
        return travel_req

    @staticmethod
    def submit_travel_request(
        db: Session,
        request_id: str,
        operator_employee_id: str,
        finance_window_employee_id: Optional[str] = None,
        hr_window_employee_id: Optional[str] = None,
    ) -> TravelRequest:
        """
        送審出差申請單：
        管線解析：
        - 若有預支款 (has_advance==true)：代理人 -> 直屬主管 -> 會計窗口 -> 人事窗口
        - 若無預支款 (has_advance==false)：代理人 -> 直屬主管 -> 人事窗口
        """
        travel_req = db.get(TravelRequest, request_id)
        if not travel_req:
            raise AppException(code="TRAVEL_REQUEST_NOT_FOUND", message="找不到出差申請單", status_code=404)

        if travel_req.employee_id != operator_employee_id:
            raise AppException(code="UNAUTHORIZED_SUBMITTER", message="僅申請人本人可送審該出差單", status_code=403)

        if travel_req.status not in ("DRAFT", "RETURNED"):
            raise AppException(
                code="INVALID_STATUS_FOR_SUBMIT",
                message=f"出差單當前狀態為 {travel_req.status}，不可重複送審",
                status_code=400,
            )

        context: Dict[str, Any] = {
            "has_advance": "true" if travel_req.has_advance else "false",
            "advance_amount": float(travel_req.advance_amount),
            "estimated_days": float(travel_req.estimated_days),
        }
        if travel_req.deputy_employee_id:
            context["agent_id"] = travel_req.deputy_employee_id
            context["agent_employee_id"] = travel_req.deputy_employee_id

        if finance_window_employee_id:
            context["finance_window_id"] = finance_window_employee_id
        if hr_window_employee_id:
            context["hr_window_id"] = hr_window_employee_id
            context["default_window_employee_id"] = hr_window_employee_id

        wf_instance = WorkflowEngine.submit_document(
            db=db,
            company_id=travel_req.company_id,
            document_type="TRAVEL",
            document_id=travel_req.id,
            applicant_employee_id=travel_req.employee_id,
            context=context,
        )

        travel_req.workflow_instance_id = wf_instance.id
        travel_req.status = "IN_REVIEW"
        if travel_req.status == "RETURNED":
            travel_req.revision += 1

        db.commit()
        db.refresh(travel_req)
        return travel_req

    @staticmethod
    def process_travel_approval(
        db: Session,
        assignment_id: str,
        operator_employee_id: str,
        action: str,  # APPROVE, REJECT, RETURN
        comments: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> TravelRequest:
        """出差申請單簽核動作推進"""
        assignment = db.get(ApprovalAssignment, assignment_id)
        if not assignment:
            raise AppException(code="ASSIGNMENT_NOT_FOUND", message="找不到待簽核任務", status_code=404)

        wf_instance = db.get(WorkflowInstance, assignment.instance_id)
        if not wf_instance or wf_instance.document_type != "TRAVEL":
            raise AppException(code="INVALID_WORKFLOW_TYPE", message="此簽核實例非出差申請流程", status_code=400)

        travel_req = db.get(TravelRequest, wf_instance.document_id)
        if not travel_req:
            raise AppException(code="TRAVEL_REQUEST_NOT_FOUND", message="找不到關聯之出差申請單", status_code=404)

        updated_instance = WorkflowEngine.execute_action(
            db=db,
            assignment_id=assignment_id,
            operator_employee_id=operator_employee_id,
            action=action,
            comments=comments,
            client_ip=client_ip,
        )

        if updated_instance.status == "APPROVED":
            travel_req.status = "APPROVED"
        elif updated_instance.status == "REJECTED":
            travel_req.status = "REJECTED"
        elif updated_instance.status == "RETURNED":
            travel_req.status = "RETURNED"

        db.commit()
        db.refresh(travel_req)
        return travel_req

    @staticmethod
    def create_travel_settlement(
        db: Session,
        company_id: str,
        employee_id: str,
        travel_request_id: str,
        currency: str,
        exchange_rate: Decimal,
        items_data: List[Dict[str, Any]],
        notes: Optional[str] = None,
    ) -> TravelSettlement:
        """
        建立出差結報單：
        1. 檢查關聯出差申請單狀態必須為 APPROVED
        2. 檢查未曾結報 (settlement_status == UNSETTLED)，防止重複報支
        3. 計算費用明細項折合本位幣
        4. 扣除預支款抵扣額，精確計算應補發/應繳回金額
        """
        travel_req = db.get(TravelRequest, travel_request_id)
        if not travel_req:
            raise AppException(code="TRAVEL_REQUEST_NOT_FOUND", message="找不到對應之出差申請單", status_code=404)

        if travel_req.status != "APPROVED":
            raise AppException(
                code="TRAVEL_NOT_APPROVED_FOR_SETTLEMENT",
                message=f"出差申請單尚未完簽核准 (目前狀態: {travel_req.status})，無法開立結報單",
                status_code=400,
            )

        if travel_req.settlement_status != "UNSETTLED":
            raise AppException(
                code="TRAVEL_ALREADY_SETTLED_OR_SETTLING",
                message=f"該出差單已處於結報狀態 ({travel_req.settlement_status})，禁止重複開立結報單",
                status_code=400,
            )

        if not items_data:
            raise AppException(code="EMPTY_EXPENSE_ITEMS", message="結報單必須至少包含一筆費用明細", status_code=400)

        total_actual_amount = Decimal("0.0000")
        total_actual_twd = Decimal("0.0000")
        expense_items: List[TravelExpenseItem] = []

        for item in items_data:
            item_amt = Decimal(str(item["amount"]))
            item_rate = Decimal(str(item.get("exchange_rate", exchange_rate)))
            item_twd = (item_amt * item_rate).quantize(Decimal("0.0001"))

            total_actual_amount += item_amt
            total_actual_twd += item_twd

            exp_item = TravelExpenseItem(
                expense_category=item["expense_category"],
                expense_date=item["expense_date"],
                currency=item.get("currency", currency),
                exchange_rate=item_rate,
                amount=item_amt,
                amount_twd=item_twd,
                invoice_number=item.get("invoice_number"),
                description=item.get("description", ""),
                attachment_url=item.get("attachment_url"),
            )
            expense_items.append(exp_item)

        # 預支款抵扣核算
        advance_offset = Decimal("0.0000")
        if travel_req.has_advance and travel_req.advance_amount > 0:
            # 預支款以其幣別與匯率折合本位幣抵扣
            advance_offset = (travel_req.advance_amount * exchange_rate).quantize(Decimal("0.0001"))

        # 應補發(正數) / 應退繳回(負數)
        net_payable = total_actual_twd - advance_offset

        settlement_num = generate_settlement_number()
        settlement = TravelSettlement(
            company_id=company_id,
            employee_id=employee_id,
            travel_request_id=travel_request_id,
            settlement_number=settlement_num,
            currency=currency,
            exchange_rate=exchange_rate,
            total_actual_amount=total_actual_amount,
            total_actual_twd=total_actual_twd,
            advance_offset_amount=advance_offset,
            net_payable_amount=net_payable,
            notes=notes,
            receipt_count=len(expense_items),
            status="DRAFT",
            payment_status="UNPAID",
            revision=1,
        )
        db.add(settlement)
        db.flush()

        for exp_item in expense_items:
            exp_item.settlement_id = settlement.id
            db.add(exp_item)

        travel_req.settlement_status = "SETTLING"
        db.commit()
        db.refresh(settlement)
        return settlement

    @staticmethod
    def submit_travel_settlement(
        db: Session,
        settlement_id: str,
        operator_employee_id: str,
        finance_window_employee_id: Optional[str] = None,
    ) -> TravelSettlement:
        """
        送審出差結報單：
        管線：直屬主管審核 -> 會計窗口審核
        """
        settlement = db.get(TravelSettlement, settlement_id)
        if not settlement:
            raise AppException(code="SETTLEMENT_NOT_FOUND", message="找不到出差結報單", status_code=404)

        if settlement.employee_id != operator_employee_id:
            raise AppException(code="UNAUTHORIZED_SUBMITTER", message="僅申請人本人可送審該結報單", status_code=403)

        if settlement.status not in ("DRAFT", "RETURNED"):
            raise AppException(
                code="INVALID_STATUS_FOR_SUBMIT",
                message=f"結報單當前狀態為 {settlement.status}，不可重複送審",
                status_code=400,
            )

        context: Dict[str, Any] = {
            "amount": float(settlement.total_actual_twd),
            "net_payable": float(settlement.net_payable_amount),
        }
        if finance_window_employee_id:
            context["finance_window_id"] = finance_window_employee_id
            context["default_window_employee_id"] = finance_window_employee_id

        wf_instance = WorkflowEngine.submit_document(
            db=db,
            company_id=settlement.company_id,
            document_type="TRAVEL_SETTLEMENT",
            document_id=settlement.id,
            applicant_employee_id=settlement.employee_id,
            context=context,
        )

        settlement.workflow_instance_id = wf_instance.id
        settlement.status = "IN_REVIEW"
        if settlement.status == "RETURNED":
            settlement.revision += 1

        db.commit()
        db.refresh(settlement)
        return settlement

    @staticmethod
    def process_settlement_approval(
        db: Session,
        assignment_id: str,
        operator_employee_id: str,
        action: str,  # APPROVE, REJECT, RETURN
        comments: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> TravelSettlement:
        """出差結報單簽核推進"""
        assignment = db.get(ApprovalAssignment, assignment_id)
        if not assignment:
            raise AppException(code="ASSIGNMENT_NOT_FOUND", message="找不到待簽核任務", status_code=404)

        wf_instance = db.get(WorkflowInstance, assignment.instance_id)
        if not wf_instance or wf_instance.document_type != "TRAVEL_SETTLEMENT":
            raise AppException(code="INVALID_WORKFLOW_TYPE", message="此簽核實例非出差結報流程", status_code=400)

        settlement = db.get(TravelSettlement, wf_instance.document_id)
        if not settlement:
            raise AppException(code="SETTLEMENT_NOT_FOUND", message="找不到關聯之出差結報單", status_code=404)

        updated_instance = WorkflowEngine.execute_action(
            db=db,
            assignment_id=assignment_id,
            operator_employee_id=operator_employee_id,
            action=action,
            comments=comments,
            client_ip=client_ip,
        )

        travel_req = db.get(TravelRequest, settlement.travel_request_id)

        if updated_instance.status == "APPROVED":
            settlement.status = "APPROVED"
            settlement.payment_status = "UNPAID"  # 進入會計待付款/待結清狀態
            if travel_req:
                travel_req.settlement_status = "SETTLED"
        elif updated_instance.status == "REJECTED":
            settlement.status = "REJECTED"
            if travel_req:
                travel_req.settlement_status = "UNSETTLED"  # 駁回後允許重新結報
        elif updated_instance.status == "RETURNED":
            settlement.status = "RETURNED"

        db.commit()
        db.refresh(settlement)
        return settlement

    @staticmethod
    def confirm_payment(
        db: Session,
        settlement_id: str,
        operator_employee_id: str,
        paid_reference: str,
    ) -> TravelSettlement:
        """會計確認完成出差款項支付／退繳沖銷入帳"""
        settlement = db.get(TravelSettlement, settlement_id)
        if not settlement:
            raise AppException(code="SETTLEMENT_NOT_FOUND", message="找不到出差結報單", status_code=404)

        if settlement.status != "APPROVED":
            raise AppException(code="SETTLEMENT_NOT_APPROVED", message="僅已完簽核准之結報單可執行會計付款結清", status_code=400)

        if settlement.payment_status == "PAID":
            raise AppException(code="ALREADY_PAID", message="該結報單已完成付款沖銷，不可重複處理", status_code=400)

        settlement.payment_status = "PAID"
        settlement.paid_at = utc_now()
        settlement.paid_reference = paid_reference

        db.commit()
        db.refresh(settlement)
        return settlement
