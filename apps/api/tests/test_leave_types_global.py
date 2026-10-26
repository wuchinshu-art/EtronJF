import pytest
from datetime import date
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.hr import Company, Organization, Employee, LeaveType, LeaveLedger
from app.models.auth import User, Role, UserRole, Permission, RolePermission, UserScope
from app.core.security import hash_password
from app.core.leave_service import LeaveService
from app.core.hr_rules import LeaveLedgerService


def get_auth_headers(client: TestClient, username: str = "global_hr_admin") -> dict:
    login_res = client.post("/api/v1/auth/login", json={"username": username, "password": "Password123!"})
    assert login_res.status_code == 200, login_res.text
    csrf_token = login_res.json()["csrf_token"]
    return {"X-CSRF-Token": csrf_token}


@pytest.fixture
def multi_company_env(db_session: Session):
    """建立跨國多公司與權限環境 (ETJ-TW 與 ETJ-JP)"""
    comp_tw = Company(id="ETJ-TW", name="台灣鈺創科技", default_currency="TWD", default_timezone="Asia/Taipei")
    comp_jp = Company(id="ETJ-JP", name="日本福岡分公司", default_currency="JPY", default_timezone="Asia/Tokyo")
    db_session.add_all([comp_tw, comp_jp])

    org_tw = Organization(id="ORG-TW-RD", company_id="ETJ-TW", code="RD", name="研發部")
    org_jp = Organization(id="ORG-JP-SALES", company_id="ETJ-JP", code="SALES", name="營業部")
    db_session.add_all([org_tw, org_jp])

    emp_tw = Employee(
        id="EMP-TW-001",
        employee_no="TW001",
        company_id="ETJ-TW",
        organization_id="ORG-TW-RD",
        full_name="陳台灣",
        email="tw001@etron.com",
        hire_date=date(2023, 1, 1),
    )
    emp_jp = Employee(
        id="EMP-JP-001",
        employee_no="JP001",
        company_id="ETJ-JP",
        organization_id="ORG-JP-SALES",
        full_name="佐藤日本",
        email="jp001@etron.com",
        hire_date=date(2023, 6, 1),
    )
    db_session.add_all([emp_tw, emp_jp])

    # 權限與管理員
    user = User(
        id="USR-HR-GLOBAL",
        username="global_hr_admin",
        email="hr_global@etron.com",
        display_name="全域HR管理員",
        primary_company_id="ETJ-TW",
        hashed_password=hash_password("Password123!"),
        is_active=True,
        is_first_login=False,
    )
    db_session.add(user)

    perm_hr = db_session.get(Permission, "hr.employee.manage")
    if not perm_hr:
        perm_hr = Permission(code="hr.employee.manage", name="HR管理", module="HR")
        db_session.add(perm_hr)

    role_hr = Role(id="ROLE-GLOBAL-HR", name="全域HR管理員", description="可管理全域假別")
    db_session.add(role_hr)

    db_session.add(RolePermission(role_id=role_hr.id, permission_code=perm_hr.code))
    db_session.add(UserRole(user_id=user.id, role_id=role_hr.id, company_id="ETJ-TW"))
    db_session.add(UserScope(user_id=user.id, company_id="ETJ-TW", scope_type="COMPANY"))

    db_session.commit()
    return {"comp_tw": comp_tw, "comp_jp": comp_jp, "emp_tw": emp_tw, "emp_jp": emp_jp, "user": user}


