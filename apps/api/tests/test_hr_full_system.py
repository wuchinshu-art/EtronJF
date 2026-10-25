import pytest
from datetime import date, timedelta
from fastapi import status

from app.core.security import hash_password, verify_password
from app.models.auth import User, Role, Permission, RolePermission, UserRole, UserScope, Session as AuthSession
from app.models.hr import Company, Organization, Employee, LeaveType, Shift, CalendarDay, EmployeeChange, LeaveLedger
from app.core.hr_rules import LeaveLedgerService


@pytest.fixture
def hr_env(db_session):
    """人事全模組整合測試環境設定"""
    # 建立台灣總部與福岡支社
    comp_tw = Company(id="ETJ-TW", name="鈺創台灣總部", default_timezone="Asia/Taipei", default_currency="TWD")
    comp_jp = Company(id="ETJ-JP", name="福岡支社", default_timezone="Asia/Tokyo", default_currency="JPY")
    db_session.add_all([comp_tw, comp_jp])
    db_session.commit()

    # 建立部門
    dept_rd = Organization(id="ORG-RD", company_id="ETJ-TW", code="RD", name="研發處", parent_id=None, level="DIVISION")
    dept_sw = Organization(id="ORG-SW", company_id="ETJ-TW", code="SW", name="軟體部", parent_id="ORG-RD", level="DEPARTMENT")
    dept_jp = Organization(id="ORG-JP-DEV", company_id="ETJ-JP", code="JPDEV", name="福岡開發課", parent_id=None, level="SECTION")
    db_session.add_all([dept_rd, dept_sw, dept_jp])
    db_session.commit()

    # 建立人事管理員
    admin_user = User(
        username="hr_manager",
        email="hr_manager@etron.com",
        hashed_password=hash_password("AdminSecure123!"),
        display_name="人事經理",
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

    # 登入取得管理員 session 與 csrf token
    return {
        "admin": admin_user,
        "comp_tw": comp_tw,
        "comp_jp": comp_jp,
        "dept_rd": dept_rd,
        "dept_sw": dept_sw,
    }


def get_auth_headers(client, username="hr_manager", password="AdminSecure123!"):
    """輔助函數：登入並回傳 CSRF Token 與 Headers"""
    res = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert res.status_code == status.HTTP_200_OK
    csrf_token = res.json()["csrf_token"]
    return {"X-CSRF-Token": csrf_token}


def test_employee_onboarding_and_account_provisioning(client, hr_env, db_session):
    """
    測試 1：員工報到作業與連動開通系統登入帳號
    - 建立員工
    - 自動寫入 ONBOARD 異動分錄
    - 自動建立 User 帳號，驗證 is_first_login=True 與 Argon2id 密碼雜湊
    - 使用該帳號成功登入
    """
    headers = get_auth_headers(client)

    onboard_payload = {
        "employee_no": "TW1001",
        "company_id": "ETJ-TW",
        "organization_id": "ORG-SW",
        "full_name": "林新進",
        "email": "newbie@etron.com",
        "hire_date": "2026-11-01",
        "create_user_account": True,
        "initial_password": "InitPass1234!",
    }

    res = client.post("/api/v1/hr/employees", json=onboard_payload, headers=headers)
    assert res.status_code == status.HTTP_201_CREATED
    emp_data = res.json()
    assert emp_data["employee_no"] == "TW1001"
    assert emp_data["status"] == "ACTIVE"

    # 驗證異動歷史
    changes = db_session.query(EmployeeChange).filter_by(employee_id=emp_data["id"]).all()
    assert len(changes) == 1
    assert changes[0].change_type == "ONBOARD"
    assert str(changes[0].effective_date) == "2026-11-01"

    # 驗證連動建立之使用者帳號
    user = db_session.query(User).filter_by(username="TW1001").first()
    assert user is not None
    assert user.is_first_login is True
    assert user.is_active is True
    assert user.employee_id == emp_data["id"]
    assert verify_password("InitPass1234!", user.hashed_password) is True

    # 測試新進員工使用初始密碼登入
    login_res = client.post("/api/v1/auth/login", json={"username": "TW1001", "password": "InitPass1234!"})
    assert login_res.status_code == status.HTTP_200_OK
    assert login_res.json()["is_first_login"] is True


def test_organization_and_manager_dag_cycle_prevention(client, hr_env, db_session):
    """
    測試 2：組織階層與主管鏈 DAG 防循環檢驗
    - 阻擋組織樹互相依賴 (Cycle)
    - 阻擋主管相互核決死循環 (Cycle)
    """
    headers = get_auth_headers(client)

    # 1. 組織循環：ORG-RD(上) -> ORG-SW(下)。嘗試建立 ORG-SUB (parent 為 SW)，再嘗試將 RD parent 設為 SUB
    res_sub = client.post(
        "/api/v1/hr/organizations",
        json={"id": "ORG-SUB", "company_id": "ETJ-TW", "code": "SUB", "name": "核心組", "parent_id": "ORG-SW"},
        headers=headers,
    )
    assert res_sub.status_code == status.HTTP_201_CREATED

    res_cycle = client.post(
        "/api/v1/hr/organizations",
        json={"id": "ORG-RD", "company_id": "ETJ-TW", "code": "RD", "name": "研發處", "parent_id": "ORG-SUB"},
        headers=headers,
    )
    assert res_cycle.status_code == status.HTTP_400_BAD_REQUEST
    assert res_cycle.json()["error"]["code"] == "ORGANIZATION_CYCLE_DETECTED"

    # 2. 主管循環：建立員工 A 與員工 B
    emp_a = Employee(employee_no="TW201", company_id="ETJ-TW", organization_id="ORG-SW", full_name="主管A", email="a@etron.com", hire_date=date(2026, 1, 1))
    emp_b = Employee(employee_no="TW202", company_id="ETJ-TW", organization_id="ORG-SW", full_name="成員B", email="b@etron.com", hire_date=date(2026, 1, 1))
    db_session.add_all([emp_a, emp_b])
    db_session.commit()

    # 設定 A 為 B 的直屬主管
    res_mgr_1 = client.post(
        f"/api/v1/hr/employees/{emp_b.id}/manager",
        json={"manager_id": emp_a.id, "relation_type": "DIRECT", "effective_from": "2026-01-01"},
        headers=headers,
    )
    assert res_mgr_1.status_code == status.HTTP_200_OK

    # 嘗試將 B 設為 A 的主管 -> 應攔截循環
    res_mgr_cycle = client.post(
        f"/api/v1/hr/employees/{emp_a.id}/manager",
        json={"manager_id": emp_b.id, "relation_type": "DIRECT", "effective_from": "2026-01-01"},
        headers=headers,
    )
    assert res_mgr_cycle.status_code == status.HTTP_400_BAD_REQUEST
    assert res_mgr_cycle.json()["error"]["code"] == "MANAGER_CYCLE_DETECTED"


def test_organization_update_and_effective_dates(client, hr_env, db_session):
    """
    測試 2.1：部門組織編輯與有效/失效日期驗證
    - 編輯部門名稱、代碼、層級
    - 設定有效起始日與失效截止日
    - 驗證日期區間檢核 (effective_date <= expiry_date)
    - 驗證不能把自己設為上級
    - 驗證代碼重複攔截
    - 驗證停用狀態
    """
    headers = get_auth_headers(client)

    # 1. 成功建立具有有效起始日與失效截止日的部門
    create_res = client.post(
        "/api/v1/hr/organizations",
        json={
            "id": "ORG-QA",
            "company_id": "ETJ-TW",
            "code": "QA",
            "name": "品質保證部",
            "parent_id": "ORG-RD",
            "level": "DEPARTMENT",
            "effective_date": "2026-01-01",
            "expiry_date": "2026-12-31",
        },
        headers=headers,
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    data = create_res.json()
    assert data["effective_date"] == "2026-01-01"
    assert data["expiry_date"] == "2026-12-31"
    assert data["is_active"] is True

    # 2. 編輯部門名稱、代碼，並延長失效日期與修改層級至 CENTER
    update_res = client.put(
        "/api/v1/hr/organizations/ORG-QA",
        json={
            "code": "QA-NEW",
            "name": "品質保證中心",
            "parent_id": "ORG-RD",
            "level": "CENTER",
            "effective_date": "2026-01-01",
            "expiry_date": "2027-12-31",
            "is_active": True,
        },
        headers=headers,
    )
    assert update_res.status_code == status.HTTP_200_OK
    updated_data = update_res.json()
    assert updated_data["code"] == "QA-NEW"
    assert updated_data["name"] == "品質保證中心"
    assert updated_data["level"] == "CENTER"
    assert updated_data["expiry_date"] == "2027-12-31"

    # 2.1 測試更新為最高決策階層 (CHAIRMAN)
    chairman_res = client.put(
        "/api/v1/hr/organizations/ORG-QA",
        json={
            "level": "CHAIRMAN",
        },
        headers=headers,
    )
    assert chairman_res.status_code == status.HTTP_200_OK
    assert chairman_res.json()["level"] == "CHAIRMAN"

    # 3. 測試反向日期檢核 (effective_date > expiry_date) -> 應回傳 400
    invalid_date_res = client.put(
        "/api/v1/hr/organizations/ORG-QA",
        json={
            "code": "QA-NEW",
            "name": "品質保證中心",
            "parent_id": "ORG-RD",
            "level": "DIVISION",
            "effective_date": "2028-01-01",
            "expiry_date": "2027-12-31",
            "is_active": True,
        },
        headers=headers,
    )
    assert invalid_date_res.status_code == status.HTTP_400_BAD_REQUEST
    assert invalid_date_res.json()["error"]["code"] == "INVALID_DATE_RANGE"

    # 4. 測試自己不能是自己的上級 (parent_id == id) -> 應回傳 400
    self_parent_res = client.put(
        "/api/v1/hr/organizations/ORG-QA",
        json={
            "code": "QA-NEW",
            "name": "品質保證中心",
            "parent_id": "ORG-QA",
            "level": "DIVISION",
        },
        headers=headers,
    )
    assert self_parent_res.status_code == status.HTTP_400_BAD_REQUEST
    assert self_parent_res.json()["error"]["code"] == "INVALID_PARENT_ORG"

    # 5. 測試代碼衝突 -> 應回傳 400
    code_conflict_res = client.put(
        "/api/v1/hr/organizations/ORG-QA",
        json={
            "code": "RD",  # RD 已存在
            "name": "衝突研發",
        },
        headers=headers,
    )
    assert code_conflict_res.status_code == status.HTTP_400_BAD_REQUEST
    assert code_conflict_res.json()["error"]["code"] == "ORG_CODE_EXISTS"

    # 6. 測試停用部門 (is_active = False)
    deactivate_res = client.put(
        "/api/v1/hr/organizations/ORG-QA",
        json={
            "code": "QA-NEW",
            "name": "品質保證中心",
            "is_active": False,
        },
        headers=headers,
    )
    assert deactivate_res.status_code == status.HTTP_200_OK
    assert deactivate_res.json()["is_active"] is False


def test_employee_transfer_and_version_increment(client, hr_env, db_session):
    """
    測試 3：員工調職作業與版本號樂觀鎖
    - 更新所屬部門
    - 版本號 version 自增
    - 異動歷史 TRANSFER 留存
    """
    headers = get_auth_headers(client)

    shift_a = Shift(id="SHIFT-A", company_id="ETJ-TW", code="SA", name="早班", work_start_time="08:00", work_end_time="17:00")
    shift_b = Shift(id="SHIFT-B", company_id="ETJ-TW", code="SB", name="晚班", work_start_time="13:00", work_end_time="22:00")
    db_session.add_all([shift_a, shift_b])
    db_session.commit()

    emp = Employee(
        employee_no="TW301",
        company_id="ETJ-TW",
        organization_id="ORG-RD",
        full_name="張專案",
        email="chang@etron.com",
        hire_date=date(2026, 2, 1),
        default_shift_id="SHIFT-A",
    )
    db_session.add(emp)
    db_session.commit()
    old_version = emp.version

    # 執行調職至 ORG-SW，並調整班別至 SHIFT-B
    transfer_payload = {
        "new_organization_id": "ORG-SW",
        "new_default_shift_id": "SHIFT-B",
        "effective_date": "2026-06-01",
        "notes": "專案轉調軟體開發部並改派晚班",
    }
    res = client.post(f"/api/v1/hr/employees/{emp.id}/transfer", json=transfer_payload, headers=headers)
    assert res.status_code == status.HTTP_200_OK

    # 查詢單一員工詳情
    detail_res = client.get(f"/api/v1/hr/employees/{emp.id}")
    assert detail_res.status_code == status.HTTP_200_OK
    detail = detail_res.json()
    assert detail["organization_id"] == "ORG-SW"
    assert detail["default_shift_id"] == "SHIFT-B"
    assert detail["version"] == old_version + 1

    # 查詢異動歷程清單
    changes_res = client.get(f"/api/v1/hr/employees/{emp.id}/changes")
    assert changes_res.status_code == status.HTTP_200_OK
    changes = changes_res.json()
    assert len(changes) >= 1
    assert changes[0]["change_type"] == "TRANSFER"
    assert changes[0]["before_organization_id"] == "ORG-RD"
    assert changes[0]["after_organization_id"] == "ORG-SW"
    assert "變更班別" in changes[0]["notes"]


def test_employee_resignation_and_session_revocation(client, hr_env, db_session):
    """
    測試 4：員工離職作業與資安連動
    - 員工在職並於獨立瀏覽器 client (emp_client) 登入取得有效 Session
    - 人事管理員使用 admin_client 執行離職作業
    - 驗證在職狀態切換為 RESIGNED，記錄離職日期
    - 驗證關聯 User 帳號 is_active 變更為 False
    - 驗證既有 Session 立即被標記為 is_revoked = True
    - 離職員工在 emp_client 再次發送請求遭 403 阻擋
    """
    from fastapi.testclient import TestClient
    from app.main import app as fastapi_app

    admin_headers = get_auth_headers(client)

    # 1. 人事管理員建立員工並開通帳號
    onboard_payload = {
        "employee_no": "TW401",
        "company_id": "ETJ-TW",
        "organization_id": "ORG-SW",
        "full_name": "即將離職員工",
        "email": "leaving@etron.com",
        "hire_date": "2026-01-01",
        "create_user_account": True,
        "initial_password": "Password789!",
    }
    emp_res = client.post("/api/v1/hr/employees", json=onboard_payload, headers=admin_headers)
    assert emp_res.status_code == status.HTTP_201_CREATED
    emp_id = emp_res.json()["id"]

    # 2. 該員工在獨立客戶端 emp_client 登入建立 Session
    emp_client = TestClient(fastapi_app)
    user_login_res = emp_client.post("/api/v1/auth/login", json={"username": "TW401", "password": "Password789!"})
    assert user_login_res.status_code == status.HTTP_200_OK

    # 驗證該員工當前能正常呼叫 GET /api/v1/auth/me
    me_res = emp_client.get("/api/v1/auth/me")
    assert me_res.status_code == status.HTTP_200_OK
    assert me_res.json()["username"] == "TW401"

    # 3. 人事管理員在 client (admin_client) 執行離職
    resign_payload = {
        "resign_date": "2026-10-31",
        "notes": "個人生涯規劃請辭",
    }
    resign_res = client.post(f"/api/v1/hr/employees/{emp_id}/resign", json=resign_payload, headers=admin_headers)
    assert resign_res.status_code == status.HTTP_200_OK
    resign_data = resign_res.json()
    assert resign_data["employee_status"] == "RESIGNED"
    assert resign_data["user_account_disabled"] is True
    assert resign_data["revoked_sessions_count"] >= 1

    # 4. 驗證該員工在 emp_client 的 Session 立即失效，存取遭 401 阻擋 (SESSION_REVOKED)
    revoked_me_res = emp_client.get("/api/v1/auth/me")
    assert revoked_me_res.status_code == status.HTTP_401_UNAUTHORIZED
    assert revoked_me_res.json()["error"]["code"] == "SESSION_REVOKED"


def test_shifts_calendars_and_leave_types_master(client, hr_env):
    """
    測試 5：班別、工作日曆與假別主檔維護與查詢
    """
    headers = get_auth_headers(client)

    # 1. 建立班別
    shift_res = client.post(
        "/api/v1/hr/shifts",
        json={
            "id": "SHIFT-TW-NORMAL",
            "company_id": "ETJ-TW",
            "code": "TW-NORMAL",
            "name": "台北常規日班 (8H)",
            "work_start_time": "09:00",
            "work_end_time": "18:00",
            "break_minutes": 60,
            "daily_standard_minutes": 480,
            "is_overnight": False,
            "timezone": "Asia/Taipei",
        },
        headers=headers,
    )
    assert shift_res.status_code == status.HTTP_201_CREATED
    assert shift_res.json()["timezone"] == "Asia/Taipei"

    # 1.1 編輯/調整班別設定 (PUT /shifts/{shift_id})
    shift_update_res = client.put(
        "/api/v1/hr/shifts/SHIFT-TW-NORMAL",
        json={
            "name": "台北常規日班 (調整工時與彈性起訖)",
            "work_start_time": "09:30",
            "work_end_time": "18:30",
            "break_minutes": 60,
            "daily_standard_minutes": 480,
            "timezone": "Asia/Tokyo",
        },
        headers=headers,
    )
    assert shift_update_res.status_code == status.HTTP_200_OK
    updated_shift = shift_update_res.json()
    assert updated_shift["name"] == "台北常規日班 (調整工時與彈性起訖)"
    assert updated_shift["work_start_time"] == "09:30"
    assert updated_shift["work_end_time"] == "18:30"
    assert updated_shift["timezone"] == "Asia/Tokyo"

    shifts_list = client.get("/api/v1/hr/shifts?company_id=ETJ-TW")
    assert shifts_list.status_code == status.HTTP_200_OK
    assert len(shifts_list.json()) >= 1
    assert any(s["work_start_time"] == "09:30" and s["timezone"] == "Asia/Tokyo" for s in shifts_list.json())

    # 2. 建立工作日曆
    cal_res = client.post(
        "/api/v1/hr/calendar-days",
        json={
            "company_id": "ETJ-TW",
            "calendar_date": "2026-10-25",
            "is_working_day": False,
            "holiday_name": "台灣光復節紀念",
            "day_type": "NATIONAL_HOLIDAY",
        },
        headers=headers,
    )
    assert cal_res.status_code == status.HTTP_201_CREATED

    cals_list = client.get("/api/v1/hr/calendar-days?company_id=ETJ-TW&start_date=2026-10-01&end_date=2026-10-31")
    assert cals_list.status_code == status.HTTP_200_OK
    assert any(c["calendar_date"] == "2026-10-25" for c in cals_list.json())

    # 3. 建立假別
    lt_res = client.post(
        "/api/v1/hr/leave-types",
        json={
            "id": "LT-SICK-TW",
            "company_id": "ETJ-TW",
            "code": "SICK",
            "name": "普通傷病假",
            "unit": "MINUTES",
            "requires_attachment": True,
            "is_paid": True,
        },
        headers=headers,
    )
    assert lt_res.status_code == status.HTTP_201_CREATED

    lts_list = client.get("/api/v1/hr/leave-types?company_id=ETJ-TW")
    assert lts_list.status_code == status.HTTP_200_OK
    assert any(lt["code"] == "SICK" for lt in lts_list.json())


def test_leave_ledger_quota_summary_and_audit_entries(client, hr_env, db_session):
    """
    測試 6：假額發放、不可變流水帳本查詢與可用天數彙總 (480 分鐘標準日換算)
    """
    headers = get_auth_headers(client)

    # 建立員工與假別
    emp = Employee(employee_no="TW501", company_id="ETJ-TW", organization_id="ORG-SW", full_name="假額測試者", email="leave_tester@etron.com", hire_date=date(2026, 1, 1))
    lt_annual = LeaveType(id="LT-ANNUAL-TEST", company_id="ETJ-TW", code="ANNUAL_TEST", name="年度特休", unit="MINUTES", requires_attachment=False, is_paid=True)
    db_session.add_all([emp, lt_annual])
    db_session.commit()

    # 發放特休 3 天 = 1440 分鐘 (有效期間 2026-01-01 ~ 2026-12-31)
    grant_payload_1 = {
        "company_id": "ETJ-TW",
        "employee_id": emp.id,
        "leave_type_id": lt_annual.id,
        "amount_minutes": 1440,
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "notes": "2026 年度特休發放 (3天)",
    }
    g1_res = client.post("/api/v1/hr/leave-ledger/grant", json=grant_payload_1, headers=headers)
    assert g1_res.status_code == status.HTTP_201_CREATED

    # 再次發放特休 4.5 天 = 2160 分鐘
    grant_payload_2 = {
        "company_id": "ETJ-TW",
        "employee_id": emp.id,
        "leave_type_id": lt_annual.id,
        "amount_minutes": 2160,
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "notes": "績效獎勵給假 (4.5天)",
    }
    g2_res = client.post("/api/v1/hr/leave-ledger/grant", json=grant_payload_2, headers=headers)
    assert g2_res.status_code == status.HTTP_201_CREATED

    # 查詢單一假別餘額
    balance_res = client.get(f"/api/v1/hr/leave-ledger/balance?employee_id={emp.id}&leave_type_id={lt_annual.id}&as_of_date=2026-07-01")
    assert balance_res.status_code == status.HTTP_200_OK
    b_data = balance_res.json()
    assert b_data["available_minutes"] == 1440 + 2160  # 3600 分鐘
    assert b_data["available_days"] == 7.5             # 3600 / 480 = 7.5 天

    # 查詢全假別可用天數彙總 (Summary)
    summary_res = client.get(f"/api/v1/hr/leave-ledger/summary?employee_id={emp.id}&as_of_date=2026-07-01")
    assert summary_res.status_code == status.HTTP_200_OK
    s_list = summary_res.json()
    annual_summary = next(item for item in s_list if item["leave_type_id"] == lt_annual.id)
    assert annual_summary["available_minutes"] == 3600
    assert annual_summary["available_days"] == 7.5

    # 查詢不可變帳本流水紀錄 (Entries)
    entries_res = client.get(f"/api/v1/hr/leave-ledger/entries?employee_id={emp.id}")
    assert entries_res.status_code == status.HTTP_200_OK
    entries = entries_res.json()
    assert len(entries) == 2
    assert entries[0]["entry_type"] == "GRANT"
    assert entries[0]["amount_minutes"] == 2160
    assert entries[1]["amount_minutes"] == 1440


def test_employee_expanded_fields_and_masking(client, db_session, hr_env):
    """驗證員工完整欄位建檔、個資動態遮罩與資料更新"""
    headers = get_auth_headers(client)

    payload = {
        "employee_no": "EMP-FULL-01",
        "company_id": "ETJ-TW",
        "organization_id": "ORG-SW",
        "full_name": "王大明",
        "english_name": "David Wang",
        "national_id": "A123456789",
        "birth_date": "1992-05-20",
        "gender": "MALE",
        "nationality": "TW",
        "marital_status": "MARRIED",
        "email": "david.wang@etron.com",
        "personal_email": "david.personal@example.com",
        "mobile_phone": "0912-345-678",
        "residential_address": "台北市信義區信義路五段7號",
        "permanent_address": "高雄市苓雅區四維三路2號",
        "emergency_contact_name": "陳小美",
        "emergency_contact_relationship": "配偶",
        "emergency_contact_phone": "0987-654-321",
        "job_title": "資深韌體工程師",
        "job_grade": "E3",
        "employment_type": "REGULAR",
        "hire_date": "2026-03-01",
        "probation_end_date": "2026-06-01",
        "create_user_account": False,
    }

    create_res = client.post("/api/v1/hr/employees", json=payload, headers=headers)
    assert create_res.status_code == status.HTTP_201_CREATED
    emp_data = create_res.json()
    emp_id = emp_data["id"]

    # 1. 驗證詳情查詢（敏感個資動態遮罩）
    detail_res = client.get(f"/api/v1/hr/employees/{emp_id}", headers=headers)
    assert detail_res.status_code == status.HTTP_200_OK
    detail = detail_res.json()

    assert detail["full_name"] == "王大明"
    assert detail["english_name"] == "David Wang"
    assert detail["national_id"] == "A12****789"  # 身分證遮罩防護
    assert detail["birth_date"] == "1992-05-20"
    assert detail["gender"] == "MALE"
    assert detail["marital_status"] == "MARRIED"
    assert detail["personal_email"] == "david.personal@example.com"
    assert detail["mobile_phone"] == "0912-345-678"
    assert detail["residential_address"] == "台北市信義區信義路五段7號"
    assert detail["permanent_address"] == "高雄市苓雅區四維三路2號"
    assert detail["emergency_contact_name"] == "陳小美"
    assert detail["emergency_contact_relationship"] == "配偶"
    assert detail["emergency_contact_phone"] == "0987-654-321"
    assert detail["job_title"] == "資深韌體工程師"
    assert detail["job_grade"] == "E3"
    assert detail["employment_type"] == "REGULAR"
    assert detail["probation_end_date"] == "2026-06-01"

    # 2. 驗證更新員工基本資料
    update_payload = {
        "job_title": "首席架構師",
        "job_grade": "E4",
        "mobile_phone": "0900-111-222",
        "emergency_contact_phone": "0988-777-666",
    }
    update_res = client.put(f"/api/v1/hr/employees/{emp_id}", json=update_payload, headers=headers)
    assert update_res.status_code == status.HTTP_200_OK
    updated = update_res.json()
    assert updated["job_title"] == "首席架構師"
    assert updated["job_grade"] == "E4"
    assert updated["mobile_phone"] == "0900-111-222"
    assert updated["emergency_contact_phone"] == "0988-777-666"
    assert updated["version"] == 2  # 樂觀鎖版本號遞增


def test_company_crud_and_expansion(client, db_session, hr_env):
    """驗證公司基本資料擴充欄位維護、更新與查詢"""
    headers = get_auth_headers(client)

    # 1. 查詢既有公司詳情
    get_res = client.get("/api/v1/hr/companies/ETJ-TW", headers=headers)
    assert get_res.status_code == status.HTTP_200_OK
    data = get_res.json()
    assert data["id"] == "ETJ-TW"
    assert data["name"] == "鈺創台灣總部"

    # 2. 更新公司基本資料 (統編、代表人、地址、電話)
    update_payload = {
        "name": "鈺創台灣科技股份有限公司",
        "tax_id": "80123456",
        "representative_name": "盧超群",
        "registered_address": "新竹科學園區創新一路8號",
        "contact_phone": "+886-3-578-2345",
        "default_timezone": "Asia/Taipei",
        "default_currency": "TWD",
        "is_active": True,
    }
    put_res = client.put("/api/v1/hr/companies/ETJ-TW", json=update_payload, headers=headers)
    assert put_res.status_code == status.HTTP_200_OK
    updated = put_res.json()
    assert updated["name"] == "鈺創台灣科技股份有限公司"
    assert updated["tax_id"] == "80123456"
    assert updated["representative_name"] == "盧超群"
    assert updated["registered_address"] == "新竹科學園區創新一路8號"
    assert updated["contact_phone"] == "+886-3-578-2345"

    # 3. 建立新子公司 / 辦事處
    create_payload = {
        "id": "ETJ-US",
        "name": "Etron USA Inc.",
        "tax_id": "EIN-987654321",
        "representative_name": "David Smith",
        "registered_address": "San Jose, CA, USA",
        "contact_phone": "+1-408-555-0199",
        "default_timezone": "America/Los_Angeles",
        "default_currency": "USD",
    }
    create_res = client.post("/api/v1/hr/companies", json=create_payload, headers=headers)
    assert create_res.status_code == status.HTTP_201_CREATED
    created = create_res.json()
    assert created["id"] == "ETJ-US"
    assert created["default_currency"] == "USD"


