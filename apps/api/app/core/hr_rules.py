from datetime import datetime, date, timezone
from typing import Optional, Set, List, Dict, Any
from sqlalchemy.orm import Session as DbSession
from sqlalchemy import select, func, desc

from app.models.hr import Company, Organization, ManagerRelation, LeaveLedger, Employee, EmployeeChange, LeaveType, Person
from app.models.auth import User, Session as AuthSession, UserRole, UserScope, Role
from app.core.security import hash_password
from app.core.errors import AppException


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def check_organization_cycle(db: DbSession, org_id: str, new_parent_id: Optional[str]) -> None:
    """
    組織階層循環檢驗 (Organization Hierarchy Cycle Detection)
    沿 parent_id 鏈向上遍歷，確保不會形成有向循環 (Directed Cycle)。
    """
    if not new_parent_id:
        return

    if org_id == new_parent_id:
        raise AppException(
            code="ORGANIZATION_CYCLE_DETECTED",
            message="組織的上層組織不能為自己",
            status_code=400,
        )

    current_parent_id = new_parent_id
    visited: Set[str] = {org_id}

    while current_parent_id:
        if current_parent_id in visited:
            raise AppException(
                code="ORGANIZATION_CYCLE_DETECTED",
                message=f"組織階層存在循環依賴，節點 [{current_parent_id}] 導致循環",
                status_code=400,
            )
        visited.add(current_parent_id)

        parent_org = db.get(Organization, current_parent_id)
        if not parent_org:
            break
        current_parent_id = parent_org.parent_id


def check_manager_cycle(db: DbSession, employee_id: str, new_manager_id: str) -> None:
    """
    主管關係鏈循環檢驗 (Manager Chain Cycle Detection)
    若將 A 的主管設為 B，檢查 B 的主管鏈中是否包含 A，避免相互核決與死循環。
    """
    if employee_id == new_manager_id:
        raise AppException(
            code="MANAGER_CYCLE_DETECTED",
            message="員工的主管不能為自己",
            status_code=400,
        )

    visited: Set[str] = {employee_id}
    current_manager_id: Optional[str] = new_manager_id

    while current_manager_id:
        if current_manager_id in visited:
            raise AppException(
                code="MANAGER_CYCLE_DETECTED",
                message=f"主管關係鏈存在循環依賴，員工 [{current_manager_id}] 導致循環",
                status_code=400,
            )
        visited.add(current_manager_id)

        # 查詢目前主管的直屬主管
        stmt = (
            select(ManagerRelation.manager_id)
            .where(
                ManagerRelation.employee_id == current_manager_id,
                ManagerRelation.relation_type == "DIRECT",
                (ManagerRelation.effective_to == None) | (ManagerRelation.effective_to >= date.today()),
            )
        )
        current_manager_id = db.execute(stmt).scalar_one_or_none()


def mask_national_id(national_id: Optional[str]) -> Optional[str]:
    """
    法定身分證號 / 居留證號 / マイナンバー 敏感個資遮罩
    例如 A123456789 -> A12****789
    """
    if not national_id:
        return None
    val = national_id.strip()
    if len(val) <= 5:
        return "****"
    return f"{val[:3]}****{val[-3:]}"


def search_persons(db: DbSession, keyword: str = "") -> List[Person]:
    """搜尋集團人員個資主檔 (支援身分證號、姓名、信箱或手機查詢)"""
    stmt = select(Person)
    if keyword and keyword.strip():
        k = f"%{keyword.strip()}%"
        stmt = stmt.where(
            (Person.full_name.ilike(k))
            | (Person.national_id.ilike(k))
            | (Person.english_name.ilike(k))
            | (Person.personal_email.ilike(k))
            | (Person.mobile_phone.ilike(k))
        )
    return list(db.execute(stmt.order_by(Person.full_name).limit(30)).scalars().all())


