import pytest
from datetime import date, timedelta
from fastapi import status

from app.core.security import hash_password
from app.models.auth import User, Role, Permission, RolePermission, UserRole, UserScope
from app.models.hr import Company, Organization, Employee, LeaveType, Shift, CalendarDay
from app.core.hr_rules import LeaveLedgerService
from app.core.errors import AppException


@pytest.fixture
def hr_setup(db_session):
    """建立人事模組基礎測試資料"""
    # 建立公司
    comp_tw = Company(id="ETJ-TW", name="鈺創台灣總部", default_timezone="Asia/Taipei", default_currency="TWD")
    comp_jp = Company(id="ETJ-JP", name="福岡支社", default_timezone="Asia/Tokyo", default_currency="JPY")
    db_session.add_all([comp_tw, comp_jp])
    db_session.commit()

    # 建立人事管理員使用者
    admin_user = User(
        username="hr_admin",
        email="hr@etron.com",
        hashed_password=hash_password("AdminPass123!"),
        display_name="人事專員",
        primary_company_id="ETJ-TW",
        is_active=True,
        is_first_login=False,
    )
    db_session.add(admin_user)

    perm = Permission(code="hr.employee.manage", name="人事管理", module="HR")
    role = Role(id="HR_ADMIN", name="人事主管")
    db_session.add_all([perm, role])
    db_session.commit()

    rp = RolePermission(role_id="HR_ADMIN", permission_code="hr.employee.manage")
    ur = UserRole(user_id=admin_user.id, role_id="HR_ADMIN", company_id="ETJ-TW")
    scope = UserScope(user_id=admin_user.id, company_id="ETJ-TW", scope_type="COMPANY")
    db_session.add_all([rp, ur, scope])
    db_session.commit()

    # 建立特別休假假別
    lt_annual = LeaveType(
        id="ANNUAL",
        company_id="ETJ-TW",
        code="ANNUAL",
        name="特別休假",
        unit="MINUTES",
        requires_attachment=False,
        is_paid=True,
    )
    db_session.add(lt_annual)
    db_session.commit()

    return {"admin": admin_user, "comp_tw": comp_tw, "comp_jp": comp_jp, "lt_annual": lt_annual}


