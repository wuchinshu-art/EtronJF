import pytest
from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session

from app.core.time import TIMEZONE_TAIPEI
from app.core.errors import AppException
from app.models.auth import User, Role, UserRole, Session as UserSession
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
from app.models.leave import LeaveRequest
from app.models.workflow import WorkflowInstance, ApprovalAssignment
from app.core.leave_calculator import calculate_leave_minutes_and_days, check_leave_overlap
from app.core.leave_service import LeaveService
from app.core.hr_rules import LeaveLedgerService


def setup_leave_test_environment(db: Session):
    """建立請假垂直切片測試所需完整環境 (公司、組織、主管鏈、班別、假別、日曆)"""
    # 1. 公司與班別
    company = Company(
        id="comp-tw",
        name="台灣總部",
        default_timezone="Asia/Taipei",
        default_currency="TWD",
    )
    db.add(company)
    db.commit()

    # 標準常日班：09:00 ~ 18:00，午休 12:00 ~ 13:00 (60分鐘)，標準工時 480 分鐘
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
    # 假別：特別休假 (特休)
    leave_type = LeaveType(
        id="lt-annual",
        company_id="comp-tw",
        code="ANNUAL",
        name="特別休假",
        unit="DAY",
        requires_attachment=False,
    )
    # 組織
    org = Organization(id="org-it", company_id="comp-tw", code="IT", name="資訊部")
    db.add_all([shift, leave_type, org])
    db.commit()

    # 2. 員工
    emp_agent = Employee(
        id="emp-agent",
        company_id="comp-tw",
        organization_id="org-it",
        employee_no="TW001",
        full_name="代理人小王",
        email="agent@etronjf8.com",
        hire_date=date(2025, 1, 1),
    )
    emp_app = Employee(
        id="emp-app",
        company_id="comp-tw",
        organization_id="org-it",
        employee_no="TW002",
        full_name="申請人小明",
        email="applicant@etronjf8.com",
        hire_date=date(2025, 1, 1),
    )
    emp_l1 = Employee(
        id="emp-l1",
        company_id="comp-tw",
        organization_id="org-it",
        employee_no="TW003",
        full_name="一級主管大李",
        email="l1@etronjf8.com",
        hire_date=date(2024, 1, 1),
    )
    emp_l2 = Employee(
        id="emp-l2",
        company_id="comp-tw",
        organization_id="org-it",
        employee_no="TW004",
        full_name="二級主管張理",
        email="l2@etronjf8.com",
        hire_date=date(2023, 1, 1),
    )
    emp_l3 = Employee(
        id="emp-l3",
        company_id="comp-tw",
        organization_id="org-it",
        employee_no="TW005",
        full_name="三級主管處長",
        email="l3@etronjf8.com",
        hire_date=date(2022, 1, 1),
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
    db.add_all([emp_agent, emp_app, emp_l1, emp_l2, emp_l3, emp_hr])
    db.commit()

    # 主管鏈關係 (直屬主管)
    rel1 = ManagerRelation(
        employee_id="emp-app",
        manager_id="emp-l1",
        relation_type="DIRECT",
        effective_from=date(2025, 1, 1),
    )
    rel2 = ManagerRelation(
        employee_id="emp-l1",
        manager_id="emp-l2",
        relation_type="DIRECT",
        effective_from=date(2024, 1, 1),
    )
    rel3 = ManagerRelation(
        employee_id="emp-l2",
        manager_id="emp-l3",
        relation_type="DIRECT",
        effective_from=date(2023, 1, 1),
    )
    db.add_all([rel1, rel2, rel3])
    db.commit()

    # 3. 設定特定工作日曆 (2026-10-23 週五為工作日，2026-10-24 週六為例假日，2026-10-25 週日為休假日，2026-10-26 週一為工作日)
    cal1 = CalendarDay(company_id="comp-tw", calendar_date=date(2026, 10, 23), is_working_day=True, day_type="REGULAR")
    cal2 = CalendarDay(company_id="comp-tw", calendar_date=date(2026, 10, 24), is_working_day=False, day_type="WEEKEND", holiday_name="週六")
    cal3 = CalendarDay(company_id="comp-tw", calendar_date=date(2026, 10, 25), is_working_day=False, day_type="WEEKEND", holiday_name="週日")
    cal4 = CalendarDay(company_id="comp-tw", calendar_date=date(2026, 10, 26), is_working_day=True, day_type="REGULAR")
    db.add_all([cal1, cal2, cal3, cal4])
    db.commit()

    db.commit()


def test_leave_work_minute_and_rest_deduction(db_session: Session):
    """
    測試 1：工時精確折算演算法
    - 排除休息時間 (午休 12:00~13:00)
    - 排除例假日 (週六、週日)
    """
    setup_leave_test_environment(db_session)
    emp = db_session.get(Employee, "emp-app")

    # 情境 A：單日請假 09:00 ~ 18:00 (台北時間) -> 涵蓋 1 小時午休，淨工作 480 分鐘 (1.00 天)
    # 2026-10-23 09:00 台北時間 = 2026-10-23 01:00 UTC
    # 2026-10-23 18:00 台北時間 = 2026-10-23 10:00 UTC
    start_utc = datetime(2026, 10, 23, 1, 0, tzinfo=timezone.utc)
    end_utc = datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc)

    mins, days = calculate_leave_minutes_and_days(db_session, emp, start_utc, end_utc)
    assert mins == 480
    assert days == Decimal("1.00")

    # 情境 B：單日上午半天 09:00 ~ 13:00 (台北時間) -> 涵蓋 12:00~13:00 午休 60 分鐘，淨工時 180 分鐘
    start_half = datetime(2026, 10, 23, 1, 0, tzinfo=timezone.utc)
    end_half = datetime(2026, 10, 23, 5, 0, tzinfo=timezone.utc)
    mins_half, days_half = calculate_leave_minutes_and_days(db_session, emp, start_half, end_half)
    assert mins_half == 180
    assert days_half == Decimal("0.38")

    # 情境 C：跨越週末 (週五 09:00 台北時間 ~ 週一 18:00 台北時間)
    # 週五 480 分鐘 + 週六 0 + 週日 0 + 週一 480 分鐘 = 960 分鐘 (2.00 天)
    end_mon_utc = datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc)
    mins_cross, days_cross = calculate_leave_minutes_and_days(db_session, emp, start_utc, end_mon_utc)
    assert mins_cross == 960
    assert days_cross == Decimal("2.00")


