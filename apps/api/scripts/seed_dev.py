import sys
import os

# 將 apps/api 加入路徑
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import select
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.auth import User, Role, Permission, RolePermission, UserRole, UserScope
from app.models.hr import Company, Organization

def seed_database():
    db = SessionLocal()
    try:
        # 1. 公司資料
        tw = db.get(Company, "ETJ-TW")
        if not tw:
            tw = Company(id="ETJ-TW", name="鈺創台灣總部", default_timezone="Asia/Taipei", default_currency="TWD")
            db.add(tw)

        jp = db.get(Company, "ETJ-JP")
        if not jp:
            jp = Company(id="ETJ-JP", name="福岡支社", default_timezone="Asia/Tokyo", default_currency="JPY")
            db.add(jp)

        db.commit()

        # 2. 部門資料
        rd = db.get(Organization, "ORG-RD")
        if not rd:
            rd = Organization(id="ORG-RD", company_id="ETJ-TW", code="RD", name="研發處", level="DIVISION")
            db.add(rd)

        sw = db.get(Organization, "ORG-SW")
        if not sw:
            sw = Organization(id="ORG-SW", company_id="ETJ-TW", code="SW", name="軟體研發部", parent_id="ORG-RD", level="DEPARTMENT")
            db.add(sw)

        db.commit()

        # 3. 權限與角色
        perms = [
            ("hr.employee.manage", "人事員工管理", "HR"),
            ("leave.create", "請假申請", "LEAVE"),
            ("dashboard.view", "營運儀表板檢視", "SYSTEM"),
        ]
        for code, name, mod in perms:
            p = db.get(Permission, code)
            if not p:
                db.add(Permission(code=code, name=name, module=mod))

        role_hr = db.get(Role, "HR_ADMIN")
        if not role_hr:
            role_hr = Role(id="HR_ADMIN", name="人事主管")
            db.add(role_hr)

        role_user = db.get(Role, "GENERAL_USER")
        if not role_user:
            role_user = Role(id="GENERAL_USER", name="一般同仁")
            db.add(role_user)

        db.commit()

        # 關聯權限
        for pcode, _, _ in perms:
            rp = db.execute(
                select(RolePermission).where(
                    RolePermission.role_id == "HR_ADMIN",
                    RolePermission.permission_code == pcode,
                )
            ).scalar_one_or_none()
            if not rp:
                db.add(RolePermission(role_id="HR_ADMIN", permission_code=pcode))

        db.commit()

        # 4. 使用者帳號
        users_to_seed = [
            {
                "username": "hr_manager",
                "email": "hr_manager@etron.com",
                "password": "AdminSecure123!",
                "display_name": "人事經理",
                "company_id": "ETJ-TW",
                "is_first_login": False,
                "role_id": "HR_ADMIN",
            },
            {
                "username": "test_admin",
                "email": "admin@etron.com",
                "password": "AdminSecure123!",
                "display_name": "系統管理員",
                "company_id": "ETJ-TW",
                "is_first_login": False,
                "role_id": "HR_ADMIN",
            },
            {
                "username": "new_employee",
                "email": "new_employee@etron.com",
                "password": "Welcome123!",
                "display_name": "新進員工",
                "company_id": "ETJ-TW",
                "is_first_login": True,
                "role_id": "GENERAL_USER",
            },
        ]

        for u in users_to_seed:
            existing = db.execute(select(User).where(User.username == u["username"])).scalar_one_or_none()
            if not existing:
                user = User(
                    username=u["username"],
                    email=u["email"],
                    hashed_password=hash_password(u["password"]),
                    display_name=u["display_name"],
                    primary_company_id=u["company_id"],
                    is_active=True,
                    is_first_login=u["is_first_login"],
                )
                db.add(user)
                db.commit()

                # UserRole
                db.add(UserRole(user_id=user.id, role_id=u["role_id"], company_id=u["company_id"]))
                # UserScope
                db.add(UserScope(user_id=user.id, company_id=u["company_id"], scope_type="COMPANY"))
                db.commit()
                print(f"Created seed user: {u['username']}")
            else:
                print(f"Seed user exists: {u['username']}")

        print("Dev database seed completed successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
