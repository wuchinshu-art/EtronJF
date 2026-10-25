from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, status, Query
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session as DbSession
from sqlalchemy import select, update, func, or_

from app.core.database import get_db
from app.core.security import hash_password
from app.core.errors import AppException
from app.models.auth import (
    User,
    Session as UserSession,
    UserRole,
    UserScope,
    Role,
    Permission,
    RolePermission,
)
from app.models.hr import Employee, Company
from app.api.deps import get_current_user, get_current_session, require_permissions

router = APIRouter(prefix="/users", tags=["Users & RBAC"])


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ==========================================
# 系統內建標準權限定義字典 (Master Permissions Dictionary)
# ==========================================
ALL_SYSTEM_PERMISSIONS = [
    # HR 人事模組
    {"code": "hr.employee.manage", "name": "人事員工維護與到離職", "module": "HR", "description": "允許開立員工到職、個人資料修改、部門調職與離職辦理"},
    {"code": "hr.org.manage", "name": "組織部門架構管理", "module": "HR", "description": "允許新增、編輯與停用公司部門組織階層"},
    {"code": "hr.shift.manage", "name": "班別工時與排班管理", "module": "HR", "description": "允許維護公司班別起訖、午休時段、彈性工時與法定標準工時"},
    {"code": "hr.ledger.manage", "name": "假額帳本與天數維護", "module": "HR", "description": "允許維護各假別主檔與員工不可變假額入帳作業"},

    # LEAVE 請假模組
    {"code": "leave.create", "name": "開立請假申請", "module": "LEAVE", "description": "允許開立特別休假、病假、事假等請假申請單"},
    {"code": "leave.approve", "name": "請假單主管審核", "module": "LEAVE", "description": "允許對部屬之請假申請進行核准或駁回簽核"},
    {"code": "leave.cancel", "name": "請假銷假與撤回", "module": "LEAVE", "description": "允許申請人抽單或銷假返還假額帳本"},

    # ATTENDANCE 考勤打卡模組
    {"code": "attendance.punch", "name": "在線打卡出勤", "module": "ATTENDANCE", "description": "允許上班/下班/外出即時定位在線打卡"},
    {"code": "attendance.manage", "name": "考勤異常檢視與匯入", "module": "ATTENDANCE", "description": "允許檢視全公司打卡事件記錄與打卡文字批次匯入解析"},

    # TRAVEL 出差與結報模組
    {"code": "travel.create", "name": "開立出差申請與預支款", "module": "TRAVEL", "description": "允許開立公務出差單與申請多幣別差旅預支款項"},
    {"code": "travel.approve", "name": "出差單主管審核", "module": "TRAVEL", "description": "允許代理人確認、直屬主管審查與人事窗口核備"},
    {"code": "travel.settle", "name": "差旅實報實銷結報", "module": "TRAVEL", "description": "允許出差核准後填寫費用明細項目並折抵預支款辦理結報"},
    {"code": "travel.finance", "name": "差旅會計確認與結清", "module": "TRAVEL", "description": "允許財務會計窗口審核差旅支出憑證並確認付款結清"},

    # FINANCE 費用報支與請款模組
    {"code": "expense.create", "name": "開立費用報銷單", "module": "FINANCE", "description": "允許填寫日常公務憑證進行實報實銷"},
    {"code": "expense.approve", "name": "費用報銷多級主管審核", "module": "FINANCE", "description": "允許依 5K/100K 門檻進行第二/三層主管逐級核可"},
    {"code": "payment.create", "name": "開立供應商請款單", "module": "FINANCE", "description": "允許關聯採購廠商開立付款申請並儲存不可變受款快照"},
    {"code": "payment.approve", "name": "供應商請款多級管線審核", "module": "FINANCE", "description": "允許依 5K/100K/500K 進行部/處/總經理多層審核推進"},
    {"code": "payment.finance", "name": "會計付款結清與匯差調整", "module": "FINANCE", "description": "允許執行出納付款登記並精確核算 ERP 拋轉匯兌損益"},
    {"code": "vendor.manage", "name": "供應商主檔與銀行帳戶維護", "module": "FINANCE", "description": "允許新增/編輯合作廠商資料並檢視完整非遮罩受款帳號"},

    # SEAL 用印管理模組
    {"code": "seal.request", "name": "開立正式用印申請", "module": "SEAL", "description": "允許申請公司大章、法人章、合約章與發票章用印"},
    {"code": "seal.approve", "name": "用印申請主管審核", "module": "SEAL", "description": "允許審查用印文件與用途事由"},
    {"code": "seal.execute", "name": "保管人實體用印登記", "module": "SEAL", "description": "允許印鑑法定保管人登記用印份數與掃描歸檔"},
    {"code": "seal.master", "name": "印鑑清冊主檔維護", "module": "SEAL", "description": "允許新增與維護公司法定印章清冊與保管人員"},

    # CONTRACT 合約管理模組
    {"code": "contract.create", "name": "合約主檔建立與審查送審", "module": "CONTRACT", "description": "允許建立採購、銷售、NDA與委任合約審查草稿"},
    {"code": "contract.approve", "name": "合約法務與權責主管審查", "module": "CONTRACT", "description": "允許法務窗口與業務主管進行合約條款審查"},
    {"code": "contract.archive", "name": "簽署合約歸檔與管理", "module": "CONTRACT", "description": "允許雙方簽妥後登記正式生效與上傳電子掃描件歸檔"},

    # SYSTEM 系統管理模組
    {"code": "system.user.manage", "name": "帳號管理與強制重設密碼", "module": "SYSTEM", "description": "允許開立、編輯、停用/啟用系統帳號與管理員密碼重設"},
    {"code": "system.role.manage", "name": "角色定義與 RBAC 權限設定", "module": "SYSTEM", "description": "允許新增自訂角色與在權限矩陣中調整模組權限授權"},
    {"code": "dashboard.view", "name": "營運儀表板總覽檢視", "module": "SYSTEM", "description": "允許檢視個人與公司營運即時儀表板統計指標"},
]