def onboard_employee(
    db: DbSession,
    employee_no: str,
    company_id: str,
    organization_id: str,
    full_name: str,
    email: str,
    hire_date: date,
    person_id: Optional[str] = None,
    english_name: Optional[str] = None,
    national_id: Optional[str] = None,
    birth_date: Optional[date] = None,
    gender: str = "NOT_SPECIFIED",
    nationality: Optional[str] = None,
    marital_status: str = "SINGLE",
    personal_email: Optional[str] = None,
    mobile_phone: Optional[str] = None,
    residential_address: Optional[str] = None,
    permanent_address: Optional[str] = None,
    emergency_contact_name: Optional[str] = None,
    emergency_contact_relationship: Optional[str] = None,
    emergency_contact_phone: Optional[str] = None,
    job_title: Optional[str] = None,
    job_grade: Optional[str] = None,
    employment_type: str = "REGULAR",
    default_shift_id: Optional[str] = None,
    probation_end_date: Optional[date] = None,
    create_user_account: bool = False,
    initial_password: Optional[str] = None,
) -> Employee:
    """
    新進員工報到作業 (Employee Onboarding)
    支援「人員個資主檔 (Person)」與「公司任職 (Employment/Employee)」分離設計。
    同一自然人可同時任職於多個不同公司。
    """
    # 1. 取得或建立 Person 主檔 (Get or Create Person Profile)
    person: Optional[Person] = None
    if person_id:
        person = db.get(Person, person_id)
        if not person:
            raise AppException(code="PERSON_NOT_FOUND", message=f"指定之人員主檔 [{person_id}] 不存在", status_code=404)
        # 用傳入資訊更新 Person 主檔最新連絡資訊
        if full_name:
            person.full_name = full_name
        if english_name is not None:
            person.english_name = english_name
        if birth_date is not None:
            person.birth_date = birth_date
        if gender:
            person.gender = gender
        if nationality is not None:
            person.nationality = nationality
        if marital_status:
            person.marital_status = marital_status
        if personal_email is not None:
            person.personal_email = personal_email
        if mobile_phone is not None:
            person.mobile_phone = mobile_phone
        if residential_address is not None:
            person.residential_address = residential_address
        if permanent_address is not None:
            person.permanent_address = permanent_address
        if emergency_contact_name is not None:
            person.emergency_contact_name = emergency_contact_name
        if emergency_contact_relationship is not None:
            person.emergency_contact_relationship = emergency_contact_relationship
        if emergency_contact_phone is not None:
            person.emergency_contact_phone = emergency_contact_phone
    else:
        # 若有提供身分識別號碼 (如身分證字號)，檢查是否已存在集團 Person
        if national_id and national_id.strip():
            person = db.execute(select(Person).where(Person.national_id == national_id.strip())).scalar_one_or_none()
        
        if not person:
            person = Person(
                national_id=national_id.strip() if national_id else None,
                full_name=full_name,
                english_name=english_name,
                birth_date=birth_date,
                gender=gender,
                nationality=nationality,
                marital_status=marital_status,
                personal_email=personal_email,
                mobile_phone=mobile_phone,
                residential_address=residential_address,
                permanent_address=permanent_address,
                emergency_contact_name=emergency_contact_name,
                emergency_contact_relationship=emergency_contact_relationship,
                emergency_contact_phone=emergency_contact_phone,
            )
            db.add(person)
            db.flush()

    # 2. 檢查同公司工號是否重複 (Company-scoped Employee No check)
    existing_emp = db.execute(
        select(Employee).where(
            Employee.company_id == company_id,
            Employee.employee_no == employee_no,
        )
    ).scalar_one_or_none()
    if existing_emp:
        raise AppException(code="EMPLOYEE_EXISTS", message=f"該公司員工工號 [{employee_no}] 已存在", status_code=409)

    # 3. 檢查同一自然人是否已在本公司任職中 (Prevent Duplicate Active Employment in Same Company)
    existing_active = db.execute(
        select(Employee).where(
            Employee.company_id == company_id,
            Employee.person_id == person.id,
            Employee.status == "ACTIVE",
        )
    ).scalar_one_or_none()
    if existing_active:
        raise AppException(
            code="DUPLICATE_COMPANY_EMPLOYMENT",
            message=f"員工 [{person.full_name}] 目前已於本公司在職中 (工號: {existing_active.employee_no})",
            status_code=409,
        )

    # 4. 建立公司任職記錄 (Create Company Employment Record)
    emp = Employee(
        person_id=person.id,
        employee_no=employee_no,
        company_id=company_id,
        organization_id=organization_id,
        full_name=person.full_name,
        english_name=person.english_name,
        national_id=person.national_id,
        birth_date=person.birth_date,
        gender=person.gender,
        nationality=person.nationality,
        marital_status=person.marital_status,
        email=email,
        personal_email=person.personal_email,
        mobile_phone=person.mobile_phone,
        residential_address=person.residential_address,
        permanent_address=person.permanent_address,
        emergency_contact_name=person.emergency_contact_name,
        emergency_contact_relationship=person.emergency_contact_relationship,
        emergency_contact_phone=person.emergency_contact_phone,
        job_title=job_title,
        job_grade=job_grade,
        employment_type=employment_type,
        default_shift_id=default_shift_id,
        hire_date=hire_date,
        probation_end_date=probation_end_date,
        status="ACTIVE",
    )
    db.add(emp)
    db.commit()
    db.refresh(emp)

    # 寫入到職異動歷史
    change = EmployeeChange(
        employee_id=emp.id,
        change_type="ONBOARD",
        effective_date=hire_date,
        after_organization_id=organization_id,
        notes=f"新進員工報到 [{job_title or '員工'}]",
    )
    db.add(change)

    # 連動開通帳號 (Account Provisioning)
    if create_user_account:
        pwd = initial_password or "Welcome123!"
        user = db.execute(select(User).where((User.username == employee_no) | (User.email == email))).scalar_one_or_none()
        if not user:
            user = User(
                username=employee_no,
                email=email,
                display_name=full_name,
                hashed_password=hash_password(pwd),
                primary_company_id=company_id,
                employee_id=emp.id,
                is_active=True,
                is_first_login=True,
            )
            db.add(user)
            db.flush()

            # 設定公司資料存取範圍
            scope = UserScope(user_id=user.id, company_id=company_id, organization_id=organization_id, scope_type="COMPANY")
            db.add(scope)
        else:
            user.employee_id = emp.id
            user.is_active = True

    db.commit()
    db.refresh(emp)
    return emp


