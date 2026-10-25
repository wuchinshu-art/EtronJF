import pytest
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.main import app
from app.core.time import TIMEZONE_TAIPEI
from app.core.security import hash_password
from app.core.errors import AppException
from app.models.auth import User, Role, UserRole, UserScope
from app.models.hr import (
    Company,
    Organization,
    Employee,
    ManagerRelation,
    Shift,
    CalendarDay,
)
from app.models.travel import TravelRequest, TravelSettlement, TravelExpenseItem
from app.models.workflow import WorkflowInstance, ApprovalAssignment
from app.core.travel_service import TravelService


def setup_travel_test_environment(db: Session):
    """建立出差與結報垂直切片測試所需完整環境 (公司、組織、主管鏈、員工與帳號)"""
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
    org = Organization(id="org-sales", company_id="comp-tw", code="SALES", name="業務部")
    db.add_all([shift, org])
    db.commit()

    # 2. 員工清單：申請人、代理人、直屬主管、會計窗口、人事窗口
    emp_app = Employee(
        id="emp-app",
        company_id="comp-tw",
        organization_id="org-sales",
        employee_no="TW010",
        full_name="申請人小明",
        email="applicant@etronjf8.com",
        hire_date=date(2025, 1, 1),
        status="ACTIVE",
    )
    emp_agent = Employee(
        id="emp-agent",
        company_id="comp-tw",
        organization_id="org-sales",
        employee_no="TW011",
        full_name="代理人小華",
        email="agent@etronjf8.com",
        hire_date=date(2025, 1, 1),
        status="ACTIVE",
    )
    emp_mgr = Employee(
        id="emp-mgr",
        company_id="comp-tw",
        organization_id="org-sales",
        employee_no="TW001",
        full_name="主管大明",
        email="manager@etronjf8.com",
        hire_date=date(2024, 1, 1),
        status="ACTIVE",
    )
    emp_fin = Employee(
        id="emp-fin",
        company_id="comp-tw",
        organization_id="org-sales",
        employee_no="TW008",
        full_name="會計小芬",
        email="finance@etronjf8.com",
        hire_date=date(2024, 1, 1),
        status="ACTIVE",
    )
    emp_hr = Employee(
        id="emp-hr",
        company_id="comp-tw",
        organization_id="org-sales",
        employee_no="TW009",
        full_name="人事小美",
        email="hr@etronjf8.com",
        hire_date=date(2024, 1, 1),
        status="ACTIVE",
    )
    db.add_all([emp_app, emp_agent, emp_mgr, emp_fin, emp_hr])
    db.commit()

    # 3. 直屬主管鏈關聯 (emp-app -> emp-mgr)
    rel = ManagerRelation(
        id="rel-app-mgr",
        employee_id="emp-app",
        manager_id="emp-mgr",
        relation_type="DIRECT",
        effective_from=date(2025, 1, 1),
    )
    db.add(rel)
    db.commit()

    # 4. User 帳號
    user_app = User(
        id="user-app",
        username="emp_app",
        email="applicant@etronjf8.com",
        hashed_password=hash_password("Pass123!"),
        display_name="申請人小明",
        employee_id="emp-app",
        primary_company_id="comp-tw",
        is_active=True,
        is_first_login=False,
    )
    user_mgr = User(
        id="user-mgr",
        username="emp_mgr",
        email="manager@etronjf8.com",
        hashed_password=hash_password("Pass123!"),
        display_name="主管大明",
        employee_id="emp-mgr",
        primary_company_id="comp-tw",
        is_active=True,
        is_first_login=False,
    )
    user_fin = User(
        id="user-fin",
        username="emp_fin",
        email="finance@etronjf8.com",
        hashed_password=hash_password("Pass123!"),
        display_name="會計小芬",
        employee_id="emp-fin",
        primary_company_id="comp-tw",
        is_active=True,
        is_first_login=False,
    )
    db.add_all([user_app, user_mgr, user_fin])
    db.commit()