def test_leave_threshold_boundaries_3_and_10_days(db_session: Session):
    """
    測試 2：3 天與 10 天門檻臨界值管線測試 (前一工作分鐘、等值臨界)
    依規約檢驗：
    - 代理人 -> 直屬主管 -> 二級主管 (>=3天) -> 三級主管 (>=10天) -> 人事窗口
    - < 3天：代理人 -> 直屬主管 -> 人事窗口
    - >= 3天 但 < 10天：代理人 -> 直屬主管 -> 二級主管 -> 人事窗口
    - >= 10天：代理人 -> 直屬主管 -> 二級主管 -> 三級主管 -> 人事窗口
    """
    setup_leave_test_environment(db_session)
    LeaveLedgerService.grant_leave(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        leave_type_id="lt-annual",
        amount_minutes=20000,
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
        created_by="admin",
        notes="測試額度",
    )

    # 1. 測試小於 3 天 (例如 2.5 天 = 1200 分鐘)
    req_sub3 = LeaveRequest(
        company_id="comp-tw",
        employee_id="emp-app",
        leave_type_id="lt-annual",
        request_number="LV-SUB-3D",
        start_time=datetime(2026, 10, 23, 1, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc),
        total_minutes=1200,
        calculated_days=Decimal("2.50"),
        reason="請假小於3天",
        deputy_employee_id="emp-agent",
        status="DRAFT",
    )
    db_session.add(req_sub3)
    db_session.commit()

    LeaveService.submit_leave_request(db_session, req_sub3.id, "emp-app", hr_window_employee_id="emp-hr")
    wf_sub3 = db_session.get(WorkflowInstance, req_sub3.workflow_instance_id)
    pipeline_sub3 = [n["name"] for n in wf_sub3.snapshot_data["resolved_pipeline"]]
    assert pipeline_sub3 == ["工作代理人審核", "直屬主管審核", "人事窗口核備"]

    # 2. 測試剛好 3 天 (3.00 天，達到 >= 3 天門檻)
    req_eq3 = LeaveRequest(
        company_id="comp-tw",
        employee_id="emp-app",
        leave_type_id="lt-annual",
        request_number="LV-EQ-3D",
        start_time=datetime(2026, 11, 1, 1, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 11, 3, 10, 0, tzinfo=timezone.utc),
        total_minutes=1440,
        calculated_days=Decimal("3.00"),
        reason="請假剛好3天",
        deputy_employee_id="emp-agent",
        status="DRAFT",
    )
    db_session.add(req_eq3)
    db_session.commit()

    LeaveService.submit_leave_request(db_session, req_eq3.id, "emp-app", hr_window_employee_id="emp-hr")
    wf_eq3 = db_session.get(WorkflowInstance, req_eq3.workflow_instance_id)
    pipeline_eq3 = [n["name"] for n in wf_eq3.snapshot_data["resolved_pipeline"]]
    assert pipeline_eq3 == ["工作代理人審核", "直屬主管審核", "第二層主管審核 (3天以上)", "人事窗口核備"]

    # 3. 測試 10 天臨界值 (10.00 天，達到 >= 10 天門檻)
    req_eq10 = LeaveRequest(
        company_id="comp-tw",
        employee_id="emp-app",
        leave_type_id="lt-annual",
        request_number="LV-EQ-10D",
        start_time=datetime(2026, 12, 1, 1, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 12, 14, 10, 0, tzinfo=timezone.utc),
        total_minutes=4800,
        calculated_days=Decimal("10.00"),
        reason="請假達到10天以上",
        deputy_employee_id="emp-agent",
        status="DRAFT",
    )
    db_session.add(req_eq10)
    db_session.commit()

    LeaveService.submit_leave_request(db_session, req_eq10.id, "emp-app", hr_window_employee_id="emp-hr")
    wf_eq10 = db_session.get(WorkflowInstance, req_eq10.workflow_instance_id)
    pipeline_eq10 = [n["name"] for n in wf_eq10.snapshot_data["resolved_pipeline"]]
    assert pipeline_eq10 == ["工作代理人審核", "直屬主管審核", "第二層主管審核 (3天以上)", "第三層主管審核 (10天以上)", "人事窗口核備"]


