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
from app.models.seal_contract import Seal, SealHandover, SealRequest, Contract
from app.models.workflow import WorkflowInstance, ApprovalAssignment
from app.core.seal_contract_service import SealContractService


def setup_seal_contract_test_environment(db: Session):
    """建立用印與合約垂直切片測試所需完整環境 (公司、組織、主管鏈、印鑑清冊、員工與帳號)"""
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
    org = Organization(id="org-legal", company_id="comp-tw", code="LEGAL", name="法務行政處", level="DIVISION")
    db.add_all([shift, org])
    db.commit()

    # 2. 員工清單：申請人、直屬主管(L1)、第二層主管(L2)、第三層主管(L3)、法務窗口、印鑑保管人、新保管人
    emp_app = Employee(
        id="emp-app",
        company_id="comp-tw",
        organization_id="org-legal",
        employee_no="TW201",
        full_name="申請人小明",
        email="applicant@etronjf8.com",
        hire_date=date(2025, 1, 1),
        status="ACTIVE",
    )
    emp_l1 = Employee(
        id="emp-l1",
        company_id="comp-tw",
        organization_id="org-legal",
        employee_no="TW202",
        full_name="直屬主管大明",
        email="manager_l1@etronjf8.com",
        hire_date=date(2024, 1, 1),
        status="ACTIVE",
    )
    emp_l2 = Employee(
        id="emp-l2",
        company_id="comp-tw",
        organization_id="org-legal",
        employee_no="TW203",
        full_name="二級主管老張",
        email="manager_l2@etronjf8.com",
        hire_date=date(2023, 1, 1),
        status="ACTIVE",
    )
    emp_l3 = Employee(
        id="emp-l3",
        company_id="comp-tw",
        organization_id="org-legal",
        employee_no="TW204",
        full_name="三級主管老陳",
        email="manager_l3@etronjf8.com",
        hire_date=date(2022, 1, 1),
        status="ACTIVE",
    )
    emp_legal = Employee(
        id="emp-legal",
        company_id="comp-tw",
        organization_id="org-legal",
        employee_no="TW205",
        full_name="法務窗口小律",
        email="legal@etronjf8.com",
        hire_date=date(2023, 1, 1),
        status="ACTIVE",
    )
    emp_cust = Employee(
        id="emp-cust",
        company_id="comp-tw",
        organization_id="org-legal",
        employee_no="TW206",
        full_name="印鑑保管人老李",
        email="custodian@etronjf8.com",
        hire_date=date(2021, 1, 1),
        status="ACTIVE",
    )
    emp_cust2 = Employee(
        id="emp-cust2",
        company_id="comp-tw",
        organization_id="org-legal",
        employee_no="TW207",
        full_name="新接任保管人小趙",
        email="custodian2@etronjf8.com",
        hire_date=date(2024, 1, 1),
        status="ACTIVE",
    )
    db.add_all([emp_app, emp_l1, emp_l2, emp_l3, emp_legal, emp_cust, emp_cust2])
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

    # 4. 印鑑清冊主檔：公司大章 (保管人為 emp-cust)
    seal = Seal(
        id="seal-comp-01",
        company_id="comp-tw",
        code="SEAL-01",
        name="台灣總部公司大印",
        seal_type="COMPANY_SEAL",
        custodian_employee_id="emp-cust",
        effective_from=date(2025, 1, 1),
        is_active=True,
        version=1,
    )
    db.add(seal)
    db.commit()

    # 5. User 帳號
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
    db.add(user_app)
    db.commit()


def test_seal_registry_and_handover_audit(db_session: Session):
    """
    測試情境 1：印鑑主檔與更換保管人審計交接留痕
    - 初始保管人為老李 (emp-cust)
    - 辦理保管人交接給小趙 (emp-cust2)
    - 驗證版本號遞增與交接歷史記錄 (SealHandover)
    - 驗證錯誤原保管人交接防呆 (INVALID_FROM_CUSTODIAN)
    """
    setup_seal_contract_test_environment(db_session)
    seal = db_session.get(Seal, "seal-comp-01")
    assert seal.custodian_employee_id == "emp-cust"
    assert seal.version == 1

    # 1. 執行合規交接
    updated_seal = SealContractService.handover_seal(
        db=db_session,
        seal_id="seal-comp-01",
        from_custodian_id="emp-cust",
        to_custodian_id="emp-cust2",
        reason="原保管人調職業務交接",
        handover_date=date(2026, 11, 1),
    )
    assert updated_seal.custodian_employee_id == "emp-cust2"
    assert updated_seal.version == 2

    # 檢查審計日誌
    handovers = SealContractService.get_seal_handovers(db_session, "seal-comp-01")
    assert len(handovers) == 1
    assert handovers[0].from_custodian_id == "emp-cust"
    assert handovers[0].to_custodian_id == "emp-cust2"
    assert handovers[0].reason == "原保管人調職業務交接"

    # 2. 負向測試：以錯誤之原保管人再次嘗試交接 -> 預期失敗
    with pytest.raises(AppException) as exc:
        SealContractService.handover_seal(
            db=db_session,
            seal_id="seal-comp-01",
            from_custodian_id="emp-cust",  # 已經不是 emp-cust
            to_custodian_id="emp-app",
            reason="非法交接",
        )
    assert exc.value.code == "INVALID_FROM_CUSTODIAN"