DEFAULT_ROLES = [
    {
        "id": "ADMIN",
        "name": "系統最高管理員",
        "description": "具備全模組所有業務操作、系統帳號管理與權限配置最高權力",
        "all_perms": True,
    },
    {
        "id": "HR_ADMIN",
        "name": "人事管理主管",
        "description": "具備人事主檔、組織部門、班別工時、假額帳本、請假與出勤完整權限",
        "perm_prefixes": ["hr.", "leave.", "attendance.", "dashboard."],
    },
    {
        "id": "FINANCE_OFFICER",
        "name": "財務會計主管",
        "description": "具備費用報銷、供應商請款、會計結清、匯率匯差與差旅財務審批權限",
        "perm_prefixes": ["expense.", "payment.", "vendor.", "travel.finance", "dashboard."],
    },
    {
        "id": "LEGAL_OFFICER",
        "name": "法務與印鑑保管人",
        "description": "具備用印申請審查、保管人實體用印登記、合約審查與合約歸檔權限",
        "perm_prefixes": ["seal.", "contract.", "dashboard."],
    },
    {
        "id": "DEPT_HEAD",
        "name": "部門主管",
        "description": "具備部屬請假初審、出差審查、費用審查與合約初審權限",
        "perm_prefixes": ["leave.approve", "travel.approve", "expense.approve", "payment.approve", "dashboard."],
    },
    {
        "id": "GENERAL_USER",
        "name": "一般在職員工",
        "description": "標準日常操作：個人在線打卡、請假、出差預支、費用報銷與用印申請",
        "perms": [
            "leave.create", "attendance.punch", "travel.create", "travel.settle",
            "expense.create", "seal.request", "dashboard.view"
        ],
    },
]


