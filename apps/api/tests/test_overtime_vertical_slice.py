import pytest
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from app.core.time import TIMEZONE_TAIPEI
from app.core.errors import AppException
from app.models.auth import User
from app.models.hr import (
    Company,
    Organization,
    Employee,
    ManagerRelation,
    Shift,
    CalendarDay,
    LeaveType,
    LeaveLedger,
)
from app.models.overtime import OvertimeRequest
from app.models.workflow import WorkflowInstance, ApprovalAssignment
from app.core.overtime_calculator import calculate_overtime_minutes, check_overtime_overlap
from app.core.overtime_service import OvertimeService
from app.core.hr_rules import LeaveLedgerService


def setup_overtime_test_environment(db: Session):
    """建立加班垂直切片測試所需完整環境 (公司、組織、主管鏈、班別、日曆)"""
    # 1. 公司與班別
    company = Company(
        id="comp-tw",
        name="台灣總部",
        default_timezone="Asia/Taipei",
        default_currency="TWD",
    )
    db.add(company)
    db.commit()

    shift = Shift(
        id="shift-std",
        company_id="comp-tw",
        code="STD",
        name="常日班",
        work_start_time="09:00",
        work_end_time="18:00",
        break_minutes=60,
        daily_standard_minutes=480,
        is_overnight=False,
    )
    org = Organization(id="org-it", company_id="comp-tw", code="IT", name="資訊部")
    db.add_all([shift, org])
    db.commit()

    # 2. 員工與直屬主管 + 人事窗口
    emp_app = Employee(
        id="emp-app",
        company_id="comp-tw",
        organization_id="org-it",
        employee_no="TW002",
        full_name="申請人小明",
        email="applicant@etronjf8.com",
        hire_date=date(2025, 1, 1),
    )
    emp_mgr = Employee(
        id="emp-mgr",
        company_id="comp-tw",
        organization_id="org-it",
        employee_no="TW003",
        full_name="直屬主管大李",
        email="mgr@etronjf8.com",
        hire_date=date(2024, 1, 1),
    )
    emp_hr = Employee(
        id="emp-hr",
        company_id="comp-tw",
        organization_id="org-it",
        employee_no="TW006",
        full_name="人事窗口小芳",
        email="hr@etronjf8.com",
        hire_date=date(2024, 1, 1),
    )
    db.add_all([emp_app, emp_mgr, emp_hr])
    db.commit()

    rel1 = ManagerRelation(
        employee_id="emp-app",
        manager_id="emp-mgr",
        relation_type="DIRECT",
        effective_from=date(2025, 1, 1),
    )
    db.add(rel1)
    db.commit()

    # 3. 日曆設定：2026-10-23 (週五 平日), 2026-10-24 (週六 休息日), 2026-10-25 (週日 例假日)
    cal1 = CalendarDay(company_id="comp-tw", calendar_date=date(2026, 10, 23), is_working_day=True, day_type="REGULAR")
    cal2 = CalendarDay(company_id="comp-tw", calendar_date=date(2026, 10, 24), is_working_day=False, day_type="REST_DAY", holiday_name="休息日")
    cal3 = CalendarDay(company_id="comp-tw", calendar_date=date(2026, 10, 25), is_working_day=False, day_type="REGULAR_HOLIDAY", holiday_name="例假日")
    db.add_all([cal1, cal2, cal3])
    db.commit()


def test_overtime_calculation_regular_and_holiday(db_session: Session):
    """
    測試 1：加班工時計算與日別分段
    - 平日加班：18:30 ~ 22:30 (4小時=240分)，扣除用餐30分 -> 淨工時210分 (前2小時120分 + 第2級距90分)
    - 休息日加班：09:00 ~ 18:00 (9小時=540分)，扣除用餐60分 -> 淨工時480分 (前2小時120分 + 3~8小時360分)
    """
    setup_overtime_test_environment(db_session)
    emp = db_session.get(Employee, "emp-app")

    # 平日加班：2026-10-23 18:30 ~ 22:30 台北時間 (10:30 ~ 14:30 UTC)
    start_utc = datetime(2026, 10, 23, 10, 30, tzinfo=timezone.utc)
    end_utc = datetime(2026, 10, 23, 14, 30, tzinfo=timezone.utc)
    res_reg = calculate_overtime_minutes(
        db=db_session,
        employee=emp,
        start_time_utc=start_utc,
        end_time_utc=end_utc,
        rest_minutes=30,
        compensation_type="COMPENSATORY_LEAVE",
    )
    assert res_reg["net_minutes"] == 210
    assert res_reg["day_type"] == "REGULAR"
    assert res_reg["tier1_minutes"] == 120
    assert res_reg["tier2_minutes"] == 90
    assert res_reg["comp_leave_minutes"] == 210

    # 休息日加班：2026-10-24 09:00 ~ 18:00 台北時間 (01:00 ~ 10:00 UTC)
    start_sat_utc = datetime(2026, 10, 24, 1, 0, tzinfo=timezone.utc)
    end_sat_utc = datetime(2026, 10, 24, 10, 0, tzinfo=timezone.utc)
    res_sat = calculate_overtime_minutes(
        db=db_session,
        employee=emp,
        start_time_utc=start_sat_utc,
        end_time_utc=end_sat_utc,
        rest_minutes=60,
        compensation_type="COMPENSATORY_LEAVE",
    )
    assert res_sat["net_minutes"] == 480
    assert res_sat["day_type"] == "REST_DAY"
    assert res_sat["tier1_minutes"] == 120
    assert res_sat["tier2_minutes"] == 360
    assert res_sat["tier3_minutes"] == 0