def test_seal_request_pipeline_and_execution(db_session: Session):
    """
    測試情境 2：用印申請簽核與保管人實體用印登記狀態機
    - 簽核管線：直屬主管 (DIRECT_MANAGER) -> 印鑑保管人 (SEAL_CUSTODIAN)
    - 簽核核准不等於已用印 (APPROVED 但 NOT_SEALED)
    - 保管人執行實體用印登記 (SEALED，記錄份數與掃描件)
    - 防呆：未核准禁止用印；已用印禁止重複登記
    """
    setup_seal_contract_test_environment(db_session)

    # 1. 建立用印申請單
    seal_req = SealContractService.create_seal_request(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        seal_id="seal-comp-01",
        document_name="銀行授權印鑑證明申請書",
        purpose="開立銀行專用帳戶申辦用印",
        copies=2,
    )
    assert seal_req.status == "DRAFT"
    assert seal_req.execution_status == "NOT_SEALED"

    # 2. 申請人送審用印單
    submitted_req = SealContractService.submit_seal_request(
        db=db_session,
        request_id=seal_req.id,
        operator_employee_id="emp-app",
    )
    assert submitted_req.status == "IN_REVIEW"

    # 檢查管線解析：直屬主管審核 -> 印鑑保管人執行
    wf_inst = db_session.get(WorkflowInstance, submitted_req.workflow_instance_id)
    pipeline_names = [n["name"] for n in wf_inst.snapshot_data["resolved_pipeline"]]
    assert pipeline_names == ["直屬主管審核", "印鑑保管人執行"]

    # 3. 第一關：直屬主管大明核准
    assign1 = (
        db_session.query(ApprovalAssignment)
        .filter(
            ApprovalAssignment.instance_id == submitted_req.workflow_instance_id,
            ApprovalAssignment.assigned_employee_id == "emp-l1",
            ApprovalAssignment.is_completed == False,
        )
        .one()
    )
    SealContractService.process_seal_approval(
        db=db_session,
        assignment_id=assign1.id,
        operator_employee_id="emp-l1",
        action="APPROVE",
        comments="同意用印申請",
    )

    # 4. 第二關：印鑑保管人老李核准
    assign2 = (
        db_session.query(ApprovalAssignment)
        .filter(
            ApprovalAssignment.instance_id == submitted_req.workflow_instance_id,
            ApprovalAssignment.assigned_employee_id == "emp-cust",
            ApprovalAssignment.is_completed == False,
        )
        .one()
    )
    SealContractService.process_seal_approval(
        db=db_session,
        assignment_id=assign2.id,
        operator_employee_id="emp-cust",
        action="APPROVE",
        comments="印鑑保管人審核通過",
    )

    db_session.refresh(submitted_req)
    # 規格核心：簽核核准後，狀態為 APPROVED，但實體尚未用印 (NOT_SEALED)
    assert submitted_req.status == "APPROVED"
    assert submitted_req.execution_status == "NOT_SEALED"

    # 5. 保管人老李執行實體用印登記 (execute_seal)
    sealed_req = SealContractService.execute_seal(
        db=db_session,
        request_id=submitted_req.id,
        operator_employee_id="emp-cust",
        sealed_copies=2,
        final_sealed_document_url="https://docs.etronjf8.com/seals/final_20261102.pdf",
    )
    assert sealed_req.execution_status == "SEALED"
    assert sealed_req.sealed_at is not None
    assert sealed_req.sealed_copies == 2
    assert sealed_req.sealed_by_employee_id == "emp-cust"
    assert sealed_req.final_sealed_document_url == "https://docs.etronjf8.com/seals/final_20261102.pdf"

    # 6. 防呆：已用印者禁止重複登記
    with pytest.raises(AppException) as exc:
        SealContractService.execute_seal(
            db=db_session,
            request_id=submitted_req.id,
            operator_employee_id="emp-cust",
            sealed_copies=2,
        )
    assert exc.value.code == "ALREADY_SEALED"