def test_travel_pipeline_without_advance(db_session: Session):
    """
    測試情境 1：無預支款出差單簽核管線 (has_advance=False)
    期望管線：工作代理人審核 -> 直屬主管審核 -> 人事窗口核備 (自動排除會計窗口)
    """
    setup_travel_test_environment(db_session)

    # 1. 建立出差單 (無預支款)
    travel_req = TravelService.create_travel_request(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        title="台南客戶拜訪",
        destination="台南科學園區",
        purpose="拜訪半導體客戶進行年度技術交流",
        transport_mode="HIGH_SPEED_RAIL",
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 4),
        estimated_days=Decimal("3.0"),
        deputy_employee_id="emp-agent",
        has_advance=False,
        advance_currency="TWD",
        advance_amount=Decimal("0.0000"),
    )
    assert travel_req.id is not None
    assert travel_req.status == "DRAFT"
    assert travel_req.settlement_status == "UNSETTLED"
    assert travel_req.request_number.startswith("TR-")

    # 2. 申請人送審出差單
    submitted_req = TravelService.submit_travel_request(
        db=db_session,
        request_id=travel_req.id,
        operator_employee_id="emp-app",
        finance_window_employee_id="emp-fin",
        hr_window_employee_id="emp-hr",
    )
    assert submitted_req.status == "IN_REVIEW"
    assert submitted_req.workflow_instance_id is not None

    # 檢查簽核快照中解析出之管線節點：應該只有 3 個節點（代理人 -> 直屬主管 -> 人事窗口）
    wf_inst = db_session.get(WorkflowInstance, submitted_req.workflow_instance_id)
    assert wf_inst is not None
    pipeline_names = [n["name"] for n in wf_inst.snapshot_data["resolved_pipeline"]]
    assert pipeline_names == ["工作代理人審核", "直屬主管審核", "人事窗口核備"]

    # 3. 第一關：代理人小華核准
    assign1 = (
        db_session.query(ApprovalAssignment)
        .filter(
            ApprovalAssignment.instance_id == submitted_req.workflow_instance_id,
            ApprovalAssignment.assigned_employee_id == "emp-agent",
            ApprovalAssignment.is_completed == False,
        )
        .one()
    )
    TravelService.process_travel_approval(
        db=db_session,
        assignment_id=assign1.id,
        operator_employee_id="emp-agent",
        action="APPROVE",
        comments="代理工作已確認交接",
    )
    db_session.refresh(submitted_req)
    assert submitted_req.status == "IN_REVIEW"

    # 4. 第二關：主管大明核准
    assign2 = (
        db_session.query(ApprovalAssignment)
        .filter(
            ApprovalAssignment.instance_id == submitted_req.workflow_instance_id,
            ApprovalAssignment.assigned_employee_id == "emp-mgr",
            ApprovalAssignment.is_completed == False,
        )
        .one()
    )
    TravelService.process_travel_approval(
        db=db_session,
        assignment_id=assign2.id,
        operator_employee_id="emp-mgr",
        action="APPROVE",
        comments="准予出差",
    )
    db_session.refresh(submitted_req)
    assert submitted_req.status == "IN_REVIEW"

    # 5. 第三關：人事窗口小美核備完簽
    assign3 = (
        db_session.query(ApprovalAssignment)
        .filter(
            ApprovalAssignment.instance_id == submitted_req.workflow_instance_id,
            ApprovalAssignment.assigned_employee_id == "emp-hr",
            ApprovalAssignment.is_completed == False,
        )
        .one()
    )
    TravelService.process_travel_approval(
        db=db_session,
        assignment_id=assign3.id,
        operator_employee_id="emp-hr",
        action="APPROVE",
        comments="人事備查完畢",
    )
    db_session.refresh(submitted_req)
    assert submitted_req.status == "APPROVED"
    assert submitted_req.settlement_status == "UNSETTLED"


