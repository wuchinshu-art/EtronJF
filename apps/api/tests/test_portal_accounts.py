"""Portal 帳號管理：伺服器端權限、公司範圍與工作階段查詢／撤銷測試。"""
import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.security import hash_password
from app.main import app as fastapi_app
from app.models.auth import User, Role, Permission, RolePermission, UserRole, UserScope, Session as UserSession

PASSWORD = "Password123!"


def _user(db, username, company, roles, first_login=False):
    u = User(
        username=username,
        email=f"{username}@etron.example",
        hashed_password=hash_password(PASSWORD),
        display_name=username,
        primary_company_id=company,
        is_active=True,
        is_first_login=first_login,
    )
    db.add(u)
    db.flush()
    for r in roles:
        db.add(UserRole(user_id=u.id, role_id=r, company_id=company))
    db.add(UserScope(user_id=u.id, company_id=company, scope_type="COMPANY"))
    return u


@pytest.fixture
def seed(db_session):
    for code, module in [
        ("system.user.manage", "SYSTEM"),
        ("system.role.manage", "SYSTEM"),
        ("leave.create", "LEAVE"),
    ]:
        db_session.add(Permission(code=code, name=code, module=module))
    for rid in ["ADMIN", "USER_ADMIN", "GENERAL_USER"]:
        db_session.add(Role(id=rid, name=rid))
    db_session.flush()
    db_session.add(RolePermission(role_id="USER_ADMIN", permission_code="system.user.manage"))
    db_session.add(RolePermission(role_id="GENERAL_USER", permission_code="leave.create"))

    users = {
        "admin": _user(db_session, "root_admin", "ETJ-TW", ["ADMIN"]),
        "tw_mgr": _user(db_session, "tw_user_admin", "ETJ-TW", ["USER_ADMIN"]),
        "tw_emp": _user(db_session, "tw_employee", "ETJ-TW", ["GENERAL_USER"]),
        "jp_emp": _user(db_session, "jp_employee", "ETJ-JP", ["GENERAL_USER"]),
    }
    db_session.commit()
    return users


def _login(client, username):
    res = client.post("/api/v1/auth/login", json={"username": username, "password": PASSWORD})
    assert res.status_code == status.HTTP_200_OK, res.text
    return {"X-CSRF-Token": res.json()["csrf_token"]}


def _second_client():
    """以獨立 cookie jar 模擬另一台裝置 (共用相同 DB override)"""
    return TestClient(fastapi_app, raise_server_exceptions=False)


# ---------- 權限：未登入 / 無權限 / 公司範圍 ----------

@pytest.mark.parametrize(
    "method,path",
    [
        ("get", "/api/v1/users"),
        ("get", "/api/v1/users/meta/roles"),
        ("get", "/api/v1/users/meta/permissions"),
        ("get", "/api/v1/auth/sessions"),
    ],
)
def test_anonymous_requests_are_rejected(client, seed, method, path):
    res = getattr(client, method)(path)
    assert res.status_code == status.HTTP_401_UNAUTHORIZED


def test_general_user_cannot_manage_accounts(client, seed):
    headers = _login(client, "tw_employee")
    target = seed["jp_emp"].id

    assert client.get("/api/v1/users").status_code == 403
    assert client.get(f"/api/v1/users/{target}").status_code == 403
    assert client.post(f"/api/v1/users/{target}/suspend", headers=headers).status_code == 403
    assert client.post(
        f"/api/v1/users/{target}/reset-password", json={"new_password": "Hacked123!"}, headers=headers
    ).status_code == 403
    res = client.put(f"/api/v1/users/{seed['tw_emp'].id}/roles", json={"role_ids": ["ADMIN"]}, headers=headers)
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "PERMISSION_DENIED"
    assert client.post(
        "/api/v1/users",
        json={"username": "evil", "email": "evil@etron.example", "password": "Password123!", "display_name": "x"},
        headers=headers,
    ).status_code == 403
    assert client.put(
        "/api/v1/users/meta/roles/GENERAL_USER/permissions",
        json={"permission_codes": ["system.user.manage"]},
        headers=headers,
    ).status_code == 403