def test_overtime_comp_leave_grant_to_leave_ledger(db_session: Session):
    """
    測試 2：加班完簽自動入帳假額帳本 (GRANT 補休)
    - 申請加班選擇 COMPENSATORY_LEAVE (240 分鐘)
    - 直屬主管審核 -> 人事窗口核備
    - 完簽後 leave_ledger 自動寫入 GRANT 240 分鐘補休，可用額度增加 240
    """
    setup_overtime_test_environment(db_session)

    start_utc = datetime(2026, 10, 23, 10, 30, tzinfo=timezone.utc)
    end_utc = datetime(2026, 10, 23, 14, 30, tzinfo=timezone.utc)

    # 建立並送審加班單
    ot_req = OvertimeService.create_overtime_request(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        start_time_utc=start_utc,
        end_time_utc=end_utc,
        reason="雙十一電商專案大促系統壓測",
        rest_minutes=0,
        compensation_type="COMPENSATORY_LEAVE",
    )
    assert ot_req.total_minutes == 240
    assert ot_req.comp_leave_minutes == 240

    OvertimeService.submit_overtime_request(db_session, ot_req.id, "emp-app", hr_window_employee_id="emp-hr")
    assert ot_req.status == "IN_REVIEW"

    # 節點 1：直屬主管大李審核
    assign1 = db_session.query(ApprovalAssignment).filter(
        ApprovalAssignment.instance_id == ot_req.workflow_instance_id,
        ApprovalAssignment.assigned_employee_id == "emp-mgr",
        ApprovalAssignment.is_completed == False,
    ).one()
    OvertimeService.process_approval(db_session, assign1.id, "emp-mgr", "APPROVE", comments="主管核可")

    # 節點 2：人事窗口小芳完簽核備 -> 完簽！
    assign2 = db_session.query(ApprovalAssignment).filter(
        ApprovalAssignment.instance_id == ot_req.workflow_instance_id,
        ApprovalAssignment.assigned_employee_id == "emp-hr",
        ApprovalAssignment.is_completed == False,
    ).one()
    OvertimeService.process_approval(db_session, assign2.id, "emp-hr", "APPROVE", comments="人事確認加班工時")

    db_session.refresh(ot_req)
    assert ot_req.status == "APPROVED"

    # 驗證補休假額已自動 GRANT 入帳 leave_ledger
    ledger_entries = db_session.query(LeaveLedger).filter(
        LeaveLedger.employee_id == "emp-app",
        LeaveLedger.entry_type == "GRANT",
    ).all()
    assert len(ledger_entries) == 1
    assert ledger_entries[0].amount_minutes == 240
    assert ledger_entries[0].reference_doc_id == ot_req.request_number

    # 驗證可用補休額度為 240 分鐘
    comp_type = db_session.query(LeaveType).filter(LeaveType.code == "COMPENSATORY").one()
    bal = LeaveLedgerService.get_available_balance(db_session, "emp-app", comp_type.id)
    assert bal == 240


def test_overtime_pay_choice_no_leave_granted(db_session: Session):
    """
    測試 3：加班選擇領取加班費 (PAY)，完簽不入補休假額帳本
    """
    setup_overtime_test_environment(db_session)

    start_utc = datetime(2026, 10, 23, 10, 30, tzinfo=timezone.utc)
    end_utc = datetime(2026, 10, 23, 14, 30, tzinfo=timezone.utc)

    ot_req = OvertimeService.create_overtime_request(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        start_time_utc=start_utc,
        end_time_utc=end_utc,
        reason="生產線急單加班",
        rest_minutes=0,
        compensation_type="PAY",
    )
    assert ot_req.comp_leave_minutes == 0

    OvertimeService.submit_overtime_request(db_session, ot_req.id, "emp-app", hr_window_employee_id="emp-hr")

    # 主管核准
    assign1 = db_session.query(ApprovalAssignment).filter(
        ApprovalAssignment.instance_id == ot_req.workflow_instance_id,
        ApprovalAssignment.assigned_employee_id == "emp-mgr",
        ApprovalAssignment.is_completed == False,
    ).one()
    OvertimeService.process_approval(db_session, assign1.id, "emp-mgr", "APPROVE")

    # 人事核備
    assign2 = db_session.query(ApprovalAssignment).filter(
        ApprovalAssignment.instance_id == ot_req.workflow_instance_id,
        ApprovalAssignment.assigned_employee_id == "emp-hr",
        ApprovalAssignment.is_completed == False,
    ).one()
    OvertimeService.process_approval(db_session, assign2.id, "emp-hr", "APPROVE")

    db_session.refresh(ot_req)
    assert ot_req.status == "APPROVED"

    # 驗證沒有產生任何 leave_ledger 分錄
    ledger_count = db_session.query(LeaveLedger).filter(LeaveLedger.employee_id == "emp-app").count()
    assert ledger_count == 0


