import pytest
from fastapi import status
from sqlalchemy import select
from app.core.security import hash_password, verify_password
from app.models.auth import User, Role, Permission, RolePermission, UserRole, UserScope, Session as UserSession


@pytest.fixture
def seed_auth_data(db_session):
    """預先植入測試用使用者、角色、權限與公司資料範圍"""
    # 建立權限
    perm1 = Permission(code="leave.create", name="申請請假", module="LEAVE")
    perm2 = Permission(code="hr.employee.manage", name="員工與帳號管理", module="HR")
    perm3 = Permission(code="payment.bank_account.view", name="檢視銀行帳號", module="FINANCE")
    db_session.add_all([perm1, perm2, perm3])

    # 建立角色
    admin_role = Role(id="ADMIN", name="系統管理員")
    hr_role = Role(id="HR_MANAGER", name="人事主管")
    emp_role = Role(id="EMPLOYEE", name="一般員工")
    db_session.add_all([admin_role, hr_role, emp_role])
    db_session.commit()

    # 綁定角色權限
    rp1 = RolePermission(role_id="HR_MANAGER", permission_code="hr.employee.manage")
    rp2 = RolePermission(role_id="EMPLOYEE", permission_code="leave.create")
    db_session.add_all([rp1, rp2])

    # 建立 2 名使用者 (1位屬於 ETJ-TW，1位屬於 ETJ-JP)
    u_tw = User(
        username="user_tw",
        email="tw@etron.com",
        hashed_password=hash_password("Password123!"),
        display_name="台灣主管",
        primary_company_id="ETJ-TW",
        is_active=True,
        is_first_login=True,
    )
    u_jp = User(
        username="user_jp",
        email="jp@etron.com",
        hashed_password=hash_password("Password456!"),
        display_name="福岡同仁",
        primary_company_id="ETJ-JP",
        is_active=True,
        is_first_login=False,
    )
    db_session.add_all([u_tw, u_jp])
    db_session.commit()

    # 賦予角色
    ur_tw = UserRole(user_id=u_tw.id, role_id="HR_MANAGER", company_id="ETJ-TW")
    ur_jp = UserRole(user_id=u_jp.id, role_id="EMPLOYEE", company_id="ETJ-JP")
    db_session.add_all([ur_tw, ur_jp])

    # 賦予公司資料範圍
    scope_tw = UserScope(user_id=u_tw.id, company_id="ETJ-TW", scope_type="COMPANY")
    scope_jp = UserScope(user_id=u_jp.id, company_id="ETJ-JP", scope_type="COMPANY")
    db_session.add_all([scope_tw, scope_jp])
    db_session.commit()

    return {"user_tw": u_tw, "user_jp": u_jp}


def test_login_and_logout_flow(client, seed_auth_data):
    """驗證登入成功寫入 HttpOnly Session Cookie、取得 CSRF Token、以及登出立即撤銷"""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "user_tw", "password": "Password123!"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    data = login_res.json()
    assert data["status"] == "success"
    assert data["is_first_login"] is True
    assert "csrf_token" in data
    csrf_token = data["csrf_token"]

    # 驗證 Cookie 包含 etj_session
    cookies = login_res.cookies
    assert "etj_session" in cookies

    # 測試 /auth/me 端點
    me_res = client.get("/api/v1/auth/me")
    assert me_res.status_code == status.HTTP_200_OK
    me_data = me_res.json()
    assert me_data["username"] == "user_tw"
    assert "hr.employee.manage" in me_data["permissions"]

    # 測試登出 (需帶 X-CSRF-Token)
    logout_res = client.post(
        "/api/v1/auth/logout",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logout_res.status_code == status.HTTP_200_OK

    # 登出後再次呼叫 /auth/me 應遭拒絕 (401 UNAUTHORIZED)
    subsequent_res = client.get("/api/v1/auth/me")
    assert subsequent_res.status_code == status.HTTP_401_UNAUTHORIZED


def test_first_time_password_initialization(client, seed_auth_data):
    """驗證首次登入設定新密碼成功，且 is_first_login 變更為 False"""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "user_tw", "password": "Password123!"},
    )
    csrf_token = login_res.json()["csrf_token"]

    # 執行首次密碼設定
    set_pwd_res = client.post(
        "/api/v1/auth/first-time-password",
        json={"new_password": "NewSecretPassword999!"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert set_pwd_res.status_code == status.HTTP_200_OK

    # 再次查詢 profile，確認 is_first_login 為 False
    me_res = client.get("/api/v1/auth/me")
    assert me_res.json()["is_first_login"] is False


def test_user_suspension_immediate_session_revocation(client, seed_auth_data, db_session):
    """驗證帳號被停用後，所有正在進行中的工作階段立即失效 (403 USER_INACTIVE)"""
    # user_jp 先登入
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "user_jp", "password": "Password456!"},
    )
    assert login_res.status_code == status.HTTP_200_OK

    # 由系統管理員停用 user_jp
    target_user = seed_auth_data["user_jp"]
    target_user.is_active = False
    db_session.commit()

    # user_jp 嘗試存取任何受保護端點，應被立即阻擋
    blocked_res = client.get("/api/v1/auth/me")
    assert blocked_res.status_code == status.HTTP_403_FORBIDDEN
    assert blocked_res.json()["error"]["code"] == "USER_INACTIVE"


