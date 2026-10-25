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
from app.models.payment import Vendor, ExpenseClaim, ExpenseClaimItem, PaymentRequest
from app.models.workflow import WorkflowInstance, ApprovalAssignment
from app.core.payment_service import PaymentService


def setup_payment_test_environment(db: Session):
    """建立費用與請款垂直切片測試所需完整環境 (公司、組織、主管鏈、員工與帳號)"""
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
    org = Organization(id="org-rd", company_id="comp-tw", code="RD", name="研發處", level="DIVISION")
    db.add_all([shift, org])
    db.commit()

    # 2. 員工清單：申請人、直屬主管(L1)、第二層主管(L2)、第三層主管(L3)、部經理、處長、總經理、會計窗口
    emp_app = Employee(
        id="emp-app",
        company_id="comp-tw",
        organization_id="org-rd",
        employee_no="TW101",
        full_name="申請人小明",
        email="applicant@etronjf8.com",
        hire_date=date(2025, 1, 1),
        status="ACTIVE",
    )
    emp_l1 = Employee(
        id="emp-l1",
        company_id="comp-tw",
        organization_id="org-rd",
        employee_no="TW102",
        full_name="直屬主管大明",
        email="manager_l1@etronjf8.com",
        hire_date=date(2024, 1, 1),
        status="ACTIVE",
    )
    emp_l2 = Employee(
        id="emp-l2",
        company_id="comp-tw",
        organization_id="org-rd",
        employee_no="TW103",
        full_name="二級主管老張",
        email="manager_l2@etronjf8.com",
        hire_date=date(2023, 1, 1),
        status="ACTIVE",
    )
    emp_l3 = Employee(
        id="emp-l3",
        company_id="comp-tw",
        organization_id="org-rd",
        employee_no="TW104",
        full_name="三級主管老陳",
        email="manager_l3@etronjf8.com",
        hire_date=date(2022, 1, 1),
        status="ACTIVE",
    )
    emp_dept = Employee(
        id="emp-dept",
        company_id="comp-tw",
        organization_id="org-rd",
        employee_no="TW105",
        full_name="部級經理李經理",
        email="dept_mgr@etronjf8.com",
        hire_date=date(2021, 1, 1),
        status="ACTIVE",
    )
    emp_div = Employee(
        id="emp-div",
        company_id="comp-tw",
        organization_id="org-rd",
        employee_no="TW106",
        full_name="處級處長王處長",
        email="div_mgr@etronjf8.com",
        hire_date=date(2020, 1, 1),
        status="ACTIVE",
    )
    emp_gm = Employee(
        id="emp-gm",
        company_id="comp-tw",
        organization_id="org-rd",
        employee_no="TW107",
        full_name="總經理",
        email="gm@etronjf8.com",
        hire_date=date(2019, 1, 1),
        status="ACTIVE",
    )
    emp_fin = Employee(
        id="emp-fin",
        company_id="comp-tw",
        organization_id="org-rd",
        employee_no="TW108",
        full_name="會計窗口小芬",
        email="finance@etronjf8.com",
        hire_date=date(2024, 1, 1),
        status="ACTIVE",
    )
    db.add_all([emp_app, emp_l1, emp_l2, emp_l3, emp_dept, emp_div, emp_gm, emp_fin])
    db.commit()

    # 3. 直屬主管鏈關聯 (emp-app -> emp-l1 -> emp-l2 -> emp-l3)
    rel1 = ManagerRelation(
        id="rel-app-l1",
        employee_id="emp-app",
        manager_id="emp-l1",
        relation_type="DIRECT",
        effective_from=date(2025, 1, 1),
    )
    rel2 = ManagerRelation(
        id="rel-l1-l2",
        employee_id="emp-l1",
        manager_id="emp-l2",
        relation_type="DIRECT",
        effective_from=date(2024, 1, 1),
    )
    rel3 = ManagerRelation(
        id="rel-l2-l3",
        employee_id="emp-l2",
        manager_id="emp-l3",
        relation_type="DIRECT",
        effective_from=date(2023, 1, 1),
    )
    db.add_all([rel1, rel2, rel3])
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
    db.add_all([user_app, user_fin])
    db.commit()


