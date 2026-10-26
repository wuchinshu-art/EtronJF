from datetime import datetime, date, timedelta, timezone
import uuid
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.core.errors import AppException
from app.models.hr import Employee, Company, LeaveType
from app.models.overtime import OvertimeRequest
from app.models.workflow import WorkflowInstance, ApprovalAssignment
from app.core.overtime_calculator import calculate_overtime_minutes, check_overtime_overlap
from app.core.hr_rules import LeaveLedgerService
from app.core.workflow_engine import WorkflowEngine


def generate_overtime_request_number() -> str:
    """產生唯一加班單號：OT-YYYYMMDD-UUID前8碼"""
    now_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    short_uuid = uuid.uuid4().hex[:8].upper()
    return f"OT-{now_str}-{short_uuid}"


class OvertimeService:
    @staticmethod
    def create_overtime_request(
        db: Session,
        company_id: str,
        employee_id: str,
        start_time_utc: datetime,
        end_time_utc: datetime,
        reason: str,
        rest_minutes: int = 0,
        compensation_type: str = "COMPENSATORY_LEAVE",
    ) -> OvertimeRequest:
        """建立加班單草稿並試算時數與級距"""
        employee = db.get(Employee, employee_id)
        if not employee:
            raise AppException(code="EMPLOYEE_NOT_FOUND", message="找不到申請員工資料", status_code=404)

        # 檢驗防重疊
        check_overtime_overlap(db, employee_id, start_time_utc, end_time_utc)

        # 計算加班時數
        calc_result = calculate_overtime_minutes(
            db=db,
            employee=employee,
            start_time_utc=start_time_utc,
            end_time_utc=end_time_utc,
            rest_minutes=rest_minutes,
            compensation_type=compensation_type,
        )

        req_number = generate_overtime_request_number()
        ot_req = OvertimeRequest(
            company_id=company_id,
            employee_id=employee_id,
            request_number=req_number,
            start_time=start_time_utc,
            end_time=end_time_utc,
            rest_minutes=rest_minutes,
            total_minutes=calc_result["net_minutes"],
            day_type=calc_result["day_type"],
            compensation_type=compensation_type,
            comp_leave_minutes=calc_result["comp_leave_minutes"],
            reason=reason,
            status="DRAFT",
            revision=1,
        )
        db.add(ot_req)
        db.commit()
        db.refresh(ot_req)
        return ot_req

    @staticmethod
    def submit_overtime_request(
        db: Session,
        request_id: str,
        operator_employee_id: str,
        hr_window_employee_id: Optional[str] = None,
    ) -> OvertimeRequest:
        """
        送審加班單：
        1. 驗證加班單狀態 (DRAFT 或 RETURNED)
        2. 重新驗證防重疊
        3. 啟動 T05 簽核引擎管線 (直屬主管 -> 人事窗口)
        4. 單據狀態轉為 IN_REVIEW
        """
        ot_req = db.get(OvertimeRequest, request_id)
        if not ot_req:
            raise AppException(code="OVERTIME_REQUEST_NOT_FOUND", message="找不到加班單", status_code=404)

        if ot_req.employee_id != operator_employee_id:
            raise AppException(code="UNAUTHORIZED_SUBMITTER", message="僅申請人本人可送審該加班單", status_code=403)

        if ot_req.status not in ("DRAFT", "RETURNED"):
            raise AppException(
                code="INVALID_STATUS_FOR_SUBMIT",
                message=f"加班單當前狀態為 {ot_req.status}，不可重複送審",
                status_code=400,
            )

        # 重新確認重疊
        check_overtime_overlap(db, ot_req.employee_id, ot_req.start_time, ot_req.end_time, exclude_request_id=ot_req.id)

        # 準備簽核 Context
        context: Dict[str, Any] = {
            "minutes": ot_req.total_minutes,
            "day_type": ot_req.day_type,
            "compensation_type": ot_req.compensation_type,
        }
        if hr_window_employee_id:
            context["hr_window_id"] = hr_window_employee_id
            context["default_window_employee_id"] = hr_window_employee_id

        # 啟動簽核引擎 (OVERTIME 標竿流程：直屬主管審核 -> 人事窗口核對)
        wf_instance = WorkflowEngine.submit_document(
            db=db,
            company_id=ot_req.company_id,
            document_type="OVERTIME",
            document_id=ot_req.id,
            applicant_employee_id=ot_req.employee_id,
            context=context,
        )

        ot_req.workflow_instance_id = wf_instance.id
        ot_req.status = "IN_REVIEW"
        if ot_req.status == "RETURNED":
            ot_req.revision += 1

        db.commit()
        db.refresh(ot_req)
        return ot_req

    @staticmethod
    def process_approval(
        db: Session,
        assignment_id: str,
        operator_employee_id: str,
        action: str,  # APPROVE, REJECT, RETURN
        comments: Optional[str] = None,
        client_ip: Optional[str] = None,
    ) -> OvertimeRequest:
        """
        簽核節點推進並連動假額帳本：
        - 若核准且流程完簽 (APPROVED)：
          - 若選擇 COMPENSATORY_LEAVE (轉補休)：自動在 leave_ledger 帳本寫入 GRANT 給予補休假額 (有效期限 1 年)！
          - 若選擇 PAY (加班費)：標記待計薪清冊
        - 若駁回 (REJECT)：狀態轉為 REJECTED
        - 若退回 (RETURN)：狀態轉為 RETURNED
        """
        assignment = db.get(ApprovalAssignment, assignment_id)
        if not assignment:
            raise AppException(code="ASSIGNMENT_NOT_FOUND", message="找不到待簽核任務", status_code=404)

        wf_instance = db.get(WorkflowInstance, assignment.instance_id)
        if not wf_instance or wf_instance.document_type != "OVERTIME":
            raise AppException(code="INVALID_WORKFLOW_TYPE", message="此簽核實例非加班流程", status_code=400)

        ot_req = db.get(OvertimeRequest, wf_instance.document_id)
        if not ot_req:
            raise AppException(code="OVERTIME_REQUEST_NOT_FOUND", message="找不到關聯之加班單", status_code=404)

        # 執行簽核動作
        updated_instance = WorkflowEngine.execute_action(
            db=db,
            assignment_id=assignment_id,
            operator_employee_id=operator_employee_id,
            action=action,
            comments=comments,
            client_ip=client_ip,
        )

        if updated_instance.status == "APPROVED":
            ot_req.status = "APPROVED"

            # 補休入帳連動
            if ot_req.compensation_type == "COMPENSATORY_LEAVE" and ot_req.comp_leave_minutes > 0:
                # 尋找全域補休假別 (COMPENSATORY 或 COMP，不分公司)
                comp_leave_type = (
                    db.query(LeaveType)
                    .filter(
                        LeaveType.code.in_(["COMPENSATORY", "COMP", "COMP_LEAVE"]),
                    )
                    .first()
                )
                if not comp_leave_type:
                    # 自動確保存在全域補休假別
                    comp_leave_type = LeaveType(
                        id="LT-COMPENSATORY",
                        company_id=None,
                        code="COMPENSATORY",
                        name="補休",
                        unit="MINUTES",
                        requires_attachment=False,
                        is_paid=True,
                    )
                    db.add(comp_leave_type)
                    db.commit()
                    db.refresh(comp_leave_type)

                valid_from = ot_req.start_time.date()
                valid_to = valid_from + timedelta(days=365)  # 補休假額有效期限 1 年

                # 寫入假額帳本 (GRANT 給予分錄)
                LeaveLedgerService.grant_leave(
                    db=db,
                    company_id=ot_req.company_id,
                    employee_id=ot_req.employee_id,
                    leave_type_id=comp_leave_type.id,
                    amount_minutes=ot_req.comp_leave_minutes,
                    valid_from=valid_from,
                    valid_to=valid_to,
                    created_by=operator_employee_id,
                    reference_doc_id=ot_req.request_number,
                    notes=f"加班單完簽自動轉補休入帳 [單號: {ot_req.request_number}]",
                )

        elif updated_instance.status == "REJECTED":
            ot_req.status = "REJECTED"
        elif updated_instance.status == "RETURNED":
            ot_req.status = "RETURNED"

        db.commit()
        db.refresh(ot_req)
        return ot_req

    @staticmethod
    def cancel_overtime_request(
        db: Session,
        request_id: str,
        operator_employee_id: str,
    ) -> OvertimeRequest:
        """申請人抽單／撤回未核准加班單"""
        ot_req = db.get(OvertimeRequest, request_id)
        if not ot_req:
            raise AppException(code="OVERTIME_REQUEST_NOT_FOUND", message="找不到加班單", status_code=404)

        if ot_req.employee_id != operator_employee_id:
            raise AppException(code="UNAUTHORIZED_OPERATOR", message="僅申請人本人可撤回加班單", status_code=403)

        if ot_req.status not in ("DRAFT", "IN_REVIEW", "RETURNED"):
            raise AppException(
                code="CANNOT_CANCEL_OVERTIME",
                message=f"加班單狀態為 {ot_req.status}，無法撤銷",
                status_code=400,
            )

        if ot_req.status == "IN_REVIEW" and ot_req.workflow_instance_id:
            wf_instance = db.get(WorkflowInstance, ot_req.workflow_instance_id)
            if wf_instance:
                wf_instance.status = "CANCELLED"

        ot_req.status = "CANCELLED"
        db.commit()
        db.refresh(ot_req)
        return ot_req