def test_leave_ledger_atomic_lifecycle_approve_and_reject(db_session: Session):
    """
    測試 3：假額帳本原子生命週期與簽核完簽扣抵、駁回釋放
    - GRANT 4800 分鐘 (10天)
    - SUBMIT 假單 (1440 分鐘) -> 產生 HOLD 分錄，可用餘額變為 3360
    - 簽核逐步流轉 APPROVE -> 最終節點完簽後產生 COMMIT 分錄，假單狀態變為 APPROVED
    - 另建立一筆假單 SUBMIT -> REJECT 駁回 -> 產生 RELEASE 分錄，可用餘額恢復
    """
    setup_leave_test_environment(db_session)
    LeaveLedgerService.grant_leave(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        leave_type_id="lt-annual",
        amount_minutes=4800,
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
        created_by="admin",
        notes="年度特休發放",
    )

    # 建立 3 天假單 (1440 分鐘)
    req = LeaveService.create_leave_request(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        leave_type_id="lt-annual",
        start_time_utc=datetime(2026, 10, 23, 1, 0, tzinfo=timezone.utc),
        end_time_utc=datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc),
        reason="返鄉探親",
        deputy_employee_id="emp-agent",
    )
    # 人為模擬將工時設為 1440分、3天以利驗證
    req.total_minutes = 1440
    req.calculated_days = Decimal("3.00")
    db_session.commit()

    # 送審
    LeaveService.submit_leave_request(db_session, req.id, "emp-app", hr_window_employee_id="emp-hr")
    assert req.status == "IN_REVIEW"

    # 驗證帳本：HOLD 1440，可用餘額為 4800 - 1440 = 3360
    bal_after_hold = LeaveLedgerService.get_available_balance(db_session, "emp-app", "lt-annual")
    assert bal_after_hold == 3360

    # 節點 1：代理人小王核准
    assign1 = db_session.query(ApprovalAssignment).filter(
        ApprovalAssignment.instance_id == req.workflow_instance_id,
        ApprovalAssignment.assigned_employee_id == "emp-agent",
        ApprovalAssignment.is_completed == False,
    ).one()
    LeaveService.process_approval(db_session, assign1.id, "emp-agent", "APPROVE", comments="同意代理")
    assert req.status == "IN_REVIEW"

    # 節點 2：直屬主管大李核准
    assign2 = db_session.query(ApprovalAssignment).filter(
        ApprovalAssignment.instance_id == req.workflow_instance_id,
        ApprovalAssignment.assigned_employee_id == "emp-l1",
        ApprovalAssignment.is_completed == False,
    ).one()
    LeaveService.process_approval(db_session, assign2.id, "emp-l1", "APPROVE", comments="主管核可")
    assert req.status == "IN_REVIEW"

    # 節點 3：第二層主管張理核准
    assign3 = db_session.query(ApprovalAssignment).filter(
        ApprovalAssignment.instance_id == req.workflow_instance_id,
        ApprovalAssignment.assigned_employee_id == "emp-l2",
        ApprovalAssignment.is_completed == False,
    ).one()
    LeaveService.process_approval(db_session, assign3.id, "emp-l2", "APPROVE", comments="二級主管核准")
    assert req.status == "IN_REVIEW"

    # 節點 4：人事窗口小芳完簽核備 -> 完簽！
    assign4 = db_session.query(ApprovalAssignment).filter(
        ApprovalAssignment.instance_id == req.workflow_instance_id,
        ApprovalAssignment.assigned_employee_id == "emp-hr",
        ApprovalAssignment.is_completed == False,
    ).one()
    LeaveService.process_approval(db_session, assign4.id, "emp-hr", "APPROVE", comments="人事完簽確認")

    # 驗證假單狀態轉為 APPROVED，帳本 COMMIT 正式扣抵
    db_session.refresh(req)
    assert req.status == "APPROVED"
    bal_after_commit = LeaveLedgerService.get_available_balance(db_session, "emp-app", "lt-annual")
    assert bal_after_commit == 3360  # 正式扣抵後可用餘額不變（因送審時已被 HOLD 扣除）

    # 驗證帳本明細中包含 GRANT, HOLD, COMMIT 三筆紀錄
    ledger_entries = db_session.query(LeaveLedger).filter(
        LeaveLedger.employee_id == "emp-app",
        LeaveLedger.leave_type_id == "lt-annual",
    ).all()
    actions = [e.entry_type for e in ledger_entries]
    assert "GRANT" in actions
    assert "HOLD" in actions
    assert "COMMIT" in actions