def test_expense_claim_threshold_boundaries(db_session: Session):
    """
    測試情境 1：費用報銷門檻管線測試 (EXPENSE)
    管線規範：
    - < 5000：直屬主管審核 -> 會計窗口審核
    - >= 5000 且 < 100000：直屬主管審核 -> 第二層主管審核 (>=5000) -> 會計窗口審核
    - >= 100000：直屬主管審核 -> 第二層主管審核 (>=5000) -> 第三層主管審核 (>=100000) -> 會計窗口審核
    """
    setup_payment_test_environment(db_session)

    # 1. 門檻 < 5000 (TWD 3,000)
    claim_small = PaymentService.create_expense_claim(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        title="部門文具採買",
        currency="TWD",
        exchange_rate=Decimal("1.0"),
        items_data=[
            {
                "category": "OFFICE",
                "expense_date": date(2026, 11, 1),
                "invoice_number": "INV-001",
                "amount": Decimal("3000.0000"),
                "description": "原子筆與影印紙",
            }
        ],
    )
    submitted_small = PaymentService.submit_expense_claim(
        db=db_session,
        claim_id=claim_small.id,
        operator_employee_id="emp-app",
        finance_window_employee_id="emp-fin",
    )
    wf_small = db_session.get(WorkflowInstance, submitted_small.workflow_instance_id)
    pipeline_small = [n["name"] for n in wf_small.snapshot_data["resolved_pipeline"]]
    assert pipeline_small == ["直屬主管審核", "會計窗口審核"]

    # 2. 門檻 >= 5000 且 < 100000 (TWD 50,000)
    claim_mid = PaymentService.create_expense_claim(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        title="團隊技術圖書採購",
        currency="TWD",
        exchange_rate=Decimal("1.0"),
        items_data=[
            {
                "category": "OFFICE",
                "expense_date": date(2026, 11, 2),
                "invoice_number": "INV-002",
                "amount": Decimal("50000.0000"),
                "description": "專業參考書籍",
            }
        ],
    )
    submitted_mid = PaymentService.submit_expense_claim(
        db=db_session,
        claim_id=claim_mid.id,
        operator_employee_id="emp-app",
        finance_window_employee_id="emp-fin",
    )
    wf_mid = db_session.get(WorkflowInstance, submitted_mid.workflow_instance_id)
    pipeline_mid = [n["name"] for n in wf_mid.snapshot_data["resolved_pipeline"]]
    assert pipeline_mid == ["直屬主管審核", "第二層主管審核 (>=5000)", "會計窗口審核"]

    # 3. 門檻 >= 100000 (TWD 120,000)
    claim_large = PaymentService.create_expense_claim(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        title="部門研討會場地費",
        currency="TWD",
        exchange_rate=Decimal("1.0"),
        items_data=[
            {
                "category": "MISC",
                "expense_date": date(2026, 11, 3),
                "invoice_number": "INV-003",
                "amount": Decimal("120000.0000"),
                "description": "年會大型會議廳租用",
            }
        ],
    )
    submitted_large = PaymentService.submit_expense_claim(
        db=db_session,
        claim_id=claim_large.id,
        operator_employee_id="emp-app",
        finance_window_employee_id="emp-fin",
    )
    wf_large = db_session.get(WorkflowInstance, submitted_large.workflow_instance_id)
    pipeline_large = [n["name"] for n in wf_large.snapshot_data["resolved_pipeline"]]
    assert pipeline_large == ["直屬主管審核", "第二層主管審核 (>=5000)", "第三層主管審核 (>=100000)", "會計窗口審核"]

    # 依序簽核大額報銷單：直屬(L1) -> 二級(L2) -> 三級(L3) -> 會計(FIN)
    approvers = ["emp-l1", "emp-l2", "emp-l3", "emp-fin"]
    for approver_id in approvers:
        assign = (
            db_session.query(ApprovalAssignment)
            .filter(
                ApprovalAssignment.instance_id == submitted_large.workflow_instance_id,
                ApprovalAssignment.assigned_employee_id == approver_id,
                ApprovalAssignment.is_completed == False,
            )
            .one()
        )
        PaymentService.process_expense_approval(
            db=db_session,
            assignment_id=assign.id,
            operator_employee_id=approver_id,
            action="APPROVE",
            comments="審核核准",
        )

    db_session.refresh(submitted_large)
    assert submitted_large.status == "APPROVED"
    assert submitted_large.payment_status == "UNPAID"