def test_travel_pipeline_with_advance(db_session: Session):
    """
    測試情境 2：有預支款出差單簽核管線 (has_advance=True)
    期望管線：工作代理人審核 -> 直屬主管審核 -> 會計窗口審核 (有預支款) -> 人事窗口核備
    """
    setup_travel_test_environment(db_session)

    # 1. 建立有預支款出差單
    travel_req = TravelService.create_travel_request(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        title="東京半導體展覽",
        destination="日本東京",
        purpose="參加國際半導體設備展覽會",
        transport_mode="AIRPLANE",
        start_date=date(2026, 11, 10),
        end_date=date(2026, 11, 14),
        estimated_days=Decimal("5.0"),
        deputy_employee_id="emp-agent",
        has_advance=True,
        advance_currency="TWD",
        advance_amount=Decimal("30000.0000"),
    )
    assert travel_req.has_advance is True
    assert travel_req.advance_amount == Decimal("30000.0000")

    # 2. 送審
    submitted_req = TravelService.submit_travel_request(
        db=db_session,
        request_id=travel_req.id,
        operator_employee_id="emp-app",
        finance_window_employee_id="emp-fin",
        hr_window_employee_id="emp-hr",
    )

    # 檢查節點受派：應該有 4 個節點（包含會計窗口）
    wf_inst = db_session.get(WorkflowInstance, submitted_req.workflow_instance_id)
    pipeline_names = [n["name"] for n in wf_inst.snapshot_data["resolved_pipeline"]]
    assert pipeline_names == ["工作代理人審核", "直屬主管審核", "會計窗口審核 (有預支款)", "人事窗口核備"]

    # 依序簽核完畢：代理人 -> 主管 -> 會計 -> 人事
    approvers = ["emp-agent", "emp-mgr", "emp-fin", "emp-hr"]
    for approver_id in approvers:
        assign = (
            db_session.query(ApprovalAssignment)
            .filter(
                ApprovalAssignment.instance_id == submitted_req.workflow_instance_id,
                ApprovalAssignment.assigned_employee_id == approver_id,
                ApprovalAssignment.is_completed == False,
            )
            .one()
        )
        TravelService.process_travel_approval(
            db=db_session,
            assignment_id=assign.id,
            operator_employee_id=approver_id,
            action="APPROVE",
            comments="審核通過",
        )

    db_session.refresh(submitted_req)
    assert submitted_req.status == "APPROVED"
    assert submitted_req.settlement_status == "UNSETTLED"


def test_travel_settlement_multicurrency_and_advance_offset(db_session: Session):
    """
    測試情境 3：出差結報多幣別匯率折算、預支款沖銷與應補發/退繳金額核算
    """
    setup_travel_test_environment(db_session)

    # 1. 建立並完簽有預支款出差單 (預支 TWD 20,000)
    travel_req = TravelService.create_travel_request(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        title="原廠技術洽談",
        destination="日本東京",
        purpose="拜訪原廠技術洽談",
        transport_mode="AIRPLANE",
        start_date=date(2026, 11, 10),
        end_date=date(2026, 11, 12),
        estimated_days=Decimal("3.0"),
        deputy_employee_id="emp-agent",
        has_advance=True,
        advance_currency="TWD",
        advance_amount=Decimal("20000.0000"),
    )
    TravelService.submit_travel_request(
        db=db_session,
        request_id=travel_req.id,
        operator_employee_id="emp-app",
        finance_window_employee_id="emp-fin",
        hr_window_employee_id="emp-hr",
    )
    # 快速將出差單直接置為 APPROVED
    travel_req.status = "APPROVED"
    travel_req.settlement_status = "UNSETTLED"
    db_session.commit()

    # 2. 開立多幣別結報單 (包含 JPY、USD、TWD)
    # 項目 1: 住宿費 JPY 50,000，匯率 0.2100 -> TWD 10,500.0000
    # 項目 2: 參展門票 USD 300，匯率 32.5000 -> TWD 9,750.0000
    # 項目 3: 當地交通 TWD 2,000，匯率 1.0000 -> TWD 2,000.0000
    # 實際總支出折合 TWD = 10,500 + 9,750 + 2,000 = 22,250.0000
    # 預支沖銷 = 20,000.0000
    # 應補發給員工 net_payable_amount = 22,250 - 20,000 = +2,250.0000
    items = [
        {
            "expense_category": "HOTEL",
            "expense_date": date(2026, 11, 10),
            "currency": "JPY",
            "exchange_rate": Decimal("0.2100"),
            "amount": Decimal("50000.0000"),
            "invoice_number": "INV-JP-001",
            "description": "東京池袋飯店兩晚住宿",
        },
        {
            "expense_category": "OTHER",
            "expense_date": date(2026, 11, 11),
            "currency": "USD",
            "exchange_rate": Decimal("32.5000"),
            "amount": Decimal("300.0000"),
            "invoice_number": "INV-US-002",
            "description": "國際技術年會註冊費",
        },
        {
            "expense_category": "TRANSPORT",
            "expense_date": date(2026, 11, 12),
            "currency": "TWD",
            "exchange_rate": Decimal("1.0000"),
            "amount": Decimal("2000.0000"),
            "invoice_number": "INV-TW-003",
            "description": "機場往返接送計程車資",
        },
    ]

    settlement = TravelService.create_travel_settlement(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        travel_request_id=travel_req.id,
        currency="TWD",
        exchange_rate=Decimal("1.0000"),
        items_data=items,
        notes="日本技術研討出差結報",
    )

    assert settlement.settlement_number.startswith("TS-")
    assert settlement.total_actual_twd == Decimal("22250.0000")
    assert settlement.advance_offset_amount == Decimal("20000.0000")
    assert settlement.net_payable_amount == Decimal("2250.0000")
    assert settlement.status == "DRAFT"
    assert settlement.payment_status == "UNPAID"

    # 檢查關聯出差單狀態轉為 SETTLING
    db_session.refresh(travel_req)
    assert travel_req.settlement_status == "SETTLING"

    # 檢查明細單項目
    exp_items = db_session.query(TravelExpenseItem).filter(TravelExpenseItem.settlement_id == settlement.id).all()
    assert len(exp_items) == 3