def test_contract_threshold_pipeline(db_session: Session):
    """
    測試情境 3：合約金額門檻管線測試 (CONTRACT)
    管線路徑：
    - < 5000 (如 TWD 0 NDA)：直屬主管審核 -> 法務窗口審查
    - >= 5000 且 < 100000 (如 TWD 50,000)：直屬主管審核 -> 第二層主管審核 (>=5000) -> 法務窗口審查
    - >= 100000 (如 TWD 600,000)：直屬主管審核 -> 第二層主管審核 (>=5000) -> 第三層主管審核 (>=100000) -> 法務窗口審查
    """
    setup_seal_contract_test_environment(db_session)

    # 1. 門檻 < 5000 (TWD 0 無金額保密協議 NDA)
    ctr_nda = SealContractService.create_contract(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        counterparty_name="台灣半導體研究中心",
        title="雙向保密協議 NDA",
        contract_type="NDA",
        start_date=date(2026, 11, 1),
        amount=Decimal("0.0000"),
        needs_seal=False,
    )
    SealContractService.submit_contract(
        db=db_session,
        contract_id=ctr_nda.id,
        operator_employee_id="emp-app",
        legal_window_employee_id="emp-legal",
    )
    wf_nda = db_session.get(WorkflowInstance, ctr_nda.workflow_instance_id)
    pipeline_nda = [n["name"] for n in wf_nda.snapshot_data["resolved_pipeline"]]
    assert pipeline_nda == ["直屬主管審核", "法務窗口審查"]

    # 2. 門檻 >= 5000 且 < 100000 (TWD 50,000 耗材採購合約)
    ctr_mid = SealContractService.create_contract(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        counterparty_name="科技精密設備公司",
        title="耗材採購年度框架協議",
        contract_type="PURCHASE",
        start_date=date(2026, 11, 1),
        amount=Decimal("50000.0000"),
        needs_seal=False,
    )
    SealContractService.submit_contract(
        db=db_session,
        contract_id=ctr_mid.id,
        operator_employee_id="emp-app",
        legal_window_employee_id="emp-legal",
    )
    wf_mid = db_session.get(WorkflowInstance, ctr_mid.workflow_instance_id)
    pipeline_mid = [n["name"] for n in wf_mid.snapshot_data["resolved_pipeline"]]
    assert pipeline_mid == ["直屬主管審核", "第二層主管審核 (>=5000)", "法務窗口審查"]

    # 3. 門檻 >= 100000 (TWD 600,000 大型產學合作服務協議)
    ctr_large = SealContractService.create_contract(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        counterparty_name="國立交通大學",
        title="前瞻IC設計委外研究合約",
        contract_type="SERVICE",
        start_date=date(2026, 11, 1),
        amount=Decimal("600000.0000"),
        needs_seal=False,
    )
    SealContractService.submit_contract(
        db=db_session,
        contract_id=ctr_large.id,
        operator_employee_id="emp-app",
        legal_window_employee_id="emp-legal",
    )
    wf_large = db_session.get(WorkflowInstance, ctr_large.workflow_instance_id)
    pipeline_large = [n["name"] for n in wf_large.snapshot_data["resolved_pipeline"]]
    assert pipeline_large == [
        "直屬主管審核",
        "第二層主管審核 (>=5000)",
        "第三層主管審核 (>=100000)",
        "法務窗口審查",
    ]