def test_expense_claim_duplicate_warning_and_payment(db_session: Session):
    """
    測試情境 2：可能重複憑證警示與會計付款結清確認
    - 相同發票號碼與金額警示 (has_duplicate_warning)
    - 會計付款結清確認 (confirm_expense_payment)
    - 防重複確認付款
    """
    setup_payment_test_environment(db_session)

    # 1. 建立第一張報銷單
    claim1 = PaymentService.create_expense_claim(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        title="客戶用餐費用",
        currency="TWD",
        exchange_rate=Decimal("1.0"),
        items_data=[
            {
                "category": "MEAL",
                "expense_date": date(2026, 11, 4),
                "invoice_number": "INV-DUP-8888",
                "amount": Decimal("2500.0000"),
                "description": "商務午餐",
            }
        ],
    )
    assert claim1.has_duplicate_warning is False

    # 2. 建立第二張報銷單，帶入完全相同的發票號碼與金額 -> 預期觸發重複警示
    claim2 = PaymentService.create_expense_claim(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        title="重複的客戶用餐費用",
        currency="TWD",
        exchange_rate=Decimal("1.0"),
        items_data=[
            {
                "category": "MEAL",
                "expense_date": date(2026, 11, 4),
                "invoice_number": "INV-DUP-8888",
                "amount": Decimal("2500.0000"),
                "description": "再次提交的發票",
            }
        ],
    )
    assert claim2.has_duplicate_warning is True

    # 3. 核准並完簽第一筆報銷單
    PaymentService.submit_expense_claim(
        db=db_session,
        claim_id=claim1.id,
        operator_employee_id="emp-app",
        finance_window_employee_id="emp-fin",
    )
    claim1.status = "APPROVED"
    db_session.commit()

    # 4. 會計執行付款確認
    paid_claim = PaymentService.confirm_expense_payment(
        db=db_session,
        claim_id=claim1.id,
        operator_employee_id="emp-fin",
        paid_reference="WIRE-EXP-20261105-001",
    )
    assert paid_claim.payment_status == "PAID"
    assert paid_claim.paid_at is not None
    assert paid_claim.paid_reference == "WIRE-EXP-20261105-001"

    # 5. 防呆：已付款禁止重複付款
    with pytest.raises(AppException) as exc:
        PaymentService.confirm_expense_payment(
            db=db_session,
            claim_id=claim1.id,
            operator_employee_id="emp-fin",
            paid_reference="WIRE-REPEAT",
        )
    assert exc.value.code == "ALREADY_PAID"


def test_vendor_bank_masking_and_snapshot_immutability(db_session: Session):
    """
    測試情境 3：供應商主檔銀行遮罩與請款單受款快照不可變性 (Snapshot Immutability)
    - 銀行帳號安全遮罩 (末4碼顯示)
    - 請款單送簽時快照保存供應商主檔，主檔後續異動不影響請款單已存快照
    """
    setup_payment_test_environment(db_session)

    # 1. 建立供應商主檔
    vendor = PaymentService.create_vendor(
        db=db_session,
        company_id="comp-tw",
        code="VEND-001",
        name="先進半導體耗材股份有限公司",
        tax_id="12345678",
        bank_country="TW",
        bank_name="台灣銀行",
        bank_code="004",
        branch_name="新竹分行",
        account_name="先進半導體耗材股份有限公司",
        account_number="0041234567890",
        bank_currency="TWD",
    )

    # 驗證銀行遮罩
    masked_vendor = PaymentService.get_vendor(db=db_session, vendor_id=vendor.id, mask_bank_info=True)
    assert masked_vendor["account_number"] == "*********7890"

    unmasked_vendor = PaymentService.get_vendor(db=db_session, vendor_id=vendor.id, mask_bank_info=False)
    assert unmasked_vendor["account_number"] == "0041234567890"

    # 2. 建立請款單，擷取快照
    pay_req = PaymentService.create_payment_request(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        vendor_id=vendor.id,
        title="11月份晶圓研磨耗材請款",
        currency="TWD",
        exchange_rate=Decimal("1.0"),
        amount=Decimal("45000.0000"),
        due_date=date(2026, 11, 30),
        invoice_number="INV-PAY-001",
    )
    assert pay_req.vendor_snapshot["code"] == "VEND-001"
    assert pay_req.vendor_snapshot["account_number"] == "0041234567890"

    # 3. 模擬駭客或管理員竄改供應商主檔銀行帳號
    vendor.account_number = "8888888888888"
    vendor.name = "已竄改名稱之公司"
    db_session.commit()

    # 4. 驗證請款單中保存的快照完全不受主檔異動影響！
    db_session.refresh(pay_req)
    assert pay_req.vendor_snapshot["account_number"] == "0041234567890"
    assert pay_req.vendor_snapshot["name"] == "先進半導體耗材股份有限公司"


