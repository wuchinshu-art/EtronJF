import pytest
from datetime import date, timedelta
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.database import get_db
from app.core.hr_rules import LeaveEntitlementService
from app.models.hr import Company, Employee, LeaveType, LeaveLedger
from app.models.auth import User


def test_taiwan_and_japan_statutory_seniority_entitlement():
    """驗證台灣與日本法定年資特休階梯演算法"""
    # 台灣 (TW): 2026-10-23
    today = date(2026, 10, 23)

    # 1. 未滿 6 個月 -> 0 天
    res_4m = LeaveEntitlementService.calculate_entitlement(date(2026, 6, 23), today, country="TW")
    assert res_4m["entitled_days"] == 0.0

    # 2. 滿 6 個月未滿 1 年 -> 3 天 (1440 分鐘)
    res_6m = LeaveEntitlementService.calculate_entitlement(date(2026, 4, 1), today, country="TW")
    assert res_6m["entitled_days"] == 3.0
    assert res_6m["entitled_minutes"] == 1440

    # 3. 滿 1 年 -> 7 天
    res_1y = LeaveEntitlementService.calculate_entitlement(date(2025, 10, 20), today, country="TW")
    assert res_1y["entitled_days"] == 7.0

    # 4. 滿 2 年 -> 10 天
    res_2y = LeaveEntitlementService.calculate_entitlement(date(2024, 10, 20), today, country="TW")
    assert res_2y["entitled_days"] == 10.0

    # 5. 滿 3 年 -> 14 天
    res_3y = LeaveEntitlementService.calculate_entitlement(date(2023, 10, 20), today, country="TW")
    assert res_3y["entitled_days"] == 14.0

    # 6. 滿 5 年 -> 15 天
    res_5y = LeaveEntitlementService.calculate_entitlement(date(2021, 10, 20), today, country="TW")
    assert res_5y["entitled_days"] == 15.0

    # 7. 滿 10 年 -> 16 天
    res_10y = LeaveEntitlementService.calculate_entitlement(date(2016, 10, 20), today, country="TW")
    assert res_10y["entitled_days"] == 16.0

    # 日本 (JP) 年次有給休暇階梯
    # 滿 6 個月 -> 10 天
    res_jp_6m = LeaveEntitlementService.calculate_entitlement(date(2026, 4, 1), today, country="JP")
    assert res_jp_6m["entitled_days"] == 10.0

    # 滿 1.5 年 -> 11 天
    res_jp_18m = LeaveEntitlementService.calculate_entitlement(date(2025, 4, 1), today, country="JP")
    assert res_jp_18m["entitled_days"] == 11.0

    # 滿 6.5 年以上 -> 20 天
    res_jp_7y = LeaveEntitlementService.calculate_entitlement(date(2019, 1, 1), today, country="JP")
    assert res_jp_7y["entitled_days"] == 20.0


from tests.test_hr_full_system import hr_env, get_auth_headers


def test_leave_types_management_and_entitlement_api(client: TestClient, hr_env, db_session: Session):
    """驗證假別新增/編輯與年資特休試算發放 API"""
    headers = get_auth_headers(client)
    company_id = "ETJ-TW"

    # 1. 建立全新假別 (如產假 MATERNITY)
    lt_id = "TEST-MATERNITY"
    lt_res = client.post(
        "/api/v1/hr/leave-types",
        json={
            "id": lt_id,
            "company_id": company_id,
            "code": "MATERNITY",
            "name": "產假 (Maternity Leave)",
            "unit": "DAYS",
            "requires_attachment": True,
            "is_paid": True,
        },
        headers=headers,
    )
    assert lt_res.status_code == 201
    lt_data = lt_res.json()
    assert lt_data["code"] == "MATERNITY"
    assert lt_data["requires_attachment"] is True

    # 2. 編輯假別 (更改名稱與備註)
    update_res = client.put(
        f"/api/v1/hr/leave-types/{lt_id}",
        json={
            "name": "全薪產假 (Full-Paid Maternity Leave)",
            "requires_attachment": True,
            "is_paid": True,
        },
        headers=headers,
    )
    assert update_res.status_code == 200
    assert update_res.json()["name"] == "全薪產假 (Full-Paid Maternity Leave)"

    # 3. 呼叫年資特休試算 API
    calc_res = client.get(f"/api/v1/hr/leave-entitlement/calculate?company_id={company_id}", headers=headers)
    assert calc_res.status_code == 200
    preview_list = calc_res.json()
    assert isinstance(preview_list, list)

    # 建立一個測試員工以驗證計算與發放
    from app.models.hr import Person, Employee
    person = Person(
        id="PM-TEST-LEAVE-01",
        full_name="測試特休人員",
        personal_email="test_leave_emp@etron.com",
    )
    db_session.add(person)
    db_session.commit()

    emp = Employee(
        id="EMP-TEST-LEAVE-01",
        person_id=person.id,
        company_id=company_id,
        organization_id=hr_env["dept_sw"].id,
        employee_no="TW-TEST-001",
        full_name="測試特休人員",
        email="test_leave_emp@etron.com",
        hire_date=date(2023, 1, 1),
        status="ACTIVE",
    )
    annual_lt = LeaveType(
        id="LT-TEST-ANNUAL",
        company_id=company_id,
        code="ANNUAL",
        name="特別休假 (Annual Leave)",
        unit="DAYS",
        requires_attachment=False,
        is_paid=True,
    )
    db_session.add_all([emp, annual_lt])
    db_session.commit()

    calc_res2 = client.get(f"/api/v1/hr/leave-entitlement/calculate?company_id={company_id}", headers=headers)
    assert calc_res2.status_code == 200
    previews = calc_res2.json()
    assert len(previews) >= 1
    found = next((p for p in previews if p["employee_id"] == emp.id), None)
    assert found is not None
    assert found["entitled_days"] > 0
    assert found["entitled_minutes"] > 0

    # 4. 批次發放特休假額入帳本
    batch_grant_res = client.post(
        "/api/v1/hr/leave-entitlement/grant-batch",
        json={
            "company_id": company_id,
            "grants": [
                {
                    "employee_id": emp.id,
                    "leave_type_id": annual_lt.id,
                    "amount_minutes": found["entitled_minutes"],
                    "valid_from": date.today().isoformat(),
                    "valid_to": (date.today() + timedelta(days=365)).isoformat(),
                    "notes": "法定特休批次核算核發測試",
                }
            ],
            "batch_notes": "年度法定特休測試核發",
        },
        headers=headers,
    )
    assert batch_grant_res.status_code == 200
    assert batch_grant_res.json()["granted_count"] == 1