def test_overtime_overlap_protection(db_session: Session):
    """
    測試 4：時段重疊加班申請拒絕防護
    """
    setup_overtime_test_environment(db_session)

    start_utc = datetime(2026, 10, 23, 10, 30, tzinfo=timezone.utc)
    end_utc = datetime(2026, 10, 23, 14, 30, tzinfo=timezone.utc)

    ot_req = OvertimeService.create_overtime_request(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        start_time_utc=start_utc,
        end_time_utc=end_utc,
        reason="正常加班",
    )
    OvertimeService.submit_overtime_request(db_session, ot_req.id, "emp-app", hr_window_employee_id="emp-hr")

    # 嘗試申請交疊時段
    with pytest.raises(AppException) as exc_info:
        OvertimeService.create_leave_request = None  # 確保呼叫 overtime
        OvertimeService.create_overtime_request(
            db=db_session,
            company_id="comp-tw",
            employee_id="emp-app",
            start_time_utc=datetime(2026, 10, 23, 11, 0, tzinfo=timezone.utc),
            end_time_utc=datetime(2026, 10, 23, 13, 0, tzinfo=timezone.utc),
            reason="時段衝突加班",
        )
    assert exc_info.value.code == "OVERTIME_REQUEST_OVERLAP"


def test_overtime_http_api_flow(client, db_session: Session):
    """
    測試 5：加班 HTTP RESTful API 端到端整合
    - POST /api/v1/overtime/calculate (試算)
    - POST /api/v1/overtime/requests (草稿)
    - POST /api/v1/overtime/requests/{id}/submit (送審)
    - GET /api/v1/overtime/requests/{id} (詳情與簽核快照查詢)
    """
    setup_overtime_test_environment(db_session)

    # 1. 試算
    calc_res = client.post(
        "/api/v1/overtime/calculate",
        json={
            "employee_id": "emp-app",
            "start_time": "2026-10-23T10:30:00Z",
            "end_time": "2026-10-23T14:30:00Z",
            "rest_minutes": 30,
            "compensation_type": "COMPENSATORY_LEAVE",
        },
    )
    assert calc_res.status_code == 200
    calc_data = calc_res.json()["calculation"]
    assert calc_data["net_minutes"] == 210

    # 建立登入使用者
    from app.core.security import hash_password
    user = User(
        id="usr-app",
        username="emp_app",
        email="applicant@etronjf8.com",
        hashed_password=hash_password("Pass123!"),
        display_name="小明",
        employee_id="emp-app",
        primary_company_id="comp-tw",
        is_first_login=False,
    )
    db_session.add(user)
    db_session.commit()

    login_res = client.post("/api/v1/auth/login", json={"username": "emp_app", "password": "Pass123!"})
    assert login_res.status_code == 200
    csrf_token = login_res.json()["csrf_token"]

    # 2. 建立草稿
    create_res = client.post(
        "/api/v1/overtime/requests",
        json={
            "company_id": "comp-tw",
            "employee_id": "emp-app",
            "start_time": "2026-10-23T10:30:00Z",
            "end_time": "2026-10-23T14:30:00Z",
            "reason": "重大系統上線支援",
            "rest_minutes": 30,
            "compensation_type": "COMPENSATORY_LEAVE",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert create_res.status_code == 201
    ot_data = create_res.json()
    req_id = ot_data["request_id"]
    assert ot_data["total_minutes"] == 210
    assert ot_data["comp_leave_minutes"] == 210

    # 3. 送審
    submit_res = client.post(
        f"/api/v1/overtime/requests/{req_id}/submit",
        json={"hr_window_employee_id": "emp-hr"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert submit_res.status_code == 200
    assert submit_res.json()["overtime_status"] == "IN_REVIEW"

    # 4. 詳情查詢
    get_res = client.get(f"/api/v1/overtime/requests/{req_id}")
    assert get_res.status_code == 200
    detail = get_res.json()
    assert detail["id"] == req_id
    assert detail["total_minutes"] == 210
    assert detail["status"] == "IN_REVIEW"
    assert detail["workflow_instance"]["status"] == "IN_REVIEW"