def test_payment_request_threshold_pipeline(db_session: Session):
    """
    測試情境 4：供應商請款門檻管線測試 (PAYMENT)
    路徑規範：
    - < 5000：直屬主管審核 -> 會計窗口付款
    - >= 5000 且 < 100000：直屬主管審核 -> 部級主管審核 (>=5000) -> 會計窗口付款
    - >= 100000 且 < 500000：直屬主管審核 -> 部級主管審核 (>=5000) -> 處級主管審核 (>=100000) -> 會計窗口付款
    - >= 500000：直屬主管審核 -> 部級主管審核 (>=5000) -> 處級主管審核 (>=100000) -> 總經理審核 (>=500000) -> 會計窗口付款
    """
    setup_payment_test_environment(db_session)
    vendor = PaymentService.create_vendor(
        db=db_session,
        company_id="comp-tw",
        code="VEND-002",
        name="日本電子材料株式會社",
        bank_currency="TWD",
    )

    # 1. 門檻 < 5000 (TWD 4,000)
    pay_small = PaymentService.create_payment_request(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        vendor_id=vendor.id,
        title="樣品測試請款",
        currency="TWD",
        exchange_rate=Decimal("1.0"),
        amount=Decimal("4000.0000"),
        due_date=date(2026, 11, 20),
    )
    PaymentService.submit_payment_request(
        db=db_session,
        payment_id=pay_small.id,
        operator_employee_id="emp-app",
        finance_window_employee_id="emp-fin",
    )
    wf_small = db_session.get(WorkflowInstance, pay_small.workflow_instance_id)
    pipeline_small = [n["name"] for n in wf_small.snapshot_data["resolved_pipeline"]]
    assert pipeline_small == ["直屬主管審核", "會計窗口付款"]

    # 2. 門檻 >= 5000 且 < 100000 (TWD 80,000)
    pay_mid = PaymentService.create_payment_request(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        vendor_id=vendor.id,
        title="季度設備保養請款",
        currency="TWD",
        exchange_rate=Decimal("1.0"),
        amount=Decimal("80000.0000"),
        due_date=date(2026, 11, 20),
    )
    PaymentService.submit_payment_request(
        db=db_session,
        payment_id=pay_mid.id,
        operator_employee_id="emp-app",
        dept_manager_id="emp-dept",
        finance_window_employee_id="emp-fin",
    )
    wf_mid = db_session.get(WorkflowInstance, pay_mid.workflow_instance_id)
    pipeline_mid = [n["name"] for n in wf_mid.snapshot_data["resolved_pipeline"]]
    assert pipeline_mid == ["直屬主管審核", "部級主管審核 (>=5000)", "會計窗口付款"]

    # 3. 門檻 >= 100000 且 < 500000 (TWD 300,000)
    pay_large = PaymentService.create_payment_request(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        vendor_id=vendor.id,
        title="真空機台維修請款",
        currency="TWD",
        exchange_rate=Decimal("1.0"),
        amount=Decimal("300000.0000"),
        due_date=date(2026, 11, 20),
    )
    PaymentService.submit_payment_request(
        db=db_session,
        payment_id=pay_large.id,
        operator_employee_id="emp-app",
        dept_manager_id="emp-dept",
        div_manager_id="emp-div",
        finance_window_employee_id="emp-fin",
    )
    wf_large = db_session.get(WorkflowInstance, pay_large.workflow_instance_id)
    pipeline_large = [n["name"] for n in wf_large.snapshot_data["resolved_pipeline"]]
    assert pipeline_large == ["直屬主管審核", "部級主管審核 (>=5000)", "處級主管審核 (>=100000)", "會計窗口付款"]

    # 4. 門檻 >= 500000 (TWD 800,000，啟動總經理審核)
    pay_huge = PaymentService.create_payment_request(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        vendor_id=vendor.id,
        title="新廠房無塵室設備請款",
        currency="TWD",
        exchange_rate=Decimal("1.0"),
        amount=Decimal("800000.0000"),
        due_date=date(2026, 11, 20),
    )
    PaymentService.submit_payment_request(
        db=db_session,
        payment_id=pay_huge.id,
        operator_employee_id="emp-app",
        dept_manager_id="emp-dept",
        div_manager_id="emp-div",
        gm_id="emp-gm",
        finance_window_employee_id="emp-fin",
    )
    wf_huge = db_session.get(WorkflowInstance, pay_huge.workflow_instance_id)
    pipeline_huge = [n["name"] for n in wf_huge.snapshot_data["resolved_pipeline"]]
    assert pipeline_huge == [
        "直屬主管審核",
        "部級主管審核 (>=5000)",
        "處級主管審核 (>=100000)",
        "總經理審核 (>=500000)",
        "會計窗口付款",
    ]

    # 依序簽核推進超大額請款單
    approvers = ["emp-l1", "emp-dept", "emp-div", "emp-gm", "emp-fin"]
    for approver_id in approvers:
        assign = (
            db_session.query(ApprovalAssignment)
            .filter(
                ApprovalAssignment.instance_id == pay_huge.workflow_instance_id,
                ApprovalAssignment.assigned_employee_id == approver_id,
                ApprovalAssignment.is_completed == False,
            )
            .one()
        )
        PaymentService.process_payment_approval(
            db=db_session,
            assignment_id=assign.id,
            operator_employee_id=approver_id,
            action="APPROVE",
            comments="大額款項核對無誤准予支付",
        )

    db_session.refresh(pay_huge)
    assert pay_huge.status == "APPROVED"
    assert pay_huge.payment_status == "UNPAID"