def test_travel_anti_duplicate_settlement(db_session: Session):
    """
    測試情境 4：出差結報防呆與防重複報支
    - 未完簽之出差單禁止結報
    - 已在結報中 (SETTLING) 之出差單禁止再次開立結報
    """
    setup_travel_test_environment(db_session)

    # 1. 建立未完簽出差單 (DRAFT)
    travel_req = TravelService.create_travel_request(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        title="新竹拜訪",
        destination="新竹科學園區",
        purpose="拜訪客戶",
        transport_mode="CAR",
        start_date=date(2026, 11, 5),
        end_date=date(2026, 11, 5),
        estimated_days=Decimal("1.0"),
    )

    # 嘗試對 DRAFT 出差單結報 -> 預期失敗
    with pytest.raises(AppException) as exc_info:
        TravelService.create_travel_settlement(
            db=db_session,
            company_id="comp-tw",
            employee_id="emp-app",
            travel_request_id=travel_req.id,
            currency="TWD",
            exchange_rate=Decimal("1.0"),
            items_data=[{"expense_category": "MEAL", "expense_date": date(2026, 11, 5), "amount": Decimal("500")}],
        )
    assert exc_info.value.code == "TRAVEL_NOT_APPROVED_FOR_SETTLEMENT"

    # 2. 將出差單設為 APPROVED
    travel_req.status = "APPROVED"
    db_session.commit()

    # 成功建立第一筆結報單
    settlement = TravelService.create_travel_settlement(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        travel_request_id=travel_req.id,
        currency="TWD",
        exchange_rate=Decimal("1.0"),
        items_data=[{"expense_category": "MEAL", "expense_date": date(2026, 11, 5), "amount": Decimal("500")}],
    )
    assert settlement.id is not None

    # 嘗試對正在結報中的出差單重複建立結報單 -> 預期失敗
    with pytest.raises(AppException) as exc_info2:
        TravelService.create_travel_settlement(
            db=db_session,
            company_id="comp-tw",
            employee_id="emp-app",
            travel_request_id=travel_req.id,
            currency="TWD",
            exchange_rate=Decimal("1.0"),
            items_data=[{"expense_category": "MEAL", "expense_date": date(2026, 11, 5), "amount": Decimal("300")}],
        )
    assert exc_info2.value.code == "TRAVEL_ALREADY_SETTLED_OR_SETTLING"