def update_employee_profile(
    db: DbSession,
    employee_id: str,
    update_data: Dict[str, Any],
) -> Employee:
    """
    更新員工基本資料 (Update Employee Profile)
    """
    emp = db.get(Employee, employee_id)
    if not emp:
        raise AppException(code="EMPLOYEE_NOT_FOUND", message="找不到指定員工", status_code=404)

    updatable_fields = [
        "full_name", "english_name", "national_id", "birth_date", "gender", "nationality", "marital_status",
        "personal_email", "mobile_phone", "residential_address", "permanent_address",
        "emergency_contact_name", "emergency_contact_relationship", "emergency_contact_phone",
        "job_title", "job_grade", "employment_type", "default_shift_id", "probation_end_date"
    ]

    for field in updatable_fields:
        if field in update_data and update_data[field] is not None:
            setattr(emp, field, update_data[field])

    emp.version += 1
    db.commit()
    db.refresh(emp)
    return emp


def process_employee_resignation(
    db: DbSession,
    employee_id: str,
    resign_date: date,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """
    員工離職安全聯動處理 (Employee Resignation & Session Revocation)
    1. 切換員工狀態為 RESIGNED，記錄離職日期。
    2. 留存 RESIGN 異動歷程。
    3. 停用關聯使用者帳號 (is_active = False)。
    4. 立即撤銷該使用者在伺服器端所有活動中的 Sessions，防範離職後越權存取。
    """
    emp = db.get(Employee, employee_id)
    if not emp:
        raise AppException(code="EMPLOYEE_NOT_FOUND", message="找不到指定之員工", status_code=404)

    emp.status = "RESIGNED"
    emp.resign_date = resign_date
    emp.version += 1

    change = EmployeeChange(
        employee_id=emp.id,
        change_type="RESIGN",
        effective_date=resign_date,
        before_organization_id=emp.organization_id,
        notes=notes or "員工辦理離職手續",
    )
    db.add(change)

    # 關聯帳號安全處置
    user = db.execute(
        select(User).where((User.employee_id == employee_id) | (User.email == emp.email))
    ).scalar_one_or_none()

    revoked_sessions_count = 0
    if user:
        user.is_active = False
        user.version += 1

        # 撤銷所有有效 sessions
        sessions = db.execute(
            select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.is_revoked == False)
        ).scalars().all()

        now = utc_now()
        for s in sessions:
            s.is_revoked = True
            s.revoked_at = now
            revoked_sessions_count += 1

    db.commit()
    return {
        "status": "success",
        "employee_id": employee_id,
        "employee_status": emp.status,
        "resign_date": resign_date.isoformat(),
        "user_account_disabled": user is not None,
        "revoked_sessions_count": revoked_sessions_count,
    }