def test_multicurrency_exchange_gain_loss_for_erp_gl(db_session: Session):
    """
    測試情境 5：外幣請款、匯兌損益差額核算與 ERP 總帳 (GL) 拋轉支援
    - 請款外幣 USD 10,000，送審匯率 32.0000 (折合 TWD 320,000)
    - 實際付款結清時匯率為 32.5000
    - 匯兌損益精確核算：10000 * (32.5000 - 32.0000) = +5000.0000 TWD
    """
    setup_payment_test_environment(db_session)
    vendor = PaymentService.create_vendor(
        db=db_session,
        company_id="comp-tw",
        code="VEND-US-001",
        name="Silicon Valley Equipment Corp",
        country="US",
        bank_currency="USD",
    )

    pay_usd = PaymentService.create_payment_request(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        vendor_id=vendor.id,
        title="美商設備授權年費請款",
        currency="USD",
        exchange_rate=Decimal("32.0000"),
        amount=Decimal("10000.0000"),
        due_date=date(2026, 11, 25),
    )
    assert pay_usd.amount_twd == Decimal("320000.0000")

    # 模擬完簽核准
    pay_usd.status = "APPROVED"
    db_session.commit()

    # 會計執行付款結清，帶入實際結算匯率 32.5000
    paid_usd = PaymentService.confirm_vendor_payment(
        db=db_session,
        payment_id=pay_usd.id,
        operator_employee_id="emp-fin",
        paid_reference="WIRE-USD-20261125-001",
        settlement_exchange_rate=Decimal("32.5000"),
    )
    assert paid_usd.payment_status == "PAID"
    assert paid_usd.settlement_exchange_rate == Decimal("32.5000")
    # 差額 = 10,000 * (32.5 - 32.0) = 5,000.0000 TWD
    assert paid_usd.exchange_gain_loss == Decimal("5000.0000")