def test_travel_settlement_approval_and_payment_confirmation(db_session: Session):
    """
    測試情境 5：出差結報簽核管線與會計付款結清確認
    管線：直屬主管審核 -> 會計窗口審核
    核准後狀態為 APPROVED，等待會計付款
    會計確認付款後 payment_status 轉為 PAID
    """
    setup_travel_test_environment(db_session)

    # 1. 建立完簽出差單
    travel_req = TravelService.create_travel_request(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        title="高雄研討會",
        destination="高雄軟體園區",
        purpose="研討會出差",
        transport_mode="HIGH_SPEED_RAIL",
        start_date=date(2026, 11, 20),
        end_date=date(2026, 11, 20),
        estimated_days=Decimal("1.0"),
    )
    travel_req.status = "APPROVED"
    db_session.commit()

    # 2. 開立結報單 (實報實銷，無預支)
    settlement = TravelService.create_travel_settlement(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        travel_request_id=travel_req.id,
        currency="TWD",
        exchange_rate=Decimal("1.0"),
        items_data=[
            {
                "expense_category": "TRANSPORT",
                "expense_date": date(2026, 11, 20),
                "currency": "TWD",
                "exchange_rate": Decimal("1.0"),
                "amount": Decimal("2980.0000"),
                "description": "台北高雄高鐵來回車票",
            }
        ],
    )

    # 3. 送審結報單
    submitted_set = TravelService.submit_travel_settlement(
        db=db_session,
        settlement_id=settlement.id,
        operator_employee_id="emp-app",
        finance_window_employee_id="emp-fin",
    )
    assert submitted_set.status == "IN_REVIEW"

    # 檢查管線快照：應該有 2 個節點（直屬主管審核 -> 會計窗口審核）
    wf_inst = db_session.get(WorkflowInstance, submitted_set.workflow_instance_id)
    pipeline_names = [n["name"] for n in wf_inst.snapshot_data["resolved_pipeline"]]
    assert pipeline_names == ["直屬主管審核", "會計窗口審核"]

    # 4. 主管核准
    assign1 = (
        db_session.query(ApprovalAssignment)
        .filter(
            ApprovalAssignment.instance_id == submitted_set.workflow_instance_id,
            ApprovalAssignment.assigned_employee_id == "emp-mgr",
            ApprovalAssignment.is_completed == False,
        )
        .one()
    )
    TravelService.process_settlement_approval(
        db=db_session,
        assignment_id=assign1.id,
        operator_employee_id="emp-mgr",
        action="APPROVE",
        comments="車票單據核對無誤",
    )

    # 5. 會計核准完簽
    assign2 = (
        db_session.query(ApprovalAssignment)
        .filter(
            ApprovalAssignment.instance_id == submitted_set.workflow_instance_id,
            ApprovalAssignment.assigned_employee_id == "emp-fin",
            ApprovalAssignment.is_completed == False,
        )
        .one()
    )
    TravelService.process_settlement_approval(
        db=db_session,
        assignment_id=assign2.id,
        operator_employee_id="emp-fin",
        action="APPROVE",
        comments="財務審核無誤，准予結報入帳",
    )

    db_session.refresh(submitted_set)
    db_session.refresh(travel_req)
    assert submitted_set.status == "APPROVED"
    assert submitted_set.payment_status == "UNPAID"
    assert travel_req.settlement_status == "SETTLED"

    # 6. 會計人員執行付款結清確認 (confirm_payment)
    paid_set = TravelService.confirm_payment(
        db=db_session,
        settlement_id=submitted_set.id,
        operator_employee_id="emp-fin",
        paid_reference="WIRE-20261121-001",
    )
    assert paid_set.payment_status == "PAID"
    assert paid_set.paid_at is not None
    assert paid_set.paid_reference == "WIRE-20261121-001"

    # 7. 防呆：已付款者不可重複確認
    with pytest.raises(AppException) as exc_repeat:
        TravelService.confirm_payment(
            db=db_session,
            settlement_id=submitted_set.id,
            operator_employee_id="emp-fin",
            paid_reference="WIRE-REPEAT",
        )
    assert exc_repeat.value.code == "ALREADY_PAID"