def test_leave_types_are_global_not_per_company(client: TestClient, multi_company_env, db_session: Session):
    """
    驗證假別為全組織通用（不分公司）：
    1. 建立假別時不需指定 company_id
    2. 全域 code 唯一性驗證
    3. 跨公司（ETJ-TW 與 ETJ-JP）均能查詢並共用同一個假種
    4. 跨公司假額發放與帳本扣抵皆能正常使用該全域假種
    5. 未使用假別可刪除，已使用假別受刪除保護
    """
    headers = get_auth_headers(client, "global_hr_admin")

    # 1. 建立全域通用假別 (不帶 company_id)
    create_payload = {
        "code": "VOLUNTEER",
        "name": "志工公益假",
        "unit": "ONE_DAY",
        "paid_type": "FULL",
        "requires_attachment": True,
    }
    res_create = client.post("/api/v1/hr/leave-types", json=create_payload, headers=headers)
    assert res_create.status_code == status.HTTP_201_CREATED, res_create.text
    created_data = res_create.json()
    assert created_data["code"] == "VOLUNTEER"
    assert created_data["name"] == "志工公益假"
    assert created_data["id"] == "LT-VOLUNTEER"
    assert created_data["company_id"] is None

    # 2. 測試全域 code 唯一性（即使指定特定公司試圖重複建立亦應被拒絕）
    duplicate_payload = {
        "company_id": "ETJ-JP",
        "code": "volunteer",  # 大小寫不拘
        "name": "日本志工假",
    }
    res_dup = client.post("/api/v1/hr/leave-types", json=duplicate_payload, headers=headers)
    assert res_dup.status_code == status.HTTP_400_BAD_REQUEST
    err_body = res_dup.json()
    err_msg = err_body.get("message") or err_body.get("error", {}).get("message", "")
    assert "已存在" in err_msg

    # 3. 測試查詢假別：不傳 company_id、傳 ETJ-TW 或傳 ETJ-JP 均能查得此全域假別
    res_list_all = client.get("/api/v1/hr/leave-types")
    assert res_list_all.status_code == status.HTTP_200_OK
    assert any(lt["code"] == "VOLUNTEER" for lt in res_list_all.json())

    res_list_tw = client.get("/api/v1/hr/leave-types?company_id=ETJ-TW")
    assert res_list_tw.status_code == status.HTTP_200_OK
    assert any(lt["code"] == "VOLUNTEER" for lt in res_list_tw.json())

    res_list_jp = client.get("/api/v1/hr/leave-types?company_id=ETJ-JP")
    assert res_list_jp.status_code == status.HTTP_200_OK
    assert any(lt["code"] == "VOLUNTEER" for lt in res_list_jp.json())

    # 4. 跨公司發放假額：台灣員工與日本員工皆使用 LT-VOLUNTEER
    emp_tw = multi_company_env["emp_tw"]
    emp_jp = multi_company_env["emp_jp"]

    # (a) 發放給台灣員工 (2天 = 960 分鐘)
    grant_tw_payload = {
        "company_id": "ETJ-TW",
        "employee_id": emp_tw.id,
        "leave_type_id": "LT-VOLUNTEER",
        "amount_minutes": 960,
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "notes": "台灣公益假發放",
    }
    res_g_tw = client.post("/api/v1/hr/leave-ledger/grant", json=grant_tw_payload, headers=headers)
    assert res_g_tw.status_code == status.HTTP_201_CREATED

    # (b) 發放給日本員工 (3天 = 1440 分鐘)
    grant_jp_payload = {
        "company_id": "ETJ-JP",
        "employee_id": emp_jp.id,
        "leave_type_id": "LT-VOLUNTEER",
        "amount_minutes": 1440,
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "notes": "日本ボランティア休暇",
    }
    res_g_jp = client.post("/api/v1/hr/leave-ledger/grant", json=grant_jp_payload, headers=headers)
    assert res_g_jp.status_code == status.HTTP_201_CREATED

    # (c) 檢查兩位員工假額彙總：皆能看到 LT-VOLUNTEER
    summary_tw = LeaveLedgerService.get_leave_quota_summary(db_session, emp_tw.id)
    v_tw = next((s for s in summary_tw if s["leave_type_code"] == "VOLUNTEER"), None)
    assert v_tw is not None
    assert v_tw["available_minutes"] == 960
    assert v_tw["available_days"] == 2.0

    summary_jp = LeaveLedgerService.get_leave_quota_summary(db_session, emp_jp.id)
    v_jp = next((s for s in summary_jp if s["leave_type_code"] == "VOLUNTEER"), None)
    assert v_jp is not None
    assert v_jp["available_minutes"] == 1440
    assert v_jp["available_days"] == 3.0

    # 5. 測試刪除防護
    # (a) LT-VOLUNTEER 已有帳本紀錄，不可刪除
    res_del_fail = client.delete("/api/v1/hr/leave-types/LT-VOLUNTEER", headers=headers)
    assert res_del_fail.status_code == status.HTTP_400_BAD_REQUEST
    del_err_body = res_del_fail.json()
    del_err_msg = del_err_body.get("message") or del_err_body.get("error", {}).get("message", "")
    assert "已有發放或使用" in del_err_msg

    # (b) 建立一個未使用的臨時假別
    res_tmp = client.post(
        "/api/v1/hr/leave-types",
        json={"code": "TEMP_TEST", "name": "臨時假別"},
        headers=headers,
    )
    assert res_tmp.status_code == status.HTTP_201_CREATED
    tmp_id = res_tmp.json()["id"]

    # (c) 未使用假別應可成功刪除
    res_del_ok = client.delete(f"/api/v1/hr/leave-types/{tmp_id}", headers=headers)
    assert res_del_ok.status_code == status.HTTP_200_OK
    assert db_session.get(LeaveType, tmp_id) is None