class LeaveLedgerService:
    """
    假額不可變帳本服務 (Immutable Leave Ledger Service)
    規約保證：不直接更新或覆寫剩餘值，採流水帳方式紀錄給予、預占、扣抵與釋放。
    """

    @staticmethod
    def get_available_balance(
        db: DbSession,
        employee_id: str,
        leave_type_id: str,
        as_of_date: Optional[date] = None,
    ) -> int:
        """
        計算截至指定日期的可用假額分鐘數 (Available Balance in Minutes)
        可用額度 = (生效中的給予總額 - 核准扣抵總額) - (簽核中預占總額 - 釋放總額)
        """
        today = as_of_date or date.today()

        stmt = (
            select(LeaveLedger)
            .where(
                LeaveLedger.employee_id == employee_id,
                LeaveLedger.leave_type_id == leave_type_id,
                LeaveLedger.valid_from <= today,
                LeaveLedger.valid_to >= today,
            )
        )
        entries = db.execute(stmt).scalars().all()

        total_granted = sum(e.amount_minutes for e in entries if e.entry_type == "GRANT")
        total_committed = sum(e.amount_minutes for e in entries if e.entry_type == "COMMIT")
        total_hold = sum(e.amount_minutes for e in entries if e.entry_type == "HOLD")
        total_released = sum(e.amount_minutes for e in entries if e.entry_type == "RELEASE")

        # 實際剩餘額度 (未扣預占)
        remaining = total_granted - total_committed
        # 當前仍處於預占鎖定的額度
        active_holds = max(0, total_hold - total_released)
        # 可供新假單申請的可用額度
        available = remaining - active_holds

        return max(0, available)

    @staticmethod
    def grant_leave(
        db: DbSession,
        company_id: str,
        employee_id: str,
        leave_type_id: str,
        amount_minutes: int,
        valid_from: date,
        valid_to: date,
        created_by: str,
        reference_doc_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> LeaveLedger:
        """假額給予入帳 (GRANT)"""
        current_bal = LeaveLedgerService.get_available_balance(db, employee_id, leave_type_id, valid_from)
        new_balance = current_bal + amount_minutes

        entry = LeaveLedger(
            company_id=company_id,
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            entry_type="GRANT",
            amount_minutes=amount_minutes,
            balance_after_minutes=new_balance,
            reference_doc_id=reference_doc_id,
            valid_from=valid_from,
            valid_to=valid_to,
            notes=notes or "年度假額給予",
            created_by=created_by,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def hold_leave(
        db: DbSession,
        company_id: str,
        employee_id: str,
        leave_type_id: str,
        amount_minutes: int,
        reference_doc_id: str,
        valid_from: date,
        valid_to: date,
        created_by: str,
    ) -> LeaveLedger:
        """
        送出請假單時預占假額 (HOLD - 防超用原子性保證)
        """
        available = LeaveLedgerService.get_available_balance(db, employee_id, leave_type_id, valid_from)
        if available < amount_minutes:
            raise AppException(
                code="INSUFFICIENT_LEAVE_BALANCE",
                message=f"假額不足：申請需求 {amount_minutes} 分鐘，目前可用餘額僅剩 {available} 分鐘",
                status_code=400,
            )

        entry = LeaveLedger(
            company_id=company_id,
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            entry_type="HOLD",
            amount_minutes=amount_minutes,
            balance_after_minutes=available - amount_minutes,
            reference_doc_id=reference_doc_id,
            valid_from=valid_from,
            valid_to=valid_to,
            notes=f"假單送簽預占 [單號: {reference_doc_id}]",
            created_by=created_by,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def commit_leave(
        db: DbSession,
        company_id: str,
        employee_id: str,
        leave_type_id: str,
        amount_minutes: int,
        reference_doc_id: str,
        valid_from: date,
        valid_to: date,
        created_by: str,
    ) -> LeaveLedger:
        """
        假單核准時扣抵假額 (COMMIT)
        """
        available = LeaveLedgerService.get_available_balance(db, employee_id, leave_type_id, valid_from)
        entry = LeaveLedger(
            company_id=company_id,
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            entry_type="COMMIT",
            amount_minutes=amount_minutes,
            balance_after_minutes=available,
            reference_doc_id=reference_doc_id,
            valid_from=valid_from,
            valid_to=valid_to,
            notes=f"假單核准扣抵 [單號: {reference_doc_id}]",
            created_by=created_by,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def release_leave(
        db: DbSession,
        company_id: str,
        employee_id: str,
        leave_type_id: str,
        amount_minutes: int,
        reference_doc_id: str,
        valid_from: date,
        valid_to: date,
        created_by: str,
    ) -> LeaveLedger:
        """
        假單撤銷或退回時釋放預占額度 (RELEASE)
        """
        available = LeaveLedgerService.get_available_balance(db, employee_id, leave_type_id, valid_from)
        entry = LeaveLedger(
            company_id=company_id,
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            entry_type="RELEASE",
            amount_minutes=amount_minutes,
            balance_after_minutes=available + amount_minutes,
            reference_doc_id=reference_doc_id,
            valid_from=valid_from,
            valid_to=valid_to,
            notes=f"假單退銷釋放預占 [單號: {reference_doc_id}]",
            created_by=created_by,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def get_ledger_entries(
        db: DbSession,
        employee_id: str,
        leave_type_id: Optional[str] = None,
        entry_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[LeaveLedger]:
        """
        查詢員工假額帳本流水清單 (Audit Ledger Entries)
        """
        stmt = select(LeaveLedger).where(LeaveLedger.employee_id == employee_id)
        if leave_type_id:
            stmt = stmt.where(LeaveLedger.leave_type_id == leave_type_id)
        if entry_type:
            stmt = stmt.where(LeaveLedger.entry_type == entry_type)

        stmt = stmt.order_by(desc(LeaveLedger.created_at)).limit(limit)
        return db.execute(stmt).scalars().all()

    @staticmethod
    def get_leave_quota_summary(
        db: DbSession,
        employee_id: str,
        as_of_date: Optional[date] = None,
    ) -> List[Dict[str, Any]]:
        """
        取得員工所有假別之可用假額彙總（換算標準工時 480 分鐘之可用天數）
        """
        emp = db.get(Employee, employee_id)
        if not emp:
            raise AppException(code="EMPLOYEE_NOT_FOUND", message="找不到指定員工", status_code=404)

        leave_types = db.execute(
            select(LeaveType).where(LeaveType.company_id == emp.company_id)
        ).scalars().all()

        today = as_of_date or date.today()
        summary = []

        for lt in leave_types:
            available_min = LeaveLedgerService.get_available_balance(db, employee_id, lt.id, today)
            summary.append({
                "leave_type_id": lt.id,
                "leave_type_code": lt.code,
                "leave_type_name": lt.name,
                "unit": lt.unit,
                "is_paid": lt.is_paid,
                "requires_attachment": lt.requires_attachment,
                "available_minutes": available_min,
                "available_days": round(available_min / 480.0, 2),
                "as_of_date": today.isoformat(),
            })

        return summary


class LeaveEntitlementService:
    """
    年資法定特別休假試算與批次核發服務 (Annual Leave Entitlement Service)
    支援台灣 (勞基法第38條週年制) 與日本 (勞基法第39條年次有給休暇) 法定階梯試算
    """

    @staticmethod
    def calculate_seniority(hire_date: date, as_of_date: date) -> tuple[int, int]:
        """
        計算服務年資 (年數, 月數)
        """
        if as_of_date < hire_date:
            return 0, 0
        total_months = (as_of_date.year - hire_date.year) * 12 + (as_of_date.month - hire_date.month)
        if as_of_date.day < hire_date.day:
            total_months -= 1
        total_months = max(0, total_months)
        years = total_months // 12
        months = total_months % 12
        return years, months

    @staticmethod
    def calculate_entitlement(hire_date: date, as_of_date: date, country: str = "TW") -> dict:
        """
        計算截至 as_of_date 員工法定應有之特休天數與分鐘數 (每日按標準 480 分鐘計算)
        """
        years, months = LeaveEntitlementService.calculate_seniority(hire_date, as_of_date)
        total_months = years * 12 + months
        days = 0.0

        if country == "JP":
            # 日本勞動基準法第39條：
            # 6個月: 10天, 1.5年: 11天, 2.5年: 12天, 3.5年: 14天, 4.5年: 16天, 5.5年: 18天, 6.5年以上: 20天
            if total_months >= 78:  # 6.5年
                days = 20.0
            elif total_months >= 66:  # 5.5年
                days = 18.0
            elif total_months >= 54:  # 4.5年
                days = 16.0
            elif total_months >= 42:  # 3.5年
                days = 14.0
            elif total_months >= 30:  # 2.5年
                days = 12.0
            elif total_months >= 18:  # 1.5年
                days = 11.0
            elif total_months >= 6:  # 6個月
                days = 10.0
            else:
                days = 0.0
            legal_basis = "日本勞基法第39條年次有給休暇基準"
        else:
            # 台灣勞基法第38條週年制：
            # 滿6個月未滿1年: 3天
            # 滿1年未滿2年: 7天
            # 滿2年未滿3年: 10天
            # 滿3年未滿5年: 14天
            # 滿5年未滿10年: 15天
            # 滿10年以上: 每滿1年加1天，上限30天
            if total_months < 6:
                days = 0.0
            elif total_months < 12:
                days = 3.0
            elif years == 1:
                days = 7.0
            elif years == 2:
                days = 10.0
            elif years in (3, 4):
                days = 14.0
            elif 5 <= years < 10:
                days = 15.0
            else:
                days = min(30.0, 15.0 + (years - 9))
            legal_basis = "台灣勞基法第38條特別休假週年制"

        minutes = int(days * 480)
        return {
            "seniority_years": years,
            "seniority_months": months,
            "entitled_days": days,
            "entitled_minutes": minutes,
            "legal_basis": legal_basis,
        }

    @staticmethod
    def get_company_entitlements_preview(
        db: DbSession,
        company_id: str,
        as_of_date: Optional[date] = None,
    ) -> list[dict]:
        """
        試算公司轄下所有在職員工法定特休天數及目前特休帳本餘額
        """
        today = as_of_date or date.today()
        comp = db.get(Company, company_id)
        country = "JP" if comp and ("JP" in comp.id.upper() or "TOKYO" in (comp.default_timezone or "").upper()) else "TW"

        # 找出特別休假 leave_type
        annual_lt = db.execute(
            select(LeaveType).where(
                LeaveType.company_id == company_id,
                LeaveType.code.in_(["ANNUAL", "SPECIAL", "ANNUAL_LEAVE"]),
            )
        ).scalars().first()

        employees = db.execute(
            select(Employee).where(
                Employee.company_id == company_id,
                Employee.status == "ACTIVE",
            ).order_by(Employee.employee_no)
        ).scalars().all()

        results = []
        for emp in employees:
            ent = LeaveEntitlementService.calculate_entitlement(emp.hire_date, today, country=country)
            
            current_bal_min = 0
            if annual_lt:
                current_bal_min = LeaveLedgerService.get_available_balance(db, emp.id, annual_lt.id, today)

            # 檢查今年度是否已有 GRANT 過特休
            already_granted_this_year = False
            if annual_lt:
                existing_grant = db.execute(
                    select(LeaveLedger).where(
                        LeaveLedger.employee_id == emp.id,
                        LeaveLedger.leave_type_id == annual_lt.id,
                        LeaveLedger.entry_type == "GRANT",
                        LeaveLedger.valid_from <= today,
                        LeaveLedger.valid_to >= today,
                    )
                ).scalars().first()
                if existing_grant:
                    already_granted_this_year = True

            results.append({
                "employee_id": emp.id,
                "employee_no": emp.employee_no,
                "full_name": emp.full_name,
                "hire_date": emp.hire_date.isoformat(),
                "seniority_years": ent["seniority_years"],
                "seniority_months": ent["seniority_months"],
                "entitled_days": ent["entitled_days"],
                "entitled_minutes": ent["entitled_minutes"],
                "current_balance_minutes": current_bal_min,
                "current_balance_days": round(current_bal_min / 480.0, 2),
                "legal_basis": ent["legal_basis"],
                "leave_type_id": annual_lt.id if annual_lt else None,
                "already_granted_this_year": already_granted_this_year,
            })

        return results