def ensure_seed_permissions_and_roles(db: DbSession):
    """確保系統全量標準權限碼與預設內建角色已入庫"""
    # 1. 確保 Permissions
    existing_perms = {p.code: p for p in db.execute(select(Permission)).scalars().all()}
    for item in ALL_SYSTEM_PERMISSIONS:
        if item["code"] not in existing_perms:
            p = Permission(
                code=item["code"],
                name=item["name"],
                module=item["module"],
                description=item["description"],
            )
            db.add(p)
            existing_perms[item["code"]] = p
    db.commit()

    # 2. 確保 Roles 與關聯 RolePermission
    for r_def in DEFAULT_ROLES:
        role = db.get(Role, r_def["id"])
        if not role:
            role = Role(
                id=r_def["id"],
                name=r_def["name"],
                description=r_def["description"],
            )
            db.add(role)
            db.commit()

        # 分配權限
        current_assigned = set(
            db.execute(select(RolePermission.permission_code).where(RolePermission.role_id == role.id)).scalars().all()
        )

        target_codes = set()
        if r_def.get("all_perms"):
            target_codes = set(existing_perms.keys())
        elif "perm_prefixes" in r_def:
            for code in existing_perms.keys():
                if any(code.startswith(pref) for pref in r_def["perm_prefixes"]):
                    target_codes.add(code)
        elif "perms" in r_def:
            target_codes = set(r_def["perms"])

        for t_code in target_codes:
            if t_code not in current_assigned and t_code in existing_perms:
                db.add(RolePermission(role_id=role.id, permission_code=t_code))
    db.commit()


# ==========================================
# Pydantic 請求與回應模型 (Schemas)
# ==========================================
class CreateUserRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    email: EmailStr
    password: str = Field(min_length=8)
    display_name: str
    primary_company_id: Optional[str] = None
    active_company_id: Optional[str] = None
    employee_id: Optional[str] = None
    role_ids: List[str] = Field(default_factory=list, description="欲指派的角色代碼清單")
    roles: Optional[List[str]] = Field(default=None, description="相容前端別名 roles")


class UpdateUserRequest(BaseModel):
    display_name: Optional[str] = None
    email: Optional[EmailStr] = None
    primary_company_id: Optional[str] = None
    active_company_id: Optional[str] = None
    employee_id: Optional[str] = None
    is_active: Optional[bool] = None


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, description="管理員指定之新密碼")


class AssignRolesRequest(BaseModel):
    company_id: Optional[str] = Field(default=None, description="角色生效公司")
    role_ids: Optional[List[str]] = Field(default=None, description="角色代碼清單")
    role_names: Optional[List[str]] = Field(default=None, description="相容前端別名 role_names")


class RoleCreateRequest(BaseModel):
    id: str = Field(min_length=2, max_length=50, description="角色英數字唯一代號，如 AUDITOR")
    name: str = Field(min_length=2, max_length=100, description="角色中文名稱")
    description: Optional[str] = None
    permission_codes: List[str] = Field(default_factory=list, description="初始權限清單")


class RoleUpdateRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class RolePermissionsUpdateRequest(BaseModel):
    permission_codes: List[str] = Field(description="權限代碼清單")


# ==========================================
# 使用者帳號管理端點 (User Accounts API)
# ==========================================
@router.get("", status_code=status.HTTP_200_OK)
def list_users(
    company_id: Optional[str] = Query(None, description="公司代碼過濾"),
    keyword: Optional[str] = Query(None, description="使用者名稱/姓名/Email 搜尋關鍵字"),
    is_active: Optional[bool] = Query(None, description="啟用狀態過濾"),
    db: DbSession = Depends(get_db),
):
    """
    查詢使用者帳號清單：
    - 關聯展示員工工號、真實姓名、所屬部門
    - 關聯展示當前已賦予之所有角色代碼與生效公司
    """
    ensure_seed_permissions_and_roles(db)

    stmt = select(User)
    if company_id:
        stmt = stmt.where(User.primary_company_id == company_id)
    if is_active is not None:
        stmt = stmt.where(User.is_active == is_active)
    if keyword:
        pattern = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                User.username.ilike(pattern),
                User.display_name.ilike(pattern),
                User.email.ilike(pattern),
            )
        )
    stmt = stmt.order_by(User.created_at.desc())
    users = db.execute(stmt).scalars().all()

    result = []
    for u in users:
        # 查詢員工資料
        emp_info = None
        if u.employee_id:
            emp = db.get(Employee, u.employee_id)
            if emp:
                emp_info = {
                    "id": emp.id,
                    "employee_no": emp.employee_no,
                    "full_name": emp.full_name,
                    "organization_id": emp.organization_id,
                    "status": emp.status,
                }

        # 查詢使用者所屬角色
        roles_stmt = (
            select(UserRole.role_id, UserRole.company_id, Role.name)
            .join(Role, UserRole.role_id == Role.id)
            .where(UserRole.user_id == u.id)
        )
        roles_rows = db.execute(roles_stmt).all()
        user_roles = [
            {"role_id": r_id, "company_id": c_id, "role_name": r_name}
            for r_id, c_id, r_name in roles_rows
        ]
        role_codes = [r_id for r_id, _, _ in roles_rows]

        result.append({
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "display_name": u.display_name,
            "primary_company_id": u.primary_company_id,
            "active_company_id": u.primary_company_id,
            "is_active": u.is_active,
            "is_first_login": u.is_first_login,
            "must_change_password": u.is_first_login,
            "employee_id": u.employee_id,
            "employee_no": emp_info["employee_no"] if emp_info else None,
            "employee": emp_info,
            "roles": user_roles,
            "role_names": role_codes,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "updated_at": u.updated_at.isoformat() if u.updated_at else None,
        })

    return result