def test_travel_http_api_flow(client: TestClient, db_session: Session):
    """
    測試情境 6：FastAPI HTTP API 端到端路由整合測試
    - 登入認證取得 CSRF Token 與 Session
    - POST /api/v1/travel/requests (建立出差單)
    - GET /api/v1/travel/requests (查詢出差單列表)
    - POST /api/v1/travel/requests/{id}/submit (送審出差單)
    - GET /api/v1/travel/requests/{id} (查詢出差單詳情)
    """
    setup_travel_test_environment(db_session)

    # 1. 登入取得 Session 與 CSRF Token
    login_res = client.post("/api/v1/auth/login", json={"username": "emp_app", "password": "Pass123!"})
    assert login_res.status_code == 200, login_res.text
    csrf_token = login_res.json()["csrf_token"]
    auth_headers = {"X-CSRF-Token": csrf_token}

    # 2. 建立出差單 API
    payload = {
        "company_id": "comp-tw",
        "employee_id": "emp-app",
        "title": "新竹客戶拜訪",
        "destination": "新竹科學園區",
        "purpose": "專案需求訪談",
        "transport_mode": "HIGH_SPEED_RAIL",
        "start_date": "2026-11-15",
        "end_date": "2026-11-15",
        "estimated_days": 1.0,
        "deputy_employee_id": "emp-agent",
        "has_advance": False,
        "advance_currency": "TWD",
        "advance_amount": 0.0,
    }
    resp = client.post("/api/v1/travel/requests", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    req_id = data["request_id"]
    assert data["status"] == "success"
    assert data["travel_status"] == "DRAFT"

    # 3. 查詢出差單列表
    resp_list = client.get("/api/v1/travel/requests?employee_id=emp-app", headers=auth_headers)
    assert resp_list.status_code == 200
    list_data = resp_list.json()
    assert len(list_data) >= 1
    assert any(r["id"] == req_id for r in list_data)

    # 4. 送審出差單 API
    submit_payload = {
        "finance_window_employee_id": "emp-fin",
        "hr_window_employee_id": "emp-hr",
    }
    resp_submit = client.post(
        f"/api/v1/travel/requests/{req_id}/submit",
        json=submit_payload,
        headers=auth_headers,
    )
    assert resp_submit.status_code == 200, resp_submit.text
    submit_data = resp_submit.json()
    assert submit_data["travel_status"] == "IN_REVIEW"

    # 5. 查詢出差單詳情 API
    resp_detail = client.get(f"/api/v1/travel/requests/{req_id}", headers=auth_headers)
    assert resp_detail.status_code == 200
    detail_data = resp_detail.json()
    assert detail_data["id"] == req_id
    assert detail_data["status"] == "IN_REVIEW"
    assert detail_data["workflow_instance"]["status"] == "IN_REVIEW"


def test_travel_request_fallback_employee(db_session: Session, client: TestClient):
    """驗證當 employee_id 為 EMP-DEFAULT 或未設定時，出差申請單可自動 fallback 至公司在職員工成功開單"""
    setup_travel_test_environment(db_session)
    login_res = client.post("/api/v1/auth/login", json={"username": "emp_app", "password": "Pass123!"})
    assert login_res.status_code == 200, login_res.text
    csrf_token = login_res.json()["csrf_token"]
    auth_headers = {"X-CSRF-Token": csrf_token}

    payload = {
        "company_id": "comp-tw",
        "employee_id": "EMP-DEFAULT",
        "title": "台北至福岡業務出差考察",
        "destination": "日本福岡 (Fukuoka, Japan)",
        "purpose": "台日營運資訊對接與客戶專案審查",
        "transport_mode": "AIRPLANE",
        "start_date": "2026-10-23",
        "end_date": "2026-10-23",
        "estimated_days": 1.0,
        "has_advance": True,
        "advance_currency": "JPY",
        "advance_amount": 50000.0,
    }
    resp = client.post("/api/v1/travel/requests", json=payload, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "success"
    assert data["request_id"] is not None
    assert data["travel_status"] == "DRAFT"