def test_cross_company_idor_forbidden(client, seed_auth_data):
    """驗證跨公司資料存取拒絕 (Cross-company IDOR Protection)"""
    # 登入 ETJ-TW 使用者
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "user_tw", "password": "Password123!"},
    )
    assert login_res.status_code == status.HTTP_200_OK

    # 存取本公司 ETJ-TW 資料 -> 允許存取 (200 OK)
    allowed_res = client.get("/api/v1/users/companies/ETJ-TW/sensitive-data")
    assert allowed_res.status_code == status.HTTP_200_OK

    # 嘗試橫向存取福岡支社 ETJ-JP 敏感資料 -> 必須嚴格拒絕 (403 CROSS_COMPANY_FORBIDDEN)
    forbidden_res = client.get("/api/v1/users/companies/ETJ-JP/sensitive-data")
    assert forbidden_res.status_code == status.HTTP_403_FORBIDDEN
    assert forbidden_res.json()["error"]["code"] == "CROSS_COMPANY_FORBIDDEN"


def test_csrf_protection_enforcement(client, seed_auth_data):
    """驗證非安全 HTTP 寫入請求若缺漏或偽造 CSRF Token 將被拒絕 (403 CSRF_VERIFICATION_FAILED)"""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "user_tw", "password": "Password123!"},
    )
    assert login_res.status_code == status.HTTP_200_OK

    # POST 寫入請求缺少 X-CSRF-Token
    failed_res = client.post(
        "/api/v1/auth/first-time-password",
        json={"new_password": "AttackPassword999!"},
    )
    assert failed_res.status_code == status.HTTP_403_FORBIDDEN
    assert failed_res.json()["error"]["code"] == "CSRF_VERIFICATION_FAILED"


def test_multi_identifier_login(client, seed_auth_data):
    """驗證多識別碼登入相容性：支援工號/帳號、完整 Email 以及 Email 前綴登入"""
    # 1. 使用者名稱 (工號 / 帳號) 登入
    res_username = client.post(
        "/api/v1/auth/login",
        json={"username": "user_tw", "password": "Password123!"},
    )
    assert res_username.status_code == status.HTTP_200_OK

    # 2. 完整電子信箱登入
    res_email = client.post(
        "/api/v1/auth/login",
        json={"username": "tw@etron.com", "password": "Password123!"},
    )
    assert res_email.status_code == status.HTTP_200_OK

    # 3. 電子信箱帳號前綴 (如 cswu, tw) 登入
    res_prefix = client.post(
        "/api/v1/auth/login",
        json={"username": "tw", "password": "Password123!"},
    )
    assert res_prefix.status_code == status.HTTP_200_OK


def test_assign_user_roles_payload_compatibility(client, seed_auth_data, db_session):
    """驗證使用者角色分配 API 之容錯與相容性：支援標準 role_ids、相容 role_names 以及自動補足生效公司"""
    u = seed_auth_data["user_tw"]

    # 先登入取得 CSRF token 與工作階段 cookie
    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "user_tw", "password": "Password123!"},
    )
    assert login_res.status_code == status.HTTP_200_OK
    csrf_token = login_res.json()["csrf_token"]
    headers = {"X-CSRF-Token": csrf_token}

    # 1. 前端相容情境：傳入 role_names 且未帶 company_id
    res_compat = client.put(
        f"/api/v1/users/{u.id}/roles",
        json={"role_names": ["EMPLOYEE"]},
        headers=headers,
    )
    assert res_compat.status_code == status.HTTP_200_OK
    assert res_compat.json()["status"] == "success"

    # 驗證角色已改為 EMPLOYEE
    roles = db_session.execute(
        select(UserRole.role_id).where(UserRole.user_id == u.id)
    ).scalars().all()
    assert "EMPLOYEE" in roles
    assert "HR_MANAGER" not in roles

    # 2. 標準情境：傳入 company_id 與 role_ids
    res_std = client.put(
        f"/api/v1/users/{u.id}/roles",
        json={"company_id": "ETJ-TW", "role_ids": ["ADMIN", "HR_MANAGER"]},
        headers=headers,
    )
    assert res_std.status_code == status.HTTP_200_OK
    assert res_std.json()["status"] == "success"

    roles_updated = db_session.execute(
        select(UserRole.role_id).where(UserRole.user_id == u.id)
    ).scalars().all()
    assert "ADMIN" in roles_updated
    assert "HR_MANAGER" in roles_updated