def test_contract_needs_seal_dynamic_pipeline_and_legal_opinion(db_session: Session):
    """
    測試情境 4：合約是否需要用印之動態管線與法務意見寫入
    - needs_seal == true：管線動態串接「印鑑保管人執行 (需用印)」節點
    - 法務窗口審批時錄入 legal_opinion，合約主表同步保存
    """
    setup_seal_contract_test_environment(db_session)

    # 建立需實體用印之產學合作合約 (needs_seal=True, amount=60,000)
    contract = SealContractService.create_contract(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        counterparty_name="先進半導體聯盟",
        title="半導體測試認證服務合約",
        contract_type="SERVICE",
        start_date=date(2026, 11, 10),
        amount=Decimal("60000.0000"),
        needs_seal=True,
    )

    # 送審
    submitted_ctr = SealContractService.submit_contract(
        db=db_session,
        contract_id=contract.id,
        operator_employee_id="emp-app",
        legal_window_employee_id="emp-legal",
        seal_custodian_employee_id="emp-cust",
    )

    # 驗證動態管線：直屬主管 -> 二級主管 -> 法務窗口 -> 印鑑保管人執行 (需用印)
    wf_inst = db_session.get(WorkflowInstance, submitted_ctr.workflow_instance_id)
    pipeline_names = [n["name"] for n in wf_inst.snapshot_data["resolved_pipeline"]]
    assert pipeline_names == [
        "直屬主管審核",
        "第二層主管審核 (>=5000)",
        "法務窗口審查",
        "印鑑保管人執行 (需用印)",
    ]

    # 1. 直屬主管核准
    assign1 = (
        db_session.query(ApprovalAssignment)
        .filter(
            ApprovalAssignment.instance_id == submitted_ctr.workflow_instance_id,
            ApprovalAssignment.assigned_employee_id == "emp-l1",
            ApprovalAssignment.is_completed == False,
        )
        .one()
    )
    SealContractService.process_contract_approval(
        db=db_session,
        assignment_id=assign1.id,
        operator_employee_id="emp-l1",
        action="APPROVE",
    )

    # 2. 第二層主管核准
    assign2 = (
        db_session.query(ApprovalAssignment)
        .filter(
            ApprovalAssignment.instance_id == submitted_ctr.workflow_instance_id,
            ApprovalAssignment.assigned_employee_id == "emp-l2",
            ApprovalAssignment.is_completed == False,
        )
        .one()
    )
    SealContractService.process_contract_approval(
        db=db_session,
        assignment_id=assign2.id,
        operator_employee_id="emp-l2",
        action="APPROVE",
    )

    # 3. 法務窗口審查：核准並輸入法務法律審查意見
    assign3 = (
        db_session.query(ApprovalAssignment)
        .filter(
            ApprovalAssignment.instance_id == submitted_ctr.workflow_instance_id,
            ApprovalAssignment.assigned_employee_id == "emp-legal",
            ApprovalAssignment.is_completed == False,
        )
        .one()
    )
    SealContractService.process_contract_approval(
        db=db_session,
        assignment_id=assign3.id,
        operator_employee_id="emp-legal",
        action="APPROVE",
        comments="條款審查完畢",
        legal_opinion="本合約智財權益歸屬已於第8條明定由我方單獨享有，風險受控，准予用印。",
    )
    db_session.refresh(submitted_ctr)
    assert submitted_ctr.legal_opinion == "本合約智財權益歸屬已於第8條明定由我方單獨享有，風險受控，准予用印。"

    # 4. 印鑑保管人核准
    assign4 = (
        db_session.query(ApprovalAssignment)
        .filter(
            ApprovalAssignment.instance_id == submitted_ctr.workflow_instance_id,
            ApprovalAssignment.assigned_employee_id == "emp-cust",
            ApprovalAssignment.is_completed == False,
        )
        .one()
    )
    SealContractService.process_contract_approval(
        db=db_session,
        assignment_id=assign4.id,
        operator_employee_id="emp-cust",
        action="APPROVE",
        comments="保管人核准用印",
    )

    db_session.refresh(submitted_ctr)
    assert submitted_ctr.status == "APPROVED"
    assert submitted_ctr.lifecycle_status == "ACTIVE"


def test_contract_archive_and_renewal_linkage(db_session: Session):
    """
    測試情境 5：合約歸檔與續約關聯作業
    - 完簽合約歸檔上傳最終簽署用印文件
    - 未完簽合約禁止歸檔防呆
    - 續約合約關聯 renewed_from_contract_id 追蹤
    """
    setup_seal_contract_test_environment(db_session)

    # 1. 建立並完簽首份合約
    ctr1 = SealContractService.create_contract(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        counterparty_name="辦公雲端服務商",
        title="雲端伺服器租賃 2025 年度合約",
        contract_type="SERVICE",
        start_date=date(2025, 1, 1),
        end_date=date(2025, 12, 31),
        amount=Decimal("12000.0000"),
    )
    ctr1.status = "APPROVED"
    ctr1.lifecycle_status = "ACTIVE"
    db_session.commit()

    # 2. 執行合約歸檔
    archived_ctr = SealContractService.archive_contract(
        db=db_session,
        contract_id=ctr1.id,
        signed_document_url="https://docs.etronjf8.com/contracts/signed_ctr_2025.pdf",
    )
    assert archived_ctr.signed_document_url == "https://docs.etronjf8.com/contracts/signed_ctr_2025.pdf"
    assert archived_ctr.archived_at is not None

    # 3. 建立 2026 年度續約合約，並關聯 2025 原合約
    renew_ctr = SealContractService.create_contract(
        db=db_session,
        company_id="comp-tw",
        employee_id="emp-app",
        counterparty_name="辦公雲端服務商",
        title="雲端伺服器租賃 2026 年度續約合約",
        contract_type="SERVICE",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        amount=Decimal("13000.0000"),
        renewed_from_contract_id=ctr1.id,
    )
    assert renew_ctr.renewed_from_contract_id == ctr1.id


