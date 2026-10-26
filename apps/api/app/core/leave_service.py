from datetime import datetime, date, timezone
import uuid
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.core.errors import AppException
from app.models.hr import Employee, Company, LeaveType
from app.models.leave import LeaveRequest
from app.models.workflow import WorkflowInstance, ApprovalAssignment
from app.core.leave_calculator import calculate_leave_minutes_and_days, check_leave_overlap
from app.core.hr_rules import LeaveLedgerService
from app.core.workflow_engine import WorkflowEngine


def generate_leave_request_number() -> str:
    """產生唯一請假單號：LV-YYYYMMDD-UUID前8碼"""
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_uuid = uuid.uuid4().hex[:8].upper()
    return f"LV-{now_str}-{short_uuid}"


class LeaveService:
    @staticmethod
    def create_leave_request(
        db: Session,
        company_id: str,
        employee_id: str,
        leave_type_id: str,
        start_time_utc: datetime,
        end_time_utc: datetime,
        reason: str,
        deputy_employee_id: Optional[str] = None,
        attachment_url: Optional[str] = None,
    ) -> LeaveRequest:
        """建立請假單草稿並試算工時"""
        employee = db.get(Employee, employee_id)
        if not employee:
            raise AppException(code="EMPLOYEE_NOT_FOUND", message="找不到申請員工資料", status_code=404)

        leave_type = db.get(LeaveType, leave_type_id)
        if not leave_type:
            leave_type = db.execute(
                select(LeaveType).where(
                    (LeaveType.code == leave_type_id.upper()) | (LeaveType.name == leave_type_id),
                )
            ).scalars().first()
        if not leave_type:
            standard_names = {
                "ANNUAL": "特別休假",
                "COMPENSATORY": "補休假",
                "OFFICIAL": "公假",
                "PERSONAL": "事假",
                "SICK": "普通傷病假",
                "FUNERAL": "喪假",
                "MARRIAGE": "婚假",
                "MATERNITY": "產假",
                "PATERNITY": "陪產假",
                "MENSTRUAL": "生理假",
                "OTHER": "其他假別",
            }
            code = leave_type_id.upper()
            name = standard_names.get(code, leave_type_id)
            leave_type = LeaveType(
                id=f"LT-{code}",
                company_id=None,
                code=code,
                name=name,
                unit="MINUTES",
                requires_attachment=(code in ["SICK", "FUNERAL", "MARRIAGE", "MATERNITY"]),
                is_paid=(code not in ["PERSONAL"]),
            )
            db.add(leave_type)
            db.flush()
        leave_type_id = leave_type.id

        if deputy_employee_id:
            deputy = db.get(Employee, deputy_employee_id)
            if not deputy:
                raise AppException(code="DEPUTY_NOT_FOUND", message="找不到指定代理人資料", status_code=404)
            if deputy_employee_id == employee_id:
                raise AppException(code="CANNOT_DEPUTIZE_SELF", message="申請人不可指定自己為代理人", status_code=400)

        # 檢驗防重疊
        check_leave_overlap(db, employee_id, start_time_utc, end_time_utc)

        # 折算工時
        total_minutes, calculated_days = calculate_leave_minutes_and_days(
            db, employee, start_time_utc, end_time_utc
        )

        if total_minutes <= 0:
            raise AppException(
                code="ZERO_WORK_MINUTES",
                message="請假區間內無有效工作工時（可能落在非工作日或非工作時段）",
                status_code=400,
            )

        req_number = generate_leave_request_number()
        leave_req = LeaveRequest(
            company_id=company_id,
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            request_number=req_number,
            start_time=start_time_utc,
            end_time=end_time_utc,
            total_minutes=total_minutes,
            calculated_days=calculated_days,
            reason=reason,
            deputy_employee_id=deputy_employee_id,
            attachment_url=attachment_url,
            status="DRAFT",
            revision=1,
        )
        db.add(leave_req)
        db.commit()
        db.refresh(leave_req)
        return leave_req

    @staticmethod
    def submit_leave_request(
        db: Session,
        request_id: str,
        operator_employee_id: str,
        hr_window_employee_id: Optional[str] = None,
    ) -> LeaveRequest:
        """
        送審請假單：
        1. 驗證請假單狀態 (DRAFT 或 RETURNED)
        2. 重新驗證防重疊與工時
        3. 假額帳本預占 (HOLD)，若可用餘額不足即刻拋錯 400
        4. 啟動 T05 簽核引擎管線，產生節點快照與待簽受派
        5. 假單狀態轉為 IN_REVIEW
        """
        leave_req = db.get(LeaveRequest, request_id)
        if not leave_req:
            raise AppException(code="LEAVE_REQUEST_NOT_FOUND", message="找不到請假單", status_code=404)

        if leave_req.employee_id != operator_employee_id:
            raise AppException(code="UNAUTHORIZED_SUBMITTER", message="僅申請人本人可送審該假單", status_code=403)

        if leave_req.status not in ("DRAFT", "RETURNED"):
            raise AppException(
                code="INVALID_STATUS_FOR_SUBMIT",
                message=f"假單當前狀態為 {leave_req.status}，不可重複送審",
                status_code=400,
            )

        employee = db.get(Employee, leave_req.employee_id)

        # 重新確認重疊
        check_leave_overlap(db, leave_req.employee_id, leave_req.start_time, leave_req.end_time, exclude_request_id=leave_req.id)

        # 帳本預占 HOLD
        start_date = leave_req.start_time.date()
        valid_to = date(start_date.year, 12, 31)
        LeaveLedgerService.hold_leave(
            db=db,
            company_id=leave_req.company_id,
            employee_id=leave_req.employee_id,
            leave_type_id=leave_req.leave_type_id,
            amount_minutes=leave_req.total_minutes,
            reference_doc_id=leave_req.request_number,
            valid_from=start_date,
            valid_to=valid_to,
            created_by=operator_employee_id,
        )

        # 準備簽核 Context
        context: Dict[str, Any] = {
            "days": float(leave_req.calculated_days),
            "minutes": leave_req.total_minutes,
        }
        if leave_req.deputy_employee_id:
            context["agent_id"] = leave_req.deputy_employee_id
            context["agent_employee_id"] = leave_req.deputy_employee_id

        if hr_window_employee_id:
            context["hr_window_id"] = hr_window_employee_id
            context["default_window_employee_id"] = hr_window_employee_id

        # 啟動簽核引擎
        wf_instance = WorkflowEngine.submit_document(
            db=db,
            company_id=leave_req.company_id,
            document_type="LEAVE",
            document_id=leave_req.id,
            applicant_employee_id=leave_req.employee_id,
            context=context,
        )

        leave_req.workflow_instance_id = wf_instance.id
        leave_req.status = "IN_REVIEW"
        if leave_req.status == "RETURNED":
            leave_req.revision += 1

        db.commit()
        db.refresh(leave_req)
        return leave_req

    @staticmethod
    def process_approval(
        db: Session,
        assignment_id: str,
        operator_employee_id: str,
        action: str,  # APPROVE, REJECT, RETURN
        comments: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> LeaveRequest:
        """
        簽核節點推進並連動假額帳本：
        - 若核准且流程完簽 (APPROVED) -> 假單狀態轉 APPROVED，帳本預占轉扣抵 (COMMIT)
        - 若駁回 (REJECT) -> 假單狀態轉 REJECTED，帳本預占釋放 (RELEASE)
        - 若退回 (RETURN) -> 假單狀態轉 RETURNED，帳本預占釋放 (RELEASE)
        """
        assignment = db.get(ApprovalAssignment, assignment_id)
        if not assignment:
            raise AppException(code="ASSIGNMENT_NOT_FOUND", message="找不到待簽核任務", status_code=404)

        wf_instance = db.get(WorkflowInstance, assignment.instance_id)
        if not wf_instance or wf_instance.document_type != "LEAVE":
            raise AppException(code="INVALID_WORKFLOW_TYPE", message="此簽核實例非請假流程", status_code=400)

        leave_req = db.get(LeaveRequest, wf_instance.document_id)
        if not leave_req:
            raise AppException(code="LEAVE_REQUEST_NOT_FOUND", message="找不到關聯之請假單", status_code=404)

        # 執行簽核動作
        updated_instance = WorkflowEngine.execute_action(
            db=db,
            assignment_id=assignment_id,
            operator_employee_id=operator_employee_id,
            action=action,
            comments=comments,
            client_ip=client_ip,
        )

        start_date = leave_req.start_time.date()
        valid_to = date(start_date.year, 12, 31)

        # 根據流程最新狀態連動帳本
        if updated_instance.status == "APPROVED":
            leave_req.status = "APPROVED"
            # 正式扣抵
            LeaveLedgerService.commit_leave(
                db=db,
                company_id=leave_req.company_id,
                employee_id=leave_req.employee_id,
                leave_type_id=leave_req.leave_type_id,
                amount_minutes=leave_req.total_minutes,
                reference_doc_id=leave_req.request_number,
                valid_from=start_date,
                valid_to=valid_to,
                created_by=operator_employee_id,
            )
            # 沖銷並釋放先前的 HOLD 預占
            LeaveLedgerService.release_leave(
                db=db,
                company_id=leave_req.company_id,
                employee_id=leave_req.employee_id,
                leave_type_id=leave_req.leave_type_id,
                amount_minutes=leave_req.total_minutes,
                reference_doc_id=leave_req.request_number,
                valid_from=start_date,
                valid_to=valid_to,
                created_by=operator_employee_id,
            )
        elif updated_instance.status == "REJECTED":
            leave_req.status = "REJECTED"
            LeaveLedgerService.release_leave(
                db=db,
                company_id=leave_req.company_id,
                employee_id=leave_req.employee_id,
                leave_type_id=leave_req.leave_type_id,
                amount_minutes=leave_req.total_minutes,
                reference_doc_id=leave_req.request_number,
                valid_from=start_date,
                valid_to=valid_to,
                created_by=operator_employee_id,
            )
        elif updated_instance.status == "RETURNED":
            leave_req.status = "RETURNED"
            LeaveLedgerService.release_leave(
                db=db,
                company_id=leave_req.company_id,
                employee_id=leave_req.employee_id,
                leave_type_id=leave_req.leave_type_id,
                amount_minutes=leave_req.total_minutes,
                reference_doc_id=leave_req.request_number,
                valid_from=start_date,
                valid_to=valid_to,
                created_by=operator_employee_id,
            )

        db.commit()
        db.refresh(leave_req)
        return leave_req

    @staticmethod
    def cancel_leave_request(
        db: Session,
        request_id: str,
        operator_employee_id: str,
    ) -> LeaveRequest:
        """申請人抽單／撤回未核准假單，並釋放帳本預占"""
        leave_req = db.get(LeaveRequest, request_id)
        if not leave_req:
            raise AppException(code="LEAVE_REQUEST_NOT_FOUND", message="找不到請假單", status_code=404)

        if leave_req.employee_id != operator_employee_id:
            raise AppException(code="UNAUTHORIZED_OPERATOR", message="僅申請人本人可撤回假單", status_code=403)

        if leave_req.status not in ("DRAFT", "IN_REVIEW", "RETURNED"):
            raise AppException(
                code="CANNOT_CANCEL_LEAVE",
                message=f"假單狀態為 {leave_req.status}，無法撤銷",
                status_code=400,
            )

        if leave_req.status == "IN_REVIEW":
            # 釋放預占
            start_date = leave_req.start_time.date()
            valid_to = date(start_date.year, 12, 31)
            LeaveLedgerService.release_leave(
                db=db,
                company_id=leave_req.company_id,
                employee_id=leave_req.employee_id,
                leave_type_id=leave_req.leave_type_id,
                amount_minutes=leave_req.total_minutes,
                reference_doc_id=leave_req.request_number,
                valid_from=start_date,
                valid_to=valid_to,
                created_by=operator_employee_id,
            )
            # 若有進行中的工作流，將實例改為 CANCELLED
            if leave_req.workflow_instance_id:
                wf_instance = db.get(WorkflowInstance, leave_req.workflow_instance_id)
                if wf_instance:
                    wf_instance.status = "CANCELLED"

        leave_req.status = "CANCELLED"
        db.commit()
        db.refresh(leave_req)
        return leave_req