def test_leave_overdraw_protection_and_overlap_rejection(db_session: Session):
    """
    測試 4：餘額超支防護與假單時段重疊拒絕防護
    """
    setup_leave_test_environment(db_session)
    # 僅發放 480 分鐘 (1天)
    LeaveLedgerService.grant_leave(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        leave_type_id="lt-annual",
        amount_minutes=480,
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
        created_by="admin",
        notes="僅發放一天",
    )

    # 建立 2 天假單 (960 分鐘)
    req_overdraw = LeaveRequest(
        company_id="comp-tw",
        employee_id="emp-app",
        leave_type_id="lt-annual",
        request_number="LV-OVERDRAW",
        start_time=datetime(2026, 10, 23, 1, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 26, 10, 0, tzinfo=timezone.utc),
        total_minutes=960,
        calculated_days=Decimal("2.00"),
        reason="超支請假",
        deputy_employee_id="emp-agent",
        status="DRAFT",
    )
    db_session.add(req_overdraw)
    db_session.commit()

    # 送審時必須拋出餘額不足例外
    with pytest.raises(AppException) as exc_info:
        LeaveService.submit_leave_request(db_session, req_overdraw.id, "emp-app", hr_window_employee_id="emp-hr")
    assert exc_info.value.code == "INSUFFICIENT_LEAVE_BALANCE"

    # 測試重疊防護：先建立並送審一筆正常假單 (480 分鐘)
    req_valid = LeaveRequest(
        company_id="comp-tw",
        employee_id="emp-app",
        leave_type_id="lt-annual",
        request_number="LV-VALID-1",
        start_time=datetime(2026, 10, 23, 1, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 10, 23, 10, 0, tzinfo=timezone.utc),
        total_minutes=480,
        calculated_days=Decimal("1.00"),
        reason="正常請假",
        deputy_employee_id="emp-agent",
        status="DRAFT",
    )
    db_session.add(req_valid)
    db_session.commit()
    LeaveService.submit_leave_request(db_session, req_valid.id, "emp-app", hr_window_employee_id="emp-hr")

    # 嘗試在相同時間區間再次申請
    with pytest.raises(AppException) as exc_overlap:
        LeaveService.create_leave_request(
            db=db_session,
            company_id="comp-tw",
            employee_id="emp-app",
            leave_type_id="lt-annual",
            start_time_utc=datetime(2026, 10, 23, 2, 0, tzinfo=timezone.utc),
            end_time_utc=datetime(2026, 10, 23, 6, 0, tzinfo=timezone.utc),
            reason="時段衝突重複請假",
        )
    assert exc_overlap.value.code == "LEAVE_REQUEST_OVERLAP"