def test_seal_and_contract_http_api_flow(client: TestClient, db_session: Session):
    """
    測試情境 6：FastAPI HTTP API 端到端路由整合測試
    - 登入認證取得 CSRF Token 與 Session
    - POST /api/v1/seals (建立印鑑)
    - GET /api/v1/seals (查詢印鑑清冊)
    - POST /api/v1/seal/requests (建立用印申請單)
    - POST /api/v1/seal/requests/{id}/submit (送審用印單)
    - POST /api/v1/contracts (建立合約單)
    - POST /api/v1/contracts/{id}/submit (送審合約單)
    - GET /api/v1/contracts/{id} (查詢合約單詳情)
    """
    setup_seal_contract_test_environment(db_session)

    # 1. 登入取得 Session 與 CSRF Token
    login_res = client.post("/api/v1/auth/login", json={"username": "emp_app", "password": "Pass123!"})
    assert login_res.status_code == 200, login_res.text
    csrf_token = login_res.json()["csrf_token"]
    auth_headers = {"X-CSRF-Token": csrf_token}

    # 2. 建立新印鑑 API
    seal_payload = {
        "company_id": "comp-tw",
        "code": "SEAL-API-02",
        "name": "合約專用騎縫章",
        "seal_type": "CONTRACT_SEAL",
        "custodian_employee_id": "emp-cust",
        "effective_from": "2026-11-01",
    }
    resp_s = client.post("/api/v1/seals", json=seal_payload, headers=auth_headers)
    assert resp_s.status_code == 201, resp_s.text
    seal_id = resp_s.json()["seal_id"]

    # 3. 查詢印鑑列表
    resp_s_list = client.get("/api/v1/seals?company_id=comp-tw", headers=auth_headers)
    assert resp_s_list.status_code == 200
    assert any(s["id"] == seal_id for s in resp_s_list.json())

    # 4. 建立用印申請 API
    req_payload = {
        "company_id": "comp-tw",
        "employee_id": "emp-app",
        "seal_id": seal_id,
        "document_name": "產學合作保密承諾書",
        "purpose": "產學專案啟動",
        "copies": 1,
    }
    resp_req = client.post("/api/v1/seal/requests", json=req_payload, headers=auth_headers)
    assert resp_req.status_code == 201, resp_req.text
    request_id = resp_req.json()["request_id"]

    # 5. 送審用印申請單 API
    resp_req_sub = client.post(
        f"/api/v1/seal/requests/{request_id}/submit",
        headers=auth_headers,
    )
    assert resp_req_sub.status_code == 200, resp_req_sub.text
    assert resp_req_sub.json()["seal_status"] == "IN_REVIEW"

    # 6. 建立合約單 API
    ctr_payload = {
        "company_id": "comp-tw",
        "employee_id": "emp-app",
        "counterparty_name": "美商高科技儀器",
        "title": "光學顯微鏡租賃合約",
        "contract_type": "LEASE",
        "start_date": "2026-11-01",
        "end_date": "2027-10-31",
        "currency": "TWD",
        "exchange_rate": 1.0,
        "amount": 85000.0,
        "needs_seal": False,
    }
    resp_ctr = client.post("/api/v1/contracts", json=ctr_payload, headers=auth_headers)
    assert resp_ctr.status_code == 201, resp_ctr.text
    contract_id = resp_ctr.json()["contract_id"]

    # 7. 送審合約單 API
    resp_ctr_sub = client.post(
        f"/api/v1/contracts/{contract_id}/submit",
        json={"legal_window_employee_id": "emp-legal"},
        headers=auth_headers,
    )
    assert resp_ctr_sub.status_code == 200, resp_ctr_sub.text
    assert resp_ctr_sub.json()["contract_status"] == "IN_REVIEW"

    # 8. 查詢合約詳情 API
    resp_detail = client.get(f"/api/v1/contracts/{contract_id}", headers=auth_headers)
    assert resp_detail.status_code == 200
    assert resp_detail.json()["id"] == contract_id
    assert resp_detail.json()["status"] == "IN_REVIEW"