def test_organization_cycle_detection(client, hr_setup, db_session):
    """驗證組織階層循環檢測：禁止 A -> B -> A 循環依賴"""
    # 建立根組織 A (研發處)
    org_a = Organization(id="ORG-RD", company_id="ETJ-TW", code="RD", name="研發處", parent_id=None)
    # 建立子組織 B (軟體部, parent 為 A)
    org_b = Organization(id="ORG-SW", company_id="ETJ-TW", code="SW", name="軟體部", parent_id="ORG-RD")
    db_session.add_all([org_a, org_b])
    db_session.commit()

    # 先登入取得 CSRF Token
    login_res = client.post("/api/v1/auth/login", json={"username": "hr_admin", "password": "AdminPass123!"})
    csrf_token = login_res.json()["csrf_token"]

    # 嘗試建立組織 C，並將 parent 設為 ORG-SW
    create_c_res = client.post(
        "/api/v1/hr/organizations",
        json={"id": "ORG-AI", "company_id": "ETJ-TW", "code": "AI", "name": "AI課", "parent_id": "ORG-SW"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert create_c_res.status_code == status.HTTP_201_CREATED

    # 嘗試將根組織 A 的 parent 設為 C (形成 A -> B -> C -> A 循環)
    cycle_res = client.post(
        "/api/v1/hr/organizations",
        json={"id": "ORG-RD", "company_id": "ETJ-TW", "code": "RD", "name": "研發處", "parent_id": "ORG-AI"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert cycle_res.status_code == status.HTTP_400_BAD_REQUEST
    assert cycle_res.json()["error"]["code"] == "ORGANIZATION_CYCLE_DETECTED"


def test_manager_cycle_detection(client, hr_setup, db_session):
    """驗證主管關係鏈循環檢測：禁止 A 是 B 的主管，同時 B 又被設為 A 的主管"""
    org = Organization(id="ORG-DEPT", company_id="ETJ-TW", code="DEPT", name="業務部", parent_id=None)
    db_session.add(org)
    db_session.commit()

    emp_a = Employee(
        employee_no="TW001", company_id="ETJ-TW", organization_id="ORG-DEPT",
        full_name="陳處長", email="a@etron.com", hire_date=date(2025, 1, 1), status="ACTIVE",
    )
    emp_b = Employee(
        employee_no="TW002", company_id="ETJ-TW", organization_id="ORG-DEPT",
        full_name="林副理", email="b@etron.com", hire_date=date(2025, 3, 1), status="ACTIVE",
    )
    db_session.add_all([emp_a, emp_b])
    db_session.commit()

    login_res = client.post("/api/v1/auth/login", json={"username": "hr_admin", "password": "AdminPass123!"})
    csrf_token = login_res.json()["csrf_token"]

    # 設定 A 是 B 的直屬主管 (B 的主管是 A)
    set_mgr_res1 = client.post(
        f"/api/v1/hr/employees/{emp_b.id}/manager",
        json={"manager_id": emp_a.id, "relation_type": "DIRECT", "effective_from": "2026-01-01"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert set_mgr_res1.status_code == status.HTTP_200_OK

    # 嘗試將 B 設為 A 的主管 (形成循環) -> 必須嚴格拒絕！
    cycle_res = client.post(
        f"/api/v1/hr/employees/{emp_a.id}/manager",
        json={"manager_id": emp_b.id, "relation_type": "DIRECT", "effective_from": "2026-01-01"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert cycle_res.status_code == status.HTTP_400_BAD_REQUEST
    assert cycle_res.json()["error"]["code"] == "MANAGER_CYCLE_DETECTED"


def test_employee_transfer_and_history(client, hr_setup, db_session):
    """驗證員工調職與異動歷史紀錄留存"""
    org1 = Organization(id="ORG-01", company_id="ETJ-TW", code="O1", name="部門1", parent_id=None)
    org2 = Organization(id="ORG-02", company_id="ETJ-TW", code="O2", name="部門2", parent_id=None)
    db_session.add_all([org1, org2])
    db_session.commit()

    emp = Employee(
        employee_no="TW009", company_id="ETJ-TW", organization_id="ORG-01",
        full_name="張專員", email="zhang@etron.com", hire_date=date(2026, 1, 1), status="ACTIVE",
    )
    db_session.add(emp)
    db_session.commit()

    login_res = client.post("/api/v1/auth/login", json={"username": "hr_admin", "password": "AdminPass123!"})
    csrf_token = login_res.json()["csrf_token"]

    # 調職至部門2
    transfer_res = client.post(
        f"/api/v1/hr/employees/{emp.id}/transfer",
        json={"new_organization_id": "ORG-02", "effective_date": "2026-06-01", "notes": "專案支援輪調"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert transfer_res.status_code == status.HTTP_200_OK

    # 驗證員工目前部門已更新為 ORG-02
    db_session.refresh(emp)
    assert emp.organization_id == "ORG-02"
    assert len(emp.changes) == 1
    assert emp.changes[0].change_type == "TRANSFER"
    assert emp.changes[0].before_organization_id == "ORG-01"
    assert emp.changes[0].after_organization_id == "ORG-02"


def test_leave_ledger_atomic_lifecycle_and_overdraw_protection(db_session, hr_setup):
    """
    假額不可變帳本完整生命週期測試：
    1. GRANT: 給予假額 4800 分鐘 (10天)
    2. 查詢可用餘額為 4800 分鐘
    3. HOLD: 送審請假 480 分鐘 (1天)，可用餘額變為 4320 分鐘
    4. 超額防護: 嘗試再 HOLD 5000 分鐘，拋出 INSUFFICIENT_LEAVE_BALANCE 拒絕超支
    5. COMMIT: 假單核准，扣抵 480 分鐘，可用額度仍為 4320 分鐘
    6. RELEASE: 若另一筆 240 分鐘假單退回，釋放預占額度
    """
    org = Organization(id="ORG-TEST", company_id="ETJ-TW", code="TEST", name="測試部", parent_id=None)
    db_session.add(org)
    db_session.commit()

    emp = Employee(
        employee_no="TW999", company_id="ETJ-TW", organization_id="ORG-TEST",
        full_name="李工程師", email="lee@etron.com", hire_date=date(2025, 1, 1), status="ACTIVE",
    )
    db_session.add(emp)
    db_session.commit()

    valid_start = date(2026, 1, 1)
    valid_end = date(2026, 12, 31)

    # 1. 給予假額 4800 分鐘 (10 天)
    LeaveLedgerService.grant_leave(
        db=db_session,
        company_id="ETJ-TW",
        employee_id=emp.id,
        leave_type_id="ANNUAL",
        amount_minutes=4800,
        valid_from=valid_start,
        valid_to=valid_end,
        created_by="system",
    )

    # 2. 驗證可用餘額為 4800
    bal1 = LeaveLedgerService.get_available_balance(db_session, emp.id, "ANNUAL", date(2026, 5, 1))
    assert bal1 == 4800

    # 3. HOLD: 預占 480 分鐘
    LeaveLedgerService.hold_leave(
        db=db_session,
        company_id="ETJ-TW",
        employee_id=emp.id,
        leave_type_id="ANNUAL",
        amount_minutes=480,
        reference_doc_id="LV-202605-001",
        valid_from=valid_start,
        valid_to=valid_end,
        created_by=emp.id,
    )
    bal2 = LeaveLedgerService.get_available_balance(db_session, emp.id, "ANNUAL", date(2026, 5, 1))
    assert bal2 == 4320  # 4800 - 480

    # 4. 超支防護測試：嘗試預占 5000 分鐘 (> 4320)
    with pytest.raises(AppException) as exc_info:
        LeaveLedgerService.hold_leave(
            db=db_session,
            company_id="ETJ-TW",
            employee_id=emp.id,
            leave_type_id="ANNUAL",
            amount_minutes=5000,
            reference_doc_id="LV-202605-002",
            valid_from=valid_start,
            valid_to=valid_end,
            created_by=emp.id,
        )
    assert exc_info.value.code == "INSUFFICIENT_LEAVE_BALANCE"

    # 5. COMMIT: 假單核准扣抵 480 分鐘
    LeaveLedgerService.commit_leave(
        db=db_session,
        company_id="ETJ-TW",
        employee_id=emp.id,
        leave_type_id="ANNUAL",
        amount_minutes=480,
        reference_doc_id="LV-202605-001",
        valid_from=valid_start,
        valid_to=valid_end,
        created_by="manager",
    )
    # RELEASE 該筆 HOLD 額度以完成沖銷結算
    LeaveLedgerService.release_leave(
        db=db_session,
        company_id="ETJ-TW",
        employee_id=emp.id,
        leave_type_id="ANNUAL",
        amount_minutes=480,
        reference_doc_id="LV-202605-001",
        valid_from=valid_start,
        valid_to=valid_end,
        created_by="system",
    )
    bal3 = LeaveLedgerService.get_available_balance(db_session, emp.id, "ANNUAL", date(2026, 5, 1))
    assert bal3 == 4320  # 正式扣除後剩餘 4320 分鐘


def test_person_master_and_multiple_company_employments(client, hr_setup, db_session):
    """驗證人員主檔與多公司任職分離架構：同一員工可任職於多公司，且同一公司工號獨立、防重複任職"""
    # 建立部門
    org_tw = Organization(id="ORG-TW-RD", company_id="ETJ-TW", code="RD", name="台灣研發部")
    org_jp = Organization(id="ORG-JP-TECH", company_id="ETJ-JP", code="TECH", name="日本技術部")
    db_session.add_all([org_tw, org_jp])
    db_session.commit()

    # 模擬登入
    login_res = client.post("/api/v1/auth/login", json={"username": "hr_admin", "password": "AdminPass123!"})
    assert login_res.status_code == status.HTTP_200_OK
    csrf_token = login_res.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf_token}

    # 1. 於台灣總部建立吳金樹新進報到
    tw_onboard_data = {
        "employee_no": "TW207",
        "company_id": "ETJ-TW",
        "organization_id": "ORG-TW-RD",
        "full_name": "吳金樹",
        "english_name": "Chinshu Wu",
        "national_id": "A123456789",
        "birth_date": "1988-06-15",
        "gender": "MALE",
        "email": "chinshu.wu@etron.com.tw",
        "mobile_phone": "0912345678",
        "job_title": "首席架構師",
        "hire_date": "2026-10-23",
    }
    r1 = client.post("/api/v1/hr/employees", json=tw_onboard_data, headers=headers)
    assert r1.status_code == status.HTTP_201_CREATED
    tw_emp = r1.json()
    assert tw_emp["employee_no"] == "TW207"
    assert tw_emp["person_id"] is not None
    person_id = tw_emp["person_id"]

    # 2. 搜尋集團人員主檔，應能查到吳金樹與其在職公司
    search_res = client.get("/api/v1/hr/persons?keyword=金樹", headers=headers)
    assert search_res.status_code == status.HTTP_200_OK
    persons = search_res.json()
    assert len(persons) >= 1
    found_person = next(p for p in persons if p["id"] == person_id)
    assert found_person["full_name"] == "吳金樹"
    assert "ETJ-TW" in found_person["current_companies"]

    # 3. 同一自然人在福岡支社辦理到職報到 (帶入相同 person_id，工號可為 JP105)
    jp_onboard_data = {
        "person_id": person_id,
        "employee_no": "JP105",
        "company_id": "ETJ-JP",
        "organization_id": "ORG-JP-TECH",
        "full_name": "吳金樹",
        "email": "chinshu.wu@etron.co.jp",
        "hire_date": "2026-10-24",
        "job_title": "日本支社技術總監",
    }
    r2 = client.post("/api/v1/hr/employees", json=jp_onboard_data, headers=headers)
    assert r2.status_code == status.HTTP_201_CREATED
    jp_emp = r2.json()
    assert jp_emp["person_id"] == person_id
    assert jp_emp["employee_no"] == "JP105"

    # 4. 檢視日本任職詳情，應能看見其他在職公司記錄 (ETJ-TW, TW207)
    detail_res = client.get(f"/api/v1/hr/employees/{jp_emp['id']}", headers=headers)
    assert detail_res.status_code == status.HTTP_200_OK
    detail_data = detail_res.json()
    assert len(detail_data["other_employments"]) == 1
    assert detail_data["other_employments"][0]["company_id"] == "ETJ-TW"
    assert detail_data["other_employments"][0]["employee_no"] == "TW207"

    # 5. 驗證同公司防重複任職：嘗試在同一公司 (ETJ-TW) 再次以同一 Person 報到，應被攔截
    dup_onboard_data = {
        "person_id": person_id,
        "employee_no": "TW999",
        "company_id": "ETJ-TW",
        "organization_id": "ORG-TW-RD",
        "full_name": "吳金樹",
        "email": "duplicate@etron.com.tw",
        "hire_date": "2026-11-01",
    }
    r_dup = client.post("/api/v1/hr/employees", json=dup_onboard_data, headers=headers)
    assert r_dup.status_code == status.HTTP_409_CONFLICT
    assert r_dup.json()["error"]["code"] == "DUPLICATE_COMPANY_EMPLOYMENT"


def test_leave_type_min_unit_and_paid_type(client, hr_setup):
    """驗證假別之最小計假單位 (0.5小時, 1小時, 1天) 與給薪方式 (全薪, 半薪, 不給薪)"""
    login_res = client.post("/api/v1/auth/login", json={"username": "hr_admin", "password": "AdminPass123!"})
    csrf_token = login_res.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf_token}

    # 1. 建立半薪假種 (例如病假 SICK-01，最小單位 HALF_HOUR, paid_type=HALF)
    lt_half_data = {
        "id": "LT-TW-SICK-HALF",
        "company_id": "ETJ-TW",
        "code": "SICK-HALF",
        "name": "普通傷病假 (半薪)",
        "unit": "HALF_HOUR",
        "paid_type": "HALF",
        "requires_attachment": True,
    }
    r1 = client.post("/api/v1/hr/leave-types", json=lt_half_data, headers=headers)
    assert r1.status_code == status.HTTP_201_CREATED
    d1 = r1.json()
    assert d1["unit"] == "HALF_HOUR"
    assert d1["paid_type"] == "HALF"
    assert d1["is_paid"] is True  # 半薪依然為有給 (is_paid=True)

    # 2. 建立不給薪假種 (例如事假 PERSONAL-UNPAID，最小單位 ONE_HOUR, paid_type=UNPAID)
    lt_unpaid_data = {
        "id": "LT-TW-UNPAID",
        "company_id": "ETJ-TW",
        "code": "PERSONAL-UNPAID",
        "name": "事假 (無給)",
        "unit": "ONE_HOUR",
        "paid_type": "UNPAID",
        "requires_attachment": False,
    }
    r2 = client.post("/api/v1/hr/leave-types", json=lt_unpaid_data, headers=headers)
    assert r2.status_code == status.HTTP_201_CREATED
    d2 = r2.json()
    assert d2["unit"] == "ONE_HOUR"
    assert d2["paid_type"] == "UNPAID"
    assert d2["is_paid"] is False  # 不給薪對應 is_paid=False

    # 3. 更新假種設定 (將普通傷病假更新為最小單位 ONE_DAY，給薪方式更新為 FULL 全薪)
    update_data = {
        "unit": "ONE_DAY",
        "paid_type": "FULL",
    }
    r3 = client.put(f"/api/v1/hr/leave-types/{d1['id']}", json=update_data, headers=headers)
    assert r3.status_code == status.HTTP_200_OK
    d3 = r3.json()
    assert d3["unit"] == "ONE_DAY"
    assert d3["paid_type"] == "FULL"
    assert d3["is_paid"] is True