def test_leave_http_api_flow(client, db_session: Session):
    """
    測試 5：HTTP RESTful API 端到端整合測試
    - POST /api/v1/leave/calculate (工時試算)
    - POST /api/v1/leave/requests (建立草稿)
    - POST /api/v1/leave/requests/{id}/submit (送審並啟動簽核)
    - GET /api/v1/leave/requests/{id} (詳情與簽核快照查詢)
    """
    setup_leave_test_environment(db_session)
    LeaveLedgerService.grant_leave(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        leave_type_id="lt-annual",
        amount_minutes=4800,
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
        created_by="admin",
    )

    # 1. 測試工時試算 API (不需要登入)
    calc_res = client.post(
        "/api/v1/leave/calculate",
        json={
            "employee_id": "emp-app",
            "start_time": "2026-10-23T01:00:00Z",
            "end_time": "2026-10-23T10:00:00Z",
        },
    )
    assert calc_res.status_code == 200
    calc_data = calc_res.json()
    assert calc_data["total_minutes"] == 480
    assert calc_data["calculated_days"] == 1.0

    # 建立關聯使用者以取得登入 Session
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

    # 2. 建立請假單草稿
    create_res = client.post(
        "/api/v1/leave/requests",
        json={
            "company_id": "comp-tw",
            "employee_id": "emp-app",
            "leave_type_id": "lt-annual",
            "start_time": "2026-10-23T01:00:00Z",
            "end_time": "2026-10-23T10:00:00Z",
            "reason": "參加研討會",
            "deputy_employee_id": "emp-agent",
        },
        headers={"X-CSRF-Token": csrf_token},
    )
    assert create_res.status_code == 201
    created_leave = create_res.json()
    req_id = created_leave["request_id"]
    assert created_leave["total_minutes"] == 480
    assert created_leave["leave_status"] == "DRAFT"

    # 3. 送審請假單
    submit_res = client.post(
        f"/api/v1/leave/requests/{req_id}/submit",
        json={"hr_window_employee_id": "emp-hr"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert submit_res.status_code == 200
    submit_data = submit_res.json()
    assert submit_data["leave_status"] == "IN_REVIEW"
    assert submit_data["workflow_instance_id"] is not None

    # 4. 查詢請假單詳情
    get_res = client.get(f"/api/v1/leave/requests/{req_id}")
    assert get_res.status_code == 200
    detail = get_res.json()
    assert detail["id"] == req_id
    assert detail["status"] == "IN_REVIEW"
    assert detail["total_minutes"] == 480
    assert detail["workflow_instance"]["status"] == "IN_REVIEW"