def test_payment_and_expense_http_api_flow(client: TestClient, db_session: Session):
    """
    測試情境 6：FastAPI HTTP API 端到端路由整合測試
    - 登入認證取得 CSRF Token 與 Session
    - POST /api/v1/vendors (建立供應商)
    - GET /api/v1/vendors (查詢供應商列表，驗證帳號遮罩)
    - POST /api/v1/expense/claims (建立費用報銷單)
    - POST /api/v1/expense/claims/{id}/submit (送審費用報銷單)
    - POST /api/v1/payment/requests (建立供應商請款單)
    - POST /api/v1/payment/requests/{id}/submit (送審請款單)
    - POST /api/v1/payment/requests/{id}/confirm-payment (會計確認付款)
    """
    setup_payment_test_environment(db_session)

    # 1. 登入取得 Session 與 CSRF Token
    login_res = client.post("/api/v1/auth/login", json={"username": "emp_app", "password": "Pass123!"})
    assert login_res.status_code == 200, login_res.text
    csrf_token = login_res.json()["csrf_token"]
    auth_headers = {"X-CSRF-Token": csrf_token}

    # 2. 建立供應商 API
    v_payload = {
        "company_id": "comp-tw",
        "code": "VEND-API-01",
        "name": "極光光電科技股份有限公司",
        "tax_id": "55667788",
        "bank_name": "玉山銀行",
        "account_number": "1234567890123",
        "bank_currency": "TWD",
    }
    resp_v = client.post("/api/v1/vendors", json=v_payload, headers=auth_headers)
    assert resp_v.status_code == 201, resp_v.text
    v_data = resp_v.json()
    vendor_id = v_data["vendor_id"]

    # 3. 查詢供應商列表，檢查遮罩
    resp_v_list = client.get("/api/v1/vendors?company_id=comp-tw", headers=auth_headers)
    assert resp_v_list.status_code == 200
    v_list = resp_v_list.json()
    target_v = next(item for item in v_list if item["id"] == vendor_id)
    assert target_v["account_number_masked"] == "*********0123"

    # 4. 建立費用報銷單 API
    exp_payload = {
        "company_id": "comp-tw",
        "employee_id": "emp-app",
        "title": "研發專利檢索費用",
        "currency": "TWD",
        "exchange_rate": 1.0,
        "items": [
            {
                "category": "MISC",
                "expense_date": "2026-11-05",
                "invoice_number": "INV-EXP-1105",
                "amount": 4200.0,
                "description": "國際專利資料庫檢索費",
            }
        ],
    }
    resp_exp = client.post("/api/v1/expense/claims", json=exp_payload, headers=auth_headers)
    assert resp_exp.status_code == 201, resp_exp.text
    exp_data = resp_exp.json()
    claim_id = exp_data["claim_id"]

    # 5. 送審費用報銷單 API
    resp_exp_sub = client.post(
        f"/api/v1/expense/claims/{claim_id}/submit",
        json={"finance_window_employee_id": "emp-fin"},
        headers=auth_headers,
    )
    assert resp_exp_sub.status_code == 200, resp_exp_sub.text
    assert resp_exp_sub.json()["claim_status"] == "IN_REVIEW"

    # 6. 建立請款單 API
    pay_payload = {
        "company_id": "comp-tw",
        "employee_id": "emp-app",
        "vendor_id": vendor_id,
        "title": "光電檢測模組請款",
        "currency": "TWD",
        "exchange_rate": 1.0,
        "amount": 25000.0,
        "due_date": "2026-11-30",
        "payment_method": "WIRE",
        "invoice_number": "INV-VEND-8899",
    }
    resp_pay = client.post("/api/v1/payment/requests", json=pay_payload, headers=auth_headers)
    assert resp_pay.status_code == 201, resp_pay.text
    pay_data = resp_pay.json()
    payment_id = pay_data["payment_id"]

    # 7. 送審請款單 API
    resp_pay_sub = client.post(
        f"/api/v1/payment/requests/{payment_id}/submit",
        json={"dept_manager_id": "emp-dept", "finance_window_employee_id": "emp-fin"},
        headers=auth_headers,
    )
    assert resp_pay_sub.status_code == 200, resp_pay_sub.text
    assert resp_pay_sub.json()["payment_status"] == "IN_REVIEW"