@router.post("", status_code=status.HTTP_201_CREATED)
def create_user(
    req: CreateUserRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """新增系統帳號 (支援自訂密碼、主公司與初始角色指派)"""
    ensure_seed_permissions_and_roles(db)

    # 檢查 username 與 email 唯一性
    exist_check = db.execute(
        select(User).where((User.username == req.username) | (User.email == req.email))
    ).scalar_one_or_none()

    if exist_check:
        raise AppException(
            code="USER_ALREADY_EXISTS",
            message=f"帳號名稱 [{req.username}] 或電子郵件 [{req.email}] 已被註冊使用",
            status_code=status.HTTP_409_CONFLICT,
        )

    comp_id = req.primary_company_id or req.active_company_id or "ETJ-TW"

    new_user = User(
        username=req.username,
        email=req.email,
        hashed_password=hash_password(req.password),
        display_name=req.display_name,
        primary_company_id=comp_id,
        employee_id=req.employee_id,
        is_active=True,
        is_first_login=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # 建立主公司 scope
    scope = UserScope(
        user_id=new_user.id,
        company_id=comp_id,
        scope_type="COMPANY",
    )
    db.add(scope)

    # 建立角色關聯 (預設至少 GENERAL_USER)
    candidate_roles = req.role_ids if req.role_ids else (req.roles if req.roles else ["GENERAL_USER"])
    for rid in candidate_roles:
        role = db.get(Role, rid)
        if not role:
            role = db.execute(select(Role).where(Role.name == rid)).scalar_one_or_none()
        if role:
            db.add(UserRole(
                user_id=new_user.id,
                role_id=role.id,
                company_id=comp_id,
            ))
    db.commit()

    return {
        "status": "success",
        "user_id": new_user.id,
        "username": new_user.username,
        "display_name": new_user.display_name,
        "message": f"帳號 [{new_user.username}] 已成功建立",
    }


@router.get("/{user_id}", status_code=status.HTTP_200_OK)
def get_user_detail(
    user_id: str,
    db: DbSession = Depends(get_db),
):
    """查詢單一使用者帳號詳情"""
    u = db.get(User, user_id)
    if not u:
        raise AppException(code="USER_NOT_FOUND", message=f"找不到指定使用者 [{user_id}]", status_code=404)

    roles_stmt = (
        select(UserRole.role_id, UserRole.company_id, Role.name)
        .join(Role, UserRole.role_id == Role.id)
        .where(UserRole.user_id == u.id)
    )
    user_roles = [
        {"role_id": r_id, "company_id": c_id, "role_name": r_name}
        for r_id, c_id, r_name in db.execute(roles_stmt).all()
    ]

    scopes = [
        {"company_id": s.company_id, "scope_type": s.scope_type}
        for s in db.execute(select(UserScope).where(UserScope.user_id == u.id)).scalars().all()
    ]

    emp_info = None
    if u.employee_id:
        emp = db.get(Employee, u.employee_id)
        if emp:
            emp_info = {
                "id": emp.id,
                "employee_no": emp.employee_no,
                "full_name": emp.full_name,
                "organization_id": emp.organization_id,
            }

    return {
        "id": u.id,
        "username": u.username,
        "email": u.email,
        "display_name": u.display_name,
        "primary_company_id": u.primary_company_id,
        "is_active": u.is_active,
        "is_first_login": u.is_first_login,
        "employee_id": u.employee_id,
        "employee": emp_info,
        "roles": user_roles,
        "scopes": scopes,
    }


@router.put("/{user_id}", status_code=status.HTTP_200_OK)
def update_user(
    user_id: str,
    req: UpdateUserRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """更新使用者基本資料 (姓名、Email、主公司、綁定員工或啟用狀態)"""
    u = db.get(User, user_id)
    if not u:
        raise AppException(code="USER_NOT_FOUND", message=f"找不到指定使用者 [{user_id}]", status_code=404)

    if req.display_name is not None:
        u.display_name = req.display_name
    if req.email is not None:
        u.email = req.email
    new_comp = req.primary_company_id or req.active_company_id
    if new_comp is not None:
        u.primary_company_id = new_comp
    if req.employee_id is not None:
        u.employee_id = req.employee_id if req.employee_id else None
    if req.is_active is not None:
        u.is_active = req.is_active

    u.updated_at = utc_now()
    u.version += 1
    db.commit()
    db.refresh(u)

    return {"status": "success", "message": f"使用者 [{u.username}] 資料更新成功"}


@router.post("/{user_id}/activate", status_code=status.HTTP_200_OK)
def activate_user(
    user_id: str,
    current_user: Optional[User] = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """重新啟用使用者帳號"""
    u = db.get(User, user_id)
    if not u:
        raise AppException(code="USER_NOT_FOUND", message=f"找不到指定使用者 [{user_id}]", status_code=404)

    u.is_active = True
    u.updated_at = utc_now()
    u.version += 1
    db.commit()

    return {"status": "success", "message": f"使用者 [{u.username}] 已重新啟用"}


@router.post("/{user_id}/suspend", status_code=status.HTTP_200_OK)
def suspend_user(
    user_id: str,
    current_user: Optional[User] = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """
    停用使用者帳號：
    1. 標記 user.is_active = False
    2. 立即撤銷 (Revoke) 該使用者所有作用中的 Session！
    """
    target = db.get(User, user_id)
    if not target:
        raise AppException(
            code="USER_NOT_FOUND",
            message="找不到指定的使用者",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    target.is_active = False
    target.updated_at = utc_now()
    target.version += 1

    # 立即撤銷該使用者之全部 Sessions
    now = utc_now()
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.is_revoked == False)
        .values(is_revoked=True, revoked_at=now)
    )
    db.commit()

    return {"status": "success", "message": f"使用者 [{target.username}] 已停用，所有有效工作階段已即時撤銷"}


@router.post("/{user_id}/reset-password", status_code=status.HTTP_200_OK)
def reset_user_password(
    user_id: str,
    req: ResetPasswordRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """管理者強制重設使用者密碼 (下次登入將被要求強制變更密碼)"""
    u = db.get(User, user_id)
    if not u:
        raise AppException(code="USER_NOT_FOUND", message=f"找不到指定使用者 [{user_id}]", status_code=404)

    u.hashed_password = hash_password(req.new_password)
    u.is_first_login = True  # 標記為首次登入要求修改密碼
    u.updated_at = utc_now()
    u.version += 1

    # 撤銷舊 session
    now = utc_now()
    db.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.is_revoked == False)
        .values(is_revoked=True, revoked_at=now)
    )
    db.commit()

    return {"status": "success", "message": f"帳號 [{u.username}] 密碼已重設，下次登入將要求強制變更密碼"}


@router.put("/{user_id}/roles", status_code=status.HTTP_200_OK)
def assign_user_roles(
    user_id: str,
    req: AssignRolesRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """更新指定使用者在特定公司生效之角色清單"""
    u = db.get(User, user_id)
    if not u:
        raise AppException(code="USER_NOT_FOUND", message=f"找不到指定使用者 [{user_id}]", status_code=404)

    target_company = req.company_id or u.primary_company_id or "ETJ-TW"
    target_roles = req.role_ids if req.role_ids is not None else (req.role_names if req.role_names is not None else [])

    # 清除該使用者在該公司的現有角色
    existing_roles = db.execute(
        select(UserRole).where(UserRole.user_id == user_id, UserRole.company_id == target_company)
    ).scalars().all()
    for er in existing_roles:
        db.delete(er)

    # 建立新角色關聯 (支援 role.id 與 role.name 容錯解析)
    for rid in target_roles:
        role = db.get(Role, rid)
        if not role:
            role = db.execute(select(Role).where(Role.name == rid)).scalar_one_or_none()
        if role:
            db.add(UserRole(
                user_id=user_id,
                role_id=role.id,
                company_id=target_company,
            ))

    # 確保公司 scope 存在
    existing_scope = db.execute(
        select(UserScope).where(UserScope.user_id == user_id, UserScope.company_id == target_company)
    ).scalar_one_or_none()
    if not existing_scope:
        db.add(UserScope(user_id=user_id, company_id=target_company, scope_type="COMPANY"))

    db.commit()
    return {"status": "success", "message": f"使用者 [{u.username}] 角色分配已更新"}


# ==========================================
# 角色與權限字典元資料端點 (Roles & Permissions Meta API)
# ==========================================
@router.get("/meta/permissions", status_code=status.HTTP_200_OK)
def list_system_permissions(
    db: DbSession = Depends(get_db),
):
    """取得系統全量權限定義清單 (依模組 Module 分組)"""
    ensure_seed_permissions_and_roles(db)
    perms = db.execute(select(Permission).order_by(Permission.module, Permission.code)).scalars().all()

    # 依模組分組
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    module_names = {
        "HR": "👥 人事主檔 (HR Master)",
        "LEAVE": "🌴 請假管理 (Leave)",
        "ATTENDANCE": "⏱️ 出勤考勤 (Attendance)",
        "TRAVEL": "✈️ 出差結報 (Travel)",
        "FINANCE": "💵 費用請款 (Finance)",
        "SEAL": "🔏 用印管理 (Seal)",
        "CONTRACT": "📜 合約審查 (Contract)",
        "SYSTEM": "⚙️ 系統安全 (System & Access)",
    }

    for p in perms:
        mod_key = p.module
        if mod_key not in grouped:
            grouped[mod_key] = []
        grouped[mod_key].append({
            "code": p.code,
            "name": p.name,
            "module": p.module,
            "description": p.description,
        })

    result = []
    for mod_key, p_list in grouped.items():
        result.append({
            "module": mod_key,
            "module_name": module_names.get(mod_key, mod_key),
            "permissions": p_list,
        })

    return result


@router.get("/meta/roles", status_code=status.HTTP_200_OK)
def list_roles_with_permissions(
    db: DbSession = Depends(get_db),
):
    """查詢所有角色、使用者人數與各角色被賦予之權限代碼清單"""
    ensure_seed_permissions_and_roles(db)
    roles = db.execute(select(Role).order_by(Role.id)).scalars().all()

    result = []
    for r in roles:
        # 查詢關聯權限
        perm_codes = db.execute(
            select(RolePermission.permission_code).where(RolePermission.role_id == r.id)
        ).scalars().all()

        # 查詢被指派此角色的使用者數
        user_count = db.execute(
            select(func.count(func.distinct(UserRole.user_id))).where(UserRole.role_id == r.id)
        ).scalar() or 0

        is_sys = r.id in ["ADMIN", "HR_ADMIN", "FINANCE_OFFICER", "LEGAL_OFFICER", "DEPT_HEAD", "GENERAL_USER"]
        result.append({
            "id": r.id,
            "name": r.name,
            "description": r.description,
            "company_id": r.company_id,
            "user_count": user_count,
            "users_count": user_count,
            "permission_codes": perm_codes,
            "permissions_count": len(perm_codes),
            "is_system_builtin": is_sys,
            "is_system": is_sys,
        })

    return result


@router.post("/meta/roles", status_code=status.HTTP_201_CREATED)
def create_role(
    req: RoleCreateRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """新增自訂角色"""
    existing = db.get(Role, req.id)
    if existing:
        raise AppException(code="ROLE_EXISTS", message=f"角色代號 [{req.id}] 已存在", status_code=400)

    role = Role(
        id=req.id.upper().strip(),
        name=req.name.strip(),
        description=req.description,
    )
    db.add(role)
    db.commit()

    # 指派權限
    for pcode in req.permission_codes:
        p = db.get(Permission, pcode)
        if p:
            db.add(RolePermission(role_id=role.id, permission_code=pcode))
    db.commit()

    return {"status": "success", "role_id": role.id, "message": f"角色 [{role.name}] 已建立"}


@router.get("/meta/roles/{role_id}/permissions", status_code=status.HTTP_200_OK)
def get_role_permissions(
    role_id: str,
    db: DbSession = Depends(get_db),
):
    """取得特定角色之所有授權權限代碼清單"""
    role = db.get(Role, role_id)
    if not role:
        raise AppException(code="ROLE_NOT_FOUND", message=f"找不到角色 [{role_id}]", status_code=404)

    perm_codes = db.execute(
        select(RolePermission.permission_code).where(RolePermission.role_id == role_id)
    ).scalars().all()

    return {"role_id": role_id, "permission_codes": perm_codes}


@router.put("/meta/roles/{role_id}", status_code=status.HTTP_200_OK)
def update_role(
    role_id: str,
    req: RoleUpdateRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """更新角色基本資料 (名稱與說明)"""
    role = db.get(Role, role_id)
    if not role:
        raise AppException(code="ROLE_NOT_FOUND", message=f"找不到角色 [{role_id}]", status_code=404)

    if req.name is not None:
        role.name = req.name
    if req.description is not None:
        role.description = req.description

    db.commit()
    return {"status": "success", "message": f"角色 [{role.name}] 已更新"}


@router.put("/meta/roles/{role_id}/permissions", status_code=status.HTTP_200_OK)
def update_role_permissions(
    role_id: str,
    req: RolePermissionsUpdateRequest,
    current_user: Optional[User] = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """調整指定角色的 RBAC 權限指派清單 (權限矩陣更新)"""
    role = db.get(Role, role_id)
    if not role:
        raise AppException(code="ROLE_NOT_FOUND", message=f"找不到角色 [{role_id}]", status_code=404)

    # 移除舊對應
    existing = db.execute(select(RolePermission).where(RolePermission.role_id == role_id)).scalars().all()
    for e in existing:
        db.delete(e)

    # 寫入新權限
    for pcode in req.permission_codes:
        p = db.get(Permission, pcode)
        if p:
            db.add(RolePermission(role_id=role_id, permission_code=pcode))

    db.commit()
    return {"status": "success", "message": f"角色 [{role.name}] 之權限配置已更新，共授權 {len(req.permission_codes)} 項操作"}


@router.delete("/meta/roles/{role_id}", status_code=status.HTTP_200_OK)
def delete_role(
    role_id: str,
    current_user: Optional[User] = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """刪除自訂角色 (內建保護角色拒絕刪除)"""
    if role_id in ["ADMIN", "GENERAL_USER", "HR_ADMIN", "FINANCE_OFFICER"]:
        raise AppException(code="CANNOT_DELETE_BUILTIN_ROLE", message="系統核心內建角色受保護，禁止刪除", status_code=400)

    role = db.get(Role, role_id)
    if not role:
        raise AppException(code="ROLE_NOT_FOUND", message=f"找不到角色 [{role_id}]", status_code=404)

    # 檢查是否有使用者正使用此角色
    in_use = db.execute(select(UserRole).where(UserRole.role_id == role_id)).first()
    if in_use:
        raise AppException(code="ROLE_IN_USE", message=f"角色 [{role.name}] 仍有使用者綁定中，無法直接刪除", status_code=400)

    db.delete(role)
    db.commit()
    return {"status": "success", "message": f"角色 [{role.name}] 已刪除"}


# ==========================================
# 跨公司敏感資料安全測試專用端點 (保留以相容現有測試)
# ==========================================
@router.get("/companies/{company_id}/sensitive-data")
def get_company_sensitive_data(
    company_id: str,
    session: UserSession = Depends(get_current_session),
    db: DbSession = Depends(get_db),
):
    """
    存取特定公司的敏感財務/人事資料
    強制驗證公司權限範圍，防止跨公司水平越權 (IDOR)
    """
    stmt = (
        select(UserScope)
        .where(
            UserScope.user_id == session.user_id,
            UserScope.company_id == company_id,
        )
    )
    has_scope = db.execute(stmt).scalar_one_or_none() is not None
    if not has_scope and session.active_company_id != company_id:
        raise AppException(
            code="CROSS_COMPANY_FORBIDDEN",
            message=f"跨公司存取遭拒：無權存取公司 [{company_id}] 之業務資源",
            status_code=status.HTTP_403_FORBIDDEN,
        )

    return {
        "company_id": company_id,
        "confidential_status": "RESTRICTED_ACCESS_GRANTED",
    }