def test_user_admin_is_limited_to_own_company(client, seed):
    headers = _login(client, "tw_user_admin")

    listed = client.get("/api/v1/users")
    assert listed.status_code == 200
    companies = {u["primary_company_id"] for u in listed.json()}
    assert companies == {"ETJ-TW"}

    assert client.get("/api/v1/users", params={"company_id": "ETJ-JP"}).status_code == 403

    jp_id = seed["jp_emp"].id
    res = client.get(f"/api/v1/users/{jp_id}")
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "CROSS_COMPANY_FORBIDDEN"
    assert client.post(f"/api/v1/users/{jp_id}/suspend", headers=headers).status_code == 403
    assert client.get(f"/api/v1/users/{jp_id}/sessions").status_code == 403

    # 不可在他公司建立帳號
    res = client.post(
        "/api/v1/users",
        json={
            "username": "new_jp",
            "email": "new_jp@etron.example",
            "password": "Password123!",
            "display_name": "new",
            "primary_company_id": "ETJ-JP",
        },
        headers=headers,
    )
    assert res.status_code == 403

    # 本公司帳號可正常管理
    tw_id = seed["tw_emp"].id
    assert client.get(f"/api/v1/users/{tw_id}").status_code == 200


def test_non_admin_cannot_grant_admin_role(client, seed):
    headers = _login(client, "tw_user_admin")
    res = client.put(
        f"/api/v1/users/{seed['tw_emp'].id}/roles",
        json={"company_id": "ETJ-TW", "role_ids": ["ADMIN"]},
        headers=headers,
    )
    assert res.status_code == 403
    assert res.json()["error"]["code"] == "ROLE_GRANT_FORBIDDEN"

    res = client.post(
        "/api/v1/users",
        json={
            "username": "sneaky",
            "email": "sneaky@etron.example",
            "password": "Password123!",
            "display_name": "s",
            "role_ids": ["ADMIN"],
        },
        headers=headers,
    )
    assert res.status_code == 403


def test_cannot_suspend_self(client, seed):
    headers = _login(client, "root_admin")
    res = client.post(f"/api/v1/users/{seed['admin'].id}/suspend", headers=headers)
    assert res.status_code == 400
    assert res.json()["error"]["code"] == "SELF_SUSPEND_FORBIDDEN"


def test_admin_can_manage_any_company(client, seed):
    headers = _login(client, "root_admin")
    jp_id = seed["jp_emp"].id
    assert client.get(f"/api/v1/users/{jp_id}").status_code == 200
    assert client.post(f"/api/v1/users/{jp_id}/suspend", headers=headers).status_code == 200


# ---------- 工作階段查詢及撤銷 ----------

def test_list_my_sessions_marks_current_and_hides_secrets(client, seed):
    _login(client, "tw_employee")
    other = _second_client()
    _login(other, "tw_employee")

    res = client.get("/api/v1/auth/sessions")
    assert res.status_code == 200
    sessions = res.json()
    assert len(sessions) == 2
    assert sum(1 for s in sessions if s["is_current"]) == 1
    for s in sessions:
        assert "session_token_hash" not in s and "csrf_token" not in s
        assert s["created_at"].endswith("Z")


def test_revoke_other_sessions_keeps_current(client, seed):
    headers = _login(client, "tw_employee")
    other = _second_client()
    _login(other, "tw_employee")
    assert other.get("/api/v1/auth/me").status_code == 200

    res = client.post("/api/v1/auth/sessions/revoke-others", headers=headers)
    assert res.status_code == 200
    assert res.json()["revoked_count"] == 1

    assert client.get("/api/v1/auth/me").status_code == 200
    gone = other.get("/api/v1/auth/me")
    assert gone.status_code == 401
    assert gone.json()["error"]["code"] == "SESSION_REVOKED"


def test_revoke_specific_session_and_idor_protection(client, seed, db_session):
    headers = _login(client, "tw_employee")
    other = _second_client()
    _login(other, "tw_employee")

    mine = client.get("/api/v1/auth/sessions").json()
    other_id = next(s["id"] for s in mine if not s["is_current"])
    res = client.post(f"/api/v1/auth/sessions/{other_id}/revoke", headers=headers)
    assert res.status_code == 200
    assert res.json()["is_current"] is False
    assert other.get("/api/v1/auth/me").status_code == 401

    # 他人 session 不可撤銷，且以 404 回應不洩漏存在與否
    jp_client = _second_client()
    _login(jp_client, "jp_employee")
    jp_session_id = db_session.execute(
        select(UserSession.id).where(UserSession.user_id == seed["jp_emp"].id, UserSession.is_revoked == False)  # noqa: E712
    ).scalar_one()
    res = client.post(f"/api/v1/auth/sessions/{jp_session_id}/revoke", headers=headers)
    assert res.status_code == 404
    assert jp_client.get("/api/v1/auth/me").status_code == 200

    # 缺 CSRF token 的撤銷請求被拒
    res = client.post(f"/api/v1/auth/sessions/{jp_session_id}/revoke")
    assert res.status_code == 403


def test_revoke_current_session_logs_out(client, seed):
    headers = _login(client, "tw_employee")
    current = next(s for s in client.get("/api/v1/auth/sessions").json() if s["is_current"])
    res = client.post(f"/api/v1/auth/sessions/{current['id']}/revoke", headers=headers)
    assert res.status_code == 200
    assert res.json()["is_current"] is True
    assert client.get("/api/v1/auth/me").status_code == 401


def test_change_password_revokes_other_sessions(client, seed):
    headers = _login(client, "tw_employee")
    other = _second_client()
    _login(other, "tw_employee")

    res = client.post(
        "/api/v1/auth/change-password",
        json={"old_password": PASSWORD, "new_password": "NewPassword456!"},
        headers=headers,
    )
    assert res.status_code == 200
    assert res.json()["revoked_other_sessions"] == 1
    assert client.get("/api/v1/auth/me").status_code == 200
    assert other.get("/api/v1/auth/me").status_code == 401


def test_admin_lists_and_force_logs_out_user(client, seed):
    victim = _second_client()
    _login(victim, "tw_employee")

    headers = _login(client, "tw_user_admin")
    uid = seed["tw_emp"].id
    listed = client.get(f"/api/v1/users/{uid}/sessions")
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    res = client.post(f"/api/v1/users/{uid}/sessions/revoke", headers=headers)
    assert res.status_code == 200
    assert res.json()["revoked_count"] == 1
    assert victim.get("/api/v1/auth/me").status_code == 401
    assert client.get(f"/api/v1/users/{uid}/sessions").json() == []



def test_seed_roles_is_safe_under_concurrent_requests(tmp_path):
    """首次載入時多個請求並行補種內建角色，不得因唯一鍵衝突失敗"""
    import threading
    from sqlalchemy import create_engine, event, func
    from sqlalchemy.orm import sessionmaker
    from app.core.database import Base
    from app.api.v1.users import ensure_seed_permissions_and_roles, ALL_SYSTEM_PERMISSIONS

    engine = create_engine(f"sqlite:///{tmp_path / 'seed.db'}", connect_args={"timeout": 30})

    @event.listens_for(engine, "connect")
    def _pragma(conn, _):
        conn.execute("PRAGMA journal_mode=WAL")

    Base.metadata.create_all(engine)
    Local = sessionmaker(bind=engine, autoflush=False)
    errors, barrier = [], threading.Barrier(6)

    def worker():
        db = Local()
        try:
            barrier.wait()
            ensure_seed_permissions_and_roles(db)
        except Exception as exc:  # pragma: no cover - 失敗時回報
            errors.append(repr(exc))
        finally:
            db.close()

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    with Local() as db:
        assert db.execute(select(func.count()).select_from(Permission)).scalar() == len(ALL_SYSTEM_PERMISSIONS)
        assert db.get(Role, "ADMIN") is not None
    engine.dispose()


def test_seed_does_not_regrant_removed_permissions(db_session):
    """管理員自權限矩陣移除的權限，不可在後續請求被自動補回"""
    from app.api.v1.users import ensure_seed_permissions_and_roles

    ensure_seed_permissions_and_roles(db_session)
    rp = db_session.get(RolePermission, ("GENERAL_USER", "leave.create"))
    assert rp is not None
    db_session.delete(rp)
    db_session.commit()

    ensure_seed_permissions_and_roles(db_session)
    assert db_session.get(RolePermission, ("GENERAL_USER", "leave.create")) is None
