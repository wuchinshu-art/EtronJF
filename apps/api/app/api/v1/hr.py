from datetime import date, datetime, timezone
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, status, Query
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from sqlalchemy.orm import Session as DbSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.errors import AppException
from app.api.deps import get_current_user, require_permissions
from app.models.auth import User
from app.models.hr import (
    Company,
    Organization,
    Employee,
    ManagerRelation,
    EmployeeChange,
    Shift,
    CalendarDay,
    LeaveType,
    LeaveLedger,
    Person,
)
from app.core.hr_rules import (
    check_organization_cycle,
    check_manager_cycle,
    LeaveLedgerService,
    onboard_employee,
    process_employee_resignation,
    mask_national_id,
    update_employee_profile,
    search_persons,
    LeaveEntitlementService,
)

router = APIRouter(prefix="/hr", tags=["HR Master"])


# ==========================================
# 1. 公司主檔 (Companies)
# ==========================================
class CompanyCreate(BaseModel):
    id: str = Field(description="公司代碼，例如 ETJ-TW / ETJ-JP")
    name: str
    tax_id: Optional[str] = None
    representative_name: Optional[str] = None
    registered_address: Optional[str] = None
    contact_phone: Optional[str] = None
    default_timezone: str = "Asia/Taipei"
    default_currency: str = "TWD"


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    tax_id: Optional[str] = None
    representative_name: Optional[str] = None
    registered_address: Optional[str] = None
    contact_phone: Optional[str] = None
    default_timezone: Optional[str] = None
    default_currency: Optional[str] = None
    is_active: Optional[bool] = None


class CompanyResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    name: str
    tax_id: Optional[str] = None
    representative_name: Optional[str] = None
    registered_address: Optional[str] = None
    contact_phone: Optional[str] = None
    default_timezone: str
    default_currency: str
    is_active: bool


@router.get("/companies", response_model=List[CompanyResponse])
def list_companies(db: DbSession = Depends(get_db)):
    return list(db.execute(select(Company)).scalars().all())


@router.get("/companies/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: str,
    db: DbSession = Depends(get_db),
):
    comp = db.get(Company, company_id)
    if not comp:
        raise AppException(code="COMPANY_NOT_FOUND", message=f"找不到公司 [{company_id}]", status_code=404)
    return comp


@router.post("/companies", response_model=CompanyResponse, status_code=status.HTTP_201_CREATED)
def create_company(
    req: CompanyCreate,
    current_user: User = Depends(get_current_user),
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    if db.get(Company, req.id):
        raise AppException(code="COMPANY_EXISTS", message=f"公司代碼 [{req.id}] 已存在", status_code=409)

    comp = Company(
        id=req.id,
        name=req.name,
        tax_id=req.tax_id,
        representative_name=req.representative_name,
        registered_address=req.registered_address,
        contact_phone=req.contact_phone,
        default_timezone=req.default_timezone,
        default_currency=req.default_currency,
    )
    db.add(comp)
    db.commit()
    db.refresh(comp)
    return comp


@router.put("/companies/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: str,
    req: CompanyUpdate,
    current_user: User = Depends(get_current_user),
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    comp = db.get(Company, company_id)
    if not comp:
        raise AppException(code="COMPANY_NOT_FOUND", message=f"找不到公司 [{company_id}]", status_code=404)

    update_data = req.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(comp, field, value)

    db.commit()
    db.refresh(comp)
    return comp


# ==========================================
# 2. 組織階層 (Organizations - 含循環驗證與有效日期)
# ==========================================
class OrgCreate(BaseModel):
    id: str
    company_id: str
    code: str
    name: str
    parent_id: Optional[str] = None
    level: str = "DEPARTMENT"
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None


class OrgUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    parent_id: Optional[str] = None
    level: Optional[str] = None
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    is_active: Optional[bool] = None


class OrgResponse(BaseModel):
    id: str
    company_id: str
    code: str
    name: str
    parent_id: Optional[str] = None
    level: str
    effective_date: Optional[date] = None
    expiry_date: Optional[date] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


@router.get("/organizations", response_model=list[OrgResponse])
def list_organizations(
    company_id: Optional[str] = Query(None, description="所屬公司代碼 (留空則查詢全部)"),
    db: DbSession = Depends(get_db),
):
    stmt = select(Organization)
    if company_id:
        stmt = stmt.where(Organization.company_id == company_id)
    stmt = stmt.order_by(Organization.company_id, Organization.code)
    return db.execute(stmt).scalars().all()


@router.post("/organizations", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
def create_organization(
    req: OrgCreate,
    current_user: User = Depends(get_current_user),
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    # 上級部門不能為自己
    if req.parent_id:
        if req.parent_id == req.id:
            raise AppException(code="INVALID_PARENT_ORG", message="上級部門不能為自己", status_code=400)
        check_organization_cycle(db, req.id, req.parent_id)

    # 日期檢查
    if req.effective_date and req.expiry_date and req.effective_date > req.expiry_date:
        raise AppException(code="INVALID_DATE_RANGE", message="有效日期不可大於失效日期", status_code=400)

    # 代碼唯一性檢查
    existing = db.execute(
        select(Organization).where(
            Organization.company_id == req.company_id,
            Organization.code == req.code,
        )
    ).scalar_one_or_none()
    if existing:
        raise AppException(code="ORG_CODE_EXISTS", message=f"部門代號 [{req.code}] 已在該公司存在", status_code=400)

    org = Organization(
        id=req.id,
        company_id=req.company_id,
        code=req.code,
        name=req.name,
        parent_id=req.parent_id,
        level=req.level,
        effective_date=req.effective_date,
        expiry_date=req.expiry_date,
    )
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


@router.put("/organizations/{organization_id}", response_model=OrgResponse)
def update_organization(
    organization_id: str,
    req: OrgUpdate,
    current_user: User = Depends(get_current_user),
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    org = db.get(Organization, organization_id)
    if not org:
        raise AppException(code="ORG_NOT_FOUND", message=f"找不到組織部門 [{organization_id}]", status_code=404)

    # 上級部門驗證與防循環
    if req.parent_id is not None:
        if req.parent_id == organization_id:
            raise AppException(code="INVALID_PARENT_ORG", message="上級部門不能為自己", status_code=400)
        if req.parent_id != "":
            parent_org = db.get(Organization, req.parent_id)
            if not parent_org or parent_org.company_id != org.company_id:
                raise AppException(code="PARENT_ORG_NOT_FOUND", message="無效的上級部門或跨公司歸屬", status_code=400)
            check_organization_cycle(db, organization_id, req.parent_id)
            org.parent_id = req.parent_id
        else:
            org.parent_id = None

    # 日期區間檢查
    eff_date = req.effective_date if req.effective_date is not None else org.effective_date
    exp_date = req.expiry_date if req.expiry_date is not None else org.expiry_date
    if eff_date and exp_date and eff_date > exp_date:
        raise AppException(code="INVALID_DATE_RANGE", message="有效日期不可大於失效日期", status_code=400)

    if req.code is not None and req.code != org.code:
        existing = db.execute(
            select(Organization).where(
                Organization.company_id == org.company_id,
                Organization.code == req.code,
                Organization.id != organization_id,
            )
        ).scalar_one_or_none()
        if existing:
            raise AppException(code="ORG_CODE_EXISTS", message=f"部門代號 [{req.code}] 已在該公司存在", status_code=400)
        org.code = req.code

    if req.name is not None:
        org.name = req.name
    if req.level is not None:
        org.level = req.level
    if req.effective_date is not None:
        org.effective_date = req.effective_date
    if req.expiry_date is not None:
        org.expiry_date = req.expiry_date
    if req.is_active is not None:
        org.is_active = req.is_active

    db.commit()
    db.refresh(org)
    return org


# ==========================================
# 3. 員工主檔與調職、離職、主管關係 (Employees & Lifecycle)
# ==========================================
class PersonResponse(BaseModel):
    id: str
    national_id: Optional[str] = None
    full_name: str
    english_name: Optional[str] = None
    birth_date: Optional[date] = None
    gender: str = "NOT_SPECIFIED"
    nationality: Optional[str] = None
    marital_status: str = "SINGLE"
    blood_type: Optional[str] = None
    military_service_status: Optional[str] = None
    driving_licenses: Optional[str] = None
    transportation_modes: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    contact_phone: Optional[str] = None
    personal_email: Optional[str] = None
    mobile_phone: Optional[str] = None
    residential_address: Optional[str] = None
    permanent_address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_mobile: Optional[str] = None
    education_history: Optional[List[Dict[str, Any]]] = None
    work_experience: Optional[List[Dict[str, Any]]] = None
    employments_count: int = 0
    current_companies: List[str] = []

    model_config = ConfigDict(from_attributes=True)


class PersonCreate(BaseModel):
    full_name: str
    english_name: Optional[str] = None
    national_id: Optional[str] = None
    birth_date: Optional[date] = None
    gender: str = "NOT_SPECIFIED"
    nationality: Optional[str] = None
    marital_status: str = "SINGLE"
    blood_type: Optional[str] = None
    military_service_status: Optional[str] = None
    driving_licenses: Optional[str] = None
    transportation_modes: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    contact_phone: Optional[str] = None
    personal_email: Optional[EmailStr] = None
    mobile_phone: Optional[str] = None
    residential_address: Optional[str] = None
    permanent_address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_mobile: Optional[str] = None
    education_history: Optional[List[Dict[str, Any]]] = None
    work_experience: Optional[List[Dict[str, Any]]] = None


class PersonUpdate(BaseModel):
    full_name: Optional[str] = None
    english_name: Optional[str] = None
    national_id: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    marital_status: Optional[str] = None
    blood_type: Optional[str] = None
    military_service_status: Optional[str] = None
    driving_licenses: Optional[str] = None
    transportation_modes: Optional[str] = None
    height_cm: Optional[int] = None
    weight_kg: Optional[int] = None
    contact_phone: Optional[str] = None
    personal_email: Optional[EmailStr] = None
    mobile_phone: Optional[str] = None
    residential_address: Optional[str] = None
    permanent_address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    emergency_contact_mobile: Optional[str] = None
    education_history: Optional[List[Dict[str, Any]]] = None
    work_experience: Optional[List[Dict[str, Any]]] = None


class EmployeeCreate(BaseModel):
    employee_no: str
    company_id: str
    organization_id: str
    full_name: str
    email: EmailStr
    hire_date: date
    person_id: Optional[str] = None
    english_name: Optional[str] = None
    national_id: Optional[str] = None
    birth_date: Optional[date] = None
    gender: str = "NOT_SPECIFIED"
    nationality: Optional[str] = None
    marital_status: str = "SINGLE"
    personal_email: Optional[EmailStr] = None
    mobile_phone: Optional[str] = None
    residential_address: Optional[str] = None
    permanent_address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    job_title: Optional[str] = None
    job_grade: Optional[str] = None
    employment_type: str = "REGULAR"
    default_shift_id: Optional[str] = None
    probation_end_date: Optional[date] = None
    create_user_account: bool = False
    initial_password: Optional[str] = None


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    english_name: Optional[str] = None
    national_id: Optional[str] = None
    birth_date: Optional[date] = None
    gender: Optional[str] = None
    nationality: Optional[str] = None
    marital_status: Optional[str] = None
    personal_email: Optional[EmailStr] = None
    mobile_phone: Optional[str] = None
    residential_address: Optional[str] = None
    permanent_address: Optional[str] = None
    emergency_contact_name: Optional[str] = None
    emergency_contact_relationship: Optional[str] = None
    emergency_contact_phone: Optional[str] = None
    job_title: Optional[str] = None
    job_grade: Optional[str] = None
    employment_type: Optional[str] = None
    default_shift_id: Optional[str] = None
    probation_end_date: Optional[date] = None


class SetManagerRequest(BaseModel):
    manager_id: str
    relation_type: str = "DIRECT"
    effective_from: date


class TransferEmployeeRequest(BaseModel):
    new_organization_id: Optional[str] = None
    new_job_title: Optional[str] = None
    new_job_grade: Optional[str] = None
    new_default_shift_id: Optional[str] = None
    effective_date: date
    notes: Optional[str] = None


class ResignEmployeeRequest(BaseModel):
    resign_date: date
    notes: Optional[str] = None


# ==========================================
# 2.5 人員個資主檔 (Persons - 集團自然人主檔與多公司任職查詢)
# ==========================================
def build_person_response(p: Person, active_comps: Optional[List[str]] = None) -> PersonResponse:
    comps = active_comps if active_comps is not None else [e.company_id for e in (p.employments or []) if e.status == "ACTIVE"]
    return PersonResponse(
        id=p.id,
        national_id=mask_national_id(p.national_id),
        full_name=p.full_name,
        english_name=p.english_name,
        birth_date=p.birth_date,
        gender=p.gender,
        nationality=p.nationality,
        marital_status=p.marital_status,
        blood_type=p.blood_type,
        military_service_status=p.military_service_status,
        driving_licenses=p.driving_licenses,
        transportation_modes=p.transportation_modes,
        height_cm=p.height_cm,
        weight_kg=p.weight_kg,
        contact_phone=p.contact_phone,
        personal_email=p.personal_email,
        mobile_phone=p.mobile_phone,
        residential_address=p.residential_address,
        permanent_address=p.permanent_address,
        emergency_contact_name=p.emergency_contact_name,
        emergency_contact_relationship=p.emergency_contact_relationship,
        emergency_contact_phone=p.emergency_contact_phone,
        emergency_contact_mobile=p.emergency_contact_mobile,
        education_history=p.education_history or [],
        work_experience=p.work_experience or [],
        employments_count=len(p.employments) if p.employments else 0,
        current_companies=comps,
    )


@router.post("/persons", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
def create_person(
    req: PersonCreate,
    db: DbSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _perm: None = Depends(require_permissions("hr.employee.manage")),
):
    """新增集團人員基本檔案主檔（純個資建檔，不涉及具體公司任職）"""
    if req.national_id and req.national_id.strip():
        existing = db.execute(select(Person).where(Person.national_id == req.national_id.strip())).scalar_one_or_none()
        if existing:
            raise AppException(code="PERSON_EXISTS", message=f"身分識別代號 [{req.national_id}] 之人員檔案已存在", status_code=409)

    person = Person(
        full_name=req.full_name.strip(),
        english_name=req.english_name.strip() if req.english_name else None,
        national_id=req.national_id.strip() if req.national_id else None,
        birth_date=req.birth_date,
        gender=req.gender,
        nationality=req.nationality.strip() if req.nationality else None,
        marital_status=req.marital_status,
        blood_type=req.blood_type.strip() if req.blood_type else None,
        military_service_status=req.military_service_status.strip() if req.military_service_status else None,
        driving_licenses=req.driving_licenses.strip() if req.driving_licenses else None,
        transportation_modes=req.transportation_modes.strip() if req.transportation_modes else None,
        height_cm=req.height_cm,
        weight_kg=req.weight_kg,
        contact_phone=req.contact_phone.strip() if req.contact_phone else None,
        personal_email=req.personal_email,
        mobile_phone=req.mobile_phone,
        residential_address=req.residential_address,
        permanent_address=req.permanent_address,
        emergency_contact_name=req.emergency_contact_name,
        emergency_contact_relationship=req.emergency_contact_relationship,
        emergency_contact_phone=req.emergency_contact_phone,
        emergency_contact_mobile=req.emergency_contact_mobile,
        education_history=req.education_history or [],
        work_experience=req.work_experience or [],
    )
    db.add(person)
    db.commit()
    db.refresh(person)

    return build_person_response(person, [])


@router.get("/persons", response_model=List[PersonResponse])
def list_persons(
    keyword: str = Query("", description="身分證號、姓名、信箱或手機查詢"),
    db: DbSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """搜尋集團人員主檔庫（供跨公司報到與個資維護使用）"""
    persons = search_persons(db, keyword)
    return [build_person_response(p) for p in persons]


@router.get("/persons/{person_id}", response_model=PersonResponse)
def get_person_detail(
    person_id: str,
    db: DbSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取得單一人員個資主檔與現有任職公司清單"""
    p = db.get(Person, person_id)
    if not p:
        raise AppException(code="PERSON_NOT_FOUND", message="找不到指定人員主檔", status_code=404)
    return build_person_response(p)


@router.put("/persons/{person_id}")
def update_person(
    person_id: str,
    req: PersonUpdate,
    db: DbSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    _perm: None = Depends(require_permissions("hr.employee.manage")),
):
    """維護人員個資主檔（連動更新各公司任職顯示）"""
    p = db.get(Person, person_id)
    if not p:
        raise AppException(code="PERSON_NOT_FOUND", message="找不到指定人員主檔", status_code=404)

    update_dict = req.model_dump(exclude_unset=True)
    for field, val in update_dict.items():
        setattr(p, field, val)

    # 同步更新該人員旗下所有 employees 的快照欄位
    for emp in p.employments:
        if "full_name" in update_dict:
            emp.full_name = p.full_name
        if "english_name" in update_dict:
            emp.english_name = p.english_name
        if "national_id" in update_dict:
            emp.national_id = p.national_id
        if "birth_date" in update_dict:
            emp.birth_date = p.birth_date
        if "gender" in update_dict:
            emp.gender = p.gender
        if "nationality" in update_dict:
            emp.nationality = p.nationality
        if "marital_status" in update_dict:
            emp.marital_status = p.marital_status
        if "personal_email" in update_dict:
            emp.personal_email = p.personal_email
        if "mobile_phone" in update_dict:
            emp.mobile_phone = p.mobile_phone
        if "residential_address" in update_dict:
            emp.residential_address = p.residential_address
        if "permanent_address" in update_dict:
            emp.permanent_address = p.permanent_address
        if "emergency_contact_name" in update_dict:
            emp.emergency_contact_name = p.emergency_contact_name
        if "emergency_contact_relationship" in update_dict:
            emp.emergency_contact_relationship = p.emergency_contact_relationship
        if "emergency_contact_phone" in update_dict:
            emp.emergency_contact_phone = p.emergency_contact_phone

    db.commit()
    db.refresh(p)
    return {"status": "success", "message": "人員主檔與各公司任職資料已同步更新"}


@router.get("/employees")
def list_employees(
    company_id: str = Query(..., description="公司代碼"),
    organization_id: Optional[str] = Query(None, description="部門過濾"),
    status_filter: Optional[str] = Query(None, alias="status", description="在職狀態過濾 ACTIVE/ON_LEAVE/RESIGNED"),
    db: DbSession = Depends(get_db),
):
    stmt = select(Employee).where(Employee.company_id == company_id)
    if organization_id:
        stmt = stmt.where(Employee.organization_id == organization_id)
    if status_filter:
        stmt = stmt.where(Employee.status == status_filter)
    return db.execute(stmt).scalars().all()


@router.get("/employees/{employee_id}")
def get_employee_detail(
    employee_id: str,
    current_user: Optional[User] = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """查詢單一員工詳情與直屬主管資訊 (含敏感個資動態遮罩)"""
    emp = db.get(Employee, employee_id)
    if not emp:
        raise AppException(code="EMPLOYEE_NOT_FOUND", message="找不到指定員工", status_code=404)

    # 查詢目前直屬主管
    mgr_stmt = (
        select(ManagerRelation)
        .where(
            ManagerRelation.employee_id == employee_id,
            ManagerRelation.relation_type == "DIRECT",
            (ManagerRelation.effective_to == None) | (ManagerRelation.effective_to >= date.today()),
        )
    )
    direct_mgr_rel = db.execute(mgr_stmt).scalar_one_or_none()
    manager_info = None
    if direct_mgr_rel:
        mgr = db.get(Employee, direct_mgr_rel.manager_id)
        if mgr:
            manager_info = {
                "manager_id": mgr.id,
                "manager_no": mgr.employee_no,
                "manager_name": mgr.full_name,
                "relation_type": direct_mgr_rel.relation_type,
                "effective_from": direct_mgr_rel.effective_from.isoformat(),
            }

    # 檢查是否有已開通之使用者帳號
    user = db.execute(select(User).where((User.employee_id == emp.id) | (User.email == emp.email))).scalar_one_or_none()

    # 敏感個資遮罩防護：身分證字號
    masked_id = mask_national_id(emp.national_id)

    # 查詢該人員於集團其他公司之任職記錄 (Multiple Employments)
    other_employments = []
    if emp.person_id:
        person_employments = db.execute(
            select(Employee).where(Employee.person_id == emp.person_id, Employee.id != emp.id)
        ).scalars().all()
        for oe in person_employments:
            other_employments.append({
                "id": oe.id,
                "company_id": oe.company_id,
                "employee_no": oe.employee_no,
                "job_title": oe.job_title,
                "status": oe.status,
                "hire_date": oe.hire_date.isoformat(),
            })

    person = db.get(Person, emp.person_id) if emp.person_id else None

    return {
        "id": emp.id,
        "person_id": emp.person_id,
        "employee_no": emp.employee_no,
        "company_id": emp.company_id,
        "organization_id": emp.organization_id,
        "organization_name": emp.organization.name if emp.organization else None,
        "department_name": emp.organization.name if emp.organization else None,
        "full_name": emp.full_name,
        "english_name": emp.english_name,
        "national_id": masked_id,
        "birth_date": emp.birth_date.isoformat() if emp.birth_date else None,
        "gender": emp.gender,
        "nationality": emp.nationality,
        "marital_status": emp.marital_status,
        "blood_type": person.blood_type if person else None,
        "military_service_status": person.military_service_status if person else None,
        "driving_licenses": person.driving_licenses if person else None,
        "transportation_modes": person.transportation_modes if person else None,
        "height_cm": person.height_cm if person else None,
        "weight_kg": person.weight_kg if person else None,
        "contact_phone": person.contact_phone if person else None,
        "mobile_phone": emp.mobile_phone or (person.mobile_phone if person else None),
        "personal_email": emp.personal_email or (person.personal_email if person else None),
        "residential_address": emp.residential_address or (person.residential_address if person else None),
        "permanent_address": emp.permanent_address or (person.permanent_address if person else None),
        "emergency_contact_name": emp.emergency_contact_name or (person.emergency_contact_name if person else None),
        "emergency_contact_relationship": emp.emergency_contact_relationship or (person.emergency_contact_relationship if person else None),
        "emergency_contact_phone": emp.emergency_contact_phone or (person.emergency_contact_phone if person else None),
        "emergency_contact_mobile": person.emergency_contact_mobile if person else None,
        "education_history": person.education_history if (person and person.education_history) else [],
        "work_experience": person.work_experience if (person and person.work_experience) else [],
        "email": emp.email,
        "job_title": emp.job_title,
        "job_grade": emp.job_grade,
        "employment_type": emp.employment_type,
        "default_shift_id": emp.default_shift_id,
        "hire_date": emp.hire_date.isoformat(),
        "probation_end_date": emp.probation_end_date.isoformat() if emp.probation_end_date else None,
        "resign_date": emp.resign_date.isoformat() if emp.resign_date else None,
        "status": emp.status,
        "version": emp.version,
        "manager": manager_info,
        "has_user_account": user is not None,
        "is_user_active": user.is_active if user else False,
        "is_first_login": user.is_first_login if user else False,
        "other_employments": other_employments,
    }


@router.put("/employees/{employee_id}")
def update_employee(
    employee_id: str,
    req: EmployeeUpdate,
    current_user: User = Depends(get_current_user),
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    """更新員工基本資料"""
    return update_employee_profile(
        db=db,
        employee_id=employee_id,
        update_data=req.model_dump(exclude_unset=True),
    )


@router.get("/employees/{employee_id}/changes")
def get_employee_changes(
    employee_id: str,
    db: DbSession = Depends(get_db),
):
    """查詢員工生命週期異動歷程（到職、調職、升遷、離職）"""
    emp = db.get(Employee, employee_id)
    if not emp:
        raise AppException(code="EMPLOYEE_NOT_FOUND", message="找不到指定員工", status_code=404)

    stmt = select(EmployeeChange).where(EmployeeChange.employee_id == employee_id).order_by(EmployeeChange.created_at.desc())
    return db.execute(stmt).scalars().all()


@router.post("/employees", status_code=status.HTTP_201_CREATED)
def create_employee(
    req: EmployeeCreate,
    current_user: User = Depends(get_current_user),
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    """新進員工報到建立（支援人員主檔關聯與連動開通系統登入帳號）"""
    return onboard_employee(
        db=db,
        employee_no=req.employee_no,
        company_id=req.company_id,
        organization_id=req.organization_id,
        full_name=req.full_name,
        email=req.email,
        hire_date=req.hire_date,
        person_id=req.person_id,
        english_name=req.english_name,
        national_id=req.national_id,
        birth_date=req.birth_date,
        gender=req.gender,
        nationality=req.nationality,
        marital_status=req.marital_status,
        personal_email=req.personal_email,
        mobile_phone=req.mobile_phone,
        residential_address=req.residential_address,
        permanent_address=req.permanent_address,
        emergency_contact_name=req.emergency_contact_name,
        emergency_contact_relationship=req.emergency_contact_relationship,
        emergency_contact_phone=req.emergency_contact_phone,
        job_title=req.job_title,
        job_grade=req.job_grade,
        employment_type=req.employment_type,
        default_shift_id=req.default_shift_id,
        probation_end_date=req.probation_end_date,
        create_user_account=req.create_user_account,
        initial_password=req.initial_password,
    )


@router.post("/employees/{employee_id}/manager")
def set_employee_manager(
    employee_id: str,
    req: SetManagerRequest,
    current_user: User = Depends(get_current_user),
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    """設定員工主管 (含禁止循環檢驗)"""
    emp = db.get(Employee, employee_id)
    mgr = db.get(Employee, req.manager_id)
    if not emp or not mgr:
        raise AppException(code="EMPLOYEE_NOT_FOUND", message="找不到指定之員工或主管", status_code=404)

    # 執行主管循環檢驗！
    check_manager_cycle(db, employee_id, req.manager_id)

    relation = ManagerRelation(
        employee_id=employee_id,
        manager_id=req.manager_id,
        relation_type=req.relation_type,
        effective_from=req.effective_from,
    )
    db.add(relation)
    db.commit()
    return {"status": "success", "message": "主管設定成功"}


@router.post("/employees/{employee_id}/transfer")
def transfer_employee(
    employee_id: str,
    req: TransferEmployeeRequest,
    current_user: User = Depends(get_current_user),
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    """員工調職：更新組織並留存調職歷史紀錄"""
    emp = db.get(Employee, employee_id)
    if not emp:
        raise AppException(code="EMPLOYEE_NOT_FOUND", message="找不到指定員工", status_code=404)

    before_org = emp.organization_id
    before_title = emp.job_title
    before_shift_id = emp.default_shift_id

    if req.new_organization_id:
        emp.organization_id = req.new_organization_id
    if req.new_job_title is not None:
        emp.job_title = req.new_job_title
    if req.new_job_grade is not None:
        emp.job_grade = req.new_job_grade
    if req.new_default_shift_id is not None:
        if req.new_default_shift_id:
            shift = db.get(Shift, req.new_default_shift_id)
            if not shift:
                raise AppException(code="SHIFT_NOT_FOUND", message="找不到指定之班別", status_code=404)
            emp.default_shift_id = req.new_default_shift_id
        else:
            emp.default_shift_id = None

    emp.version += 1

    note_parts = []
    if req.new_organization_id and req.new_organization_id != before_org:
        note_parts.append(f"調動部門: {req.new_organization_id}")
    if req.new_job_title and req.new_job_title != before_title:
        note_parts.append(f"變更職位/職稱: {req.new_job_title}")
    if req.new_default_shift_id is not None and req.new_default_shift_id != before_shift_id:
        if req.new_default_shift_id:
            shift = db.get(Shift, req.new_default_shift_id)
            shift_name = f"{shift.name} ({shift.code})" if shift else req.new_default_shift_id
            note_parts.append(f"變更班別: {shift_name}")
        else:
            note_parts.append("變更班別: 取消指定預設班別")
    if req.notes:
        note_parts.append(req.notes)

    change = EmployeeChange(
        employee_id=emp.id,
        change_type="TRANSFER",
        effective_date=req.effective_date,
        before_organization_id=before_org,
        after_organization_id=emp.organization_id,
        notes="; ".join(note_parts) if note_parts else "職務異動",
    )
    db.add(change)
    db.commit()
    return {"status": "success", "message": "員工異動作業成功，歷程已留存"}


@router.post("/employees/{employee_id}/resign")
def resign_employee(
    employee_id: str,
    req: ResignEmployeeRequest,
    current_user: User = Depends(get_current_user),
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    """員工離職作業：狀態變更、離職異動歷程、同步停用帳號並撤銷所有 Session"""
    return process_employee_resignation(
        db=db,
        employee_id=employee_id,
        resign_date=req.resign_date,
        notes=req.notes,
    )


# ==========================================
# 4. 班別與工作日曆 (Shifts & Calendar)
# ==========================================
class ShiftCreate(BaseModel):
    id: str
    company_id: str
    code: str
    name: str
    work_start_time: str
    work_end_time: str
    break_start_time: Optional[str] = "12:00"
    break_end_time: Optional[str] = "13:00"
    break_minutes: int = 60
    daily_standard_minutes: int = 480
    flex_minutes: int = 0
    is_overnight: bool = False
    timezone: str = "Asia/Taipei"


class ShiftUpdate(BaseModel):
    code: Optional[str] = None
    name: Optional[str] = None
    work_start_time: Optional[str] = None
    work_end_time: Optional[str] = None
    break_start_time: Optional[str] = None
    break_end_time: Optional[str] = None
    break_minutes: Optional[int] = None
    daily_standard_minutes: Optional[int] = None
    flex_minutes: Optional[int] = None
    is_overnight: Optional[bool] = None
    timezone: Optional[str] = None


class CalendarDayCreate(BaseModel):
    company_id: str
    calendar_date: date
    is_working_day: bool
    holiday_name: Optional[str] = None
    day_type: str = "REGULAR"


@router.post("/shifts", status_code=status.HTTP_201_CREATED)
def create_shift(
    req: ShiftCreate,
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    shift = Shift(
        id=req.id,
        company_id=req.company_id,
        code=req.code,
        name=req.name,
        work_start_time=req.work_start_time,
        work_end_time=req.work_end_time,
        break_start_time=req.break_start_time,
        break_end_time=req.break_end_time,
        break_minutes=req.break_minutes,
        daily_standard_minutes=req.daily_standard_minutes,
        flex_minutes=req.flex_minutes,
        is_overnight=req.is_overnight,
        timezone=req.timezone or "Asia/Taipei",
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return shift


@router.put("/shifts/{shift_id}")
def update_shift(
    shift_id: str,
    req: ShiftUpdate,
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    """編輯 / 調整班別設定 (工作起訖時間、休息區間、彈性工時、標準工時、夜班標記、時區)"""
    shift = db.get(Shift, shift_id)
    if not shift:
        raise AppException(code="SHIFT_NOT_FOUND", message=f"找不到指定班別 [{shift_id}]", status_code=404)

    if req.name is not None:
        shift.name = req.name
    if req.code is not None:
        shift.code = req.code
    if req.work_start_time is not None:
        shift.work_start_time = req.work_start_time
    if req.work_end_time is not None:
        shift.work_end_time = req.work_end_time
    if req.break_start_time is not None:
        shift.break_start_time = req.break_start_time
    if req.break_end_time is not None:
        shift.break_end_time = req.break_end_time
    if req.break_minutes is not None:
        shift.break_minutes = req.break_minutes
    if req.daily_standard_minutes is not None:
        shift.daily_standard_minutes = req.daily_standard_minutes
    if req.flex_minutes is not None:
        shift.flex_minutes = req.flex_minutes
    if req.is_overnight is not None:
        shift.is_overnight = req.is_overnight
    if req.timezone is not None:
        shift.timezone = req.timezone

    db.commit()
    db.refresh(shift)
    return shift


@router.delete("/shifts/{shift_id}")
def delete_shift(
    shift_id: str,
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    """刪除指定班別 (若有員工綁定則拒絕刪除)"""
    shift = db.get(Shift, shift_id)
    if not shift:
        raise AppException(code="SHIFT_NOT_FOUND", message=f"找不到指定班別 [{shift_id}]", status_code=404)

    emp_using = db.query(Employee).filter(Employee.default_shift_id == shift_id).first()
    if emp_using:
        raise AppException(
            code="SHIFT_IN_USE",
            message=f"班別 [{shift.name}] 目前有在職員工（如工號 {emp_using.employee_no}）綁定使用中，無法直接刪除",
            status_code=400,
        )

    db.delete(shift)
    db.commit()
    return {"status": "success", "message": f"班別 [{shift.name}] 已刪除"}


@router.post("/calendar-days", status_code=status.HTTP_201_CREATED)
def create_calendar_day(
    req: CalendarDayCreate,
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    c_day = CalendarDay(
        company_id=req.company_id,
        calendar_date=req.calendar_date,
        is_working_day=req.is_working_day,
        holiday_name=req.holiday_name,
        day_type=req.day_type,
    )
    db.add(c_day)
    db.commit()
    return c_day


# ==========================================
# 5. 假別主檔與假額不可變帳本 (Leave Types & Ledger)
# ==========================================
class LeaveTypeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    company_id: Optional[str] = None
    code: str
    name: str
    unit: str
    requires_attachment: bool
    is_paid: bool
    paid_type: str = "FULL"


class LeaveTypeCreate(BaseModel):
    id: Optional[str] = None
    company_id: Optional[str] = None
    code: str
    name: str
    unit: str = "HALF_HOUR"
    requires_attachment: bool = False
    is_paid: bool = True
    paid_type: Optional[str] = None


class GrantLeaveRequest(BaseModel):
    company_id: str
    employee_id: str
    leave_type_id: str
    amount_minutes: int
    valid_from: date
    valid_to: date
    notes: Optional[str] = None


@router.post("/leave-types", response_model=LeaveTypeResponse, status_code=status.HTTP_201_CREATED)
def create_leave_type(
    req: LeaveTypeCreate,
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    """建立假別（假別為跨公司全域通用主檔，不分公司）"""
    code_upper = req.code.strip().upper()
    existing_code = db.execute(select(LeaveType).where(LeaveType.code == code_upper)).scalar_one_or_none()
    if existing_code:
        raise AppException(
            code="LEAVE_TYPE_CODE_EXISTS",
            message=f"假別代碼 [{code_upper}] 已存在，假別為全域不分公司主檔",
            status_code=400,
        )

    lt_id = req.id or f"LT-{code_upper}"
    existing_id = db.get(LeaveType, lt_id)
    if existing_id:
        raise AppException(
            code="LEAVE_TYPE_ID_EXISTS",
            message=f"假別識別碼 [{lt_id}] 已存在",
            status_code=400,
        )

    paid_type = req.paid_type
    if not paid_type:
        paid_type = "FULL" if req.is_paid else "UNPAID"
    is_paid = (paid_type != "UNPAID")
    
    lt = LeaveType(
        id=lt_id,
        company_id=req.company_id,
        code=code_upper,
        name=req.name.strip(),
        unit=req.unit,
        requires_attachment=req.requires_attachment,
        is_paid=is_paid,
        paid_type=paid_type,
    )
    db.add(lt)
    db.commit()
    db.refresh(lt)
    return lt


@router.delete("/leave-types/{id}", status_code=status.HTTP_200_OK)
def delete_leave_type(
    id: str,
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    """刪除假別（僅限未產生假額帳本或假單紀錄之假別）"""
    lt = db.get(LeaveType, id)
    if not lt:
        raise AppException(code="LEAVE_TYPE_NOT_FOUND", message=f"假別代號 [{id}] 不存在", status_code=404)
    
    # 檢查是否已在帳本中使用
    has_ledger = db.execute(select(LeaveLedger).where(LeaveLedger.leave_type_id == id)).scalars().first()
    if has_ledger:
        raise AppException(code="LEAVE_TYPE_IN_USE", message="該假別已有發放或使用之假額帳本紀錄，不可刪除", status_code=400)
    
    db.delete(lt)
    db.commit()
    return {"message": f"假別 [{id}] 已成功刪除"}


@router.post("/leave-ledger/grant", status_code=status.HTTP_201_CREATED)
def grant_leave(
    req: GrantLeaveRequest,
    current_user: User = Depends(get_current_user),
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    """發放假額至員工帳本 (GRANT)"""
    entry = LeaveLedgerService.grant_leave(
        db=db,
        company_id=req.company_id,
        employee_id=req.employee_id,
        leave_type_id=req.leave_type_id,
        amount_minutes=req.amount_minutes,
        valid_from=req.valid_from,
        valid_to=req.valid_to,
        created_by=current_user.id,
        notes=req.notes,
    )
    return entry


@router.get("/shifts")
def list_shifts(
    company_id: str = Query(..., description="公司代碼"),
    db: DbSession = Depends(get_db),
):
    """查詢公司班別清單"""
    stmt = select(Shift).where(Shift.company_id == company_id)
    return db.execute(stmt).scalars().all()


@router.get("/calendar-days")
def list_calendar_days(
    company_id: str = Query(..., description="公司代碼"),
    start_date: Optional[date] = Query(None, description="起始日期"),
    end_date: Optional[date] = Query(None, description="結束日期"),
    db: DbSession = Depends(get_db),
):
    """查詢公司工作日曆"""
    stmt = select(CalendarDay).where(CalendarDay.company_id == company_id)
    if start_date:
        stmt = stmt.where(CalendarDay.calendar_date >= start_date)
    if end_date:
        stmt = stmt.where(CalendarDay.calendar_date <= end_date)
    stmt = stmt.order_by(CalendarDay.calendar_date)
    return db.execute(stmt).scalars().all()


@router.get("/leave-types", response_model=List[LeaveTypeResponse])
def list_leave_types(
    company_id: Optional[str] = Query(None, description="公司代碼（選填，因假別為全域不分公司主檔，不傳或傳入均回傳全域假別）"),
    db: DbSession = Depends(get_db),
):
    """查詢全域假別清單（不分公司）"""
    stmt = select(LeaveType).order_by(LeaveType.code)
    return db.execute(stmt).scalars().all()



@router.get("/leave-ledger/balance")
def get_leave_balance(
    employee_id: str = Query(...),
    leave_type_id: str = Query(...),
    as_of_date: Optional[date] = None,
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """查詢員工在指定日期之可用假額餘額 (分鐘)"""
    available_minutes = LeaveLedgerService.get_available_balance(
        db=db,
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        as_of_date=as_of_date,
    )
    return {
        "employee_id": employee_id,
        "leave_type_id": leave_type_id,
        "available_minutes": available_minutes,
        "available_days": round(available_minutes / 480.0, 2),  # 以 8 小時 = 480 分鐘換算天數
    }


@router.get("/leave-ledger/entries")
def get_leave_ledger_entries(
    employee_id: str = Query(..., description="員工 ID"),
    leave_type_id: Optional[str] = Query(None, description="假別 ID"),
    entry_type: Optional[str] = Query(None, description="分錄類型 GRANT/HOLD/COMMIT/RELEASE/CANCEL"),
    limit: int = Query(50, le=200, description="最大返回筆數"),
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """查詢員工假額帳本不可變流水紀錄"""
    return LeaveLedgerService.get_ledger_entries(
        db=db,
        employee_id=employee_id,
        leave_type_id=leave_type_id,
        entry_type=entry_type,
        limit=limit,
    )


@router.get("/leave-ledger/summary")
def get_leave_quota_summary(
    employee_id: str = Query(..., description="員工 ID"),
    as_of_date: Optional[date] = Query(None, description="計算基準日"),
    current_user: User = Depends(get_current_user),
    db: DbSession = Depends(get_db),
):
    """取得員工所有假別之可用天數與分鐘數彙總（換算標準工時 480 分鐘）"""
    return LeaveLedgerService.get_leave_quota_summary(
        db=db,
        employee_id=employee_id,
        as_of_date=as_of_date,
    )


class LeaveTypeUpdate(BaseModel):
    name: Optional[str] = None
    unit: Optional[str] = None
    requires_attachment: Optional[bool] = None
    is_paid: Optional[bool] = None
    paid_type: Optional[str] = None


@router.put("/leave-types/{id}", response_model=LeaveTypeResponse)
def update_leave_type(
    id: str,
    req: LeaveTypeUpdate,
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    """更新假別設定"""
    lt = db.get(LeaveType, id)
    if not lt:
        raise AppException(code="LEAVE_TYPE_NOT_FOUND", message=f"假別代號 [{id}] 不存在", status_code=404)
    if req.name is not None:
        lt.name = req.name
    if req.unit is not None:
        lt.unit = req.unit
    if req.requires_attachment is not None:
        lt.requires_attachment = req.requires_attachment
    if req.paid_type is not None:
        lt.paid_type = req.paid_type
        lt.is_paid = (req.paid_type != "UNPAID")
    elif req.is_paid is not None:
        lt.is_paid = req.is_paid
        if not req.is_paid:
            lt.paid_type = "UNPAID"
        elif lt.paid_type == "UNPAID":
            lt.paid_type = "FULL"
    db.commit()
    db.refresh(lt)
    return lt


@router.get("/leave-entitlement/calculate")
def calculate_company_annual_leave_entitlements(
    company_id: str = Query(..., description="公司代碼"),
    as_of_date: Optional[date] = Query(None, description="計算基準日"),
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    """
    計算全公司在職員工截至指定基準日之法定特休試算清冊 (年資、應給天數、換算分鐘數、目前帳本餘額與是否已給)
    """
    return LeaveEntitlementService.get_company_entitlements_preview(
        db=db,
        company_id=company_id,
        as_of_date=as_of_date,
    )


class SingleGrantItem(BaseModel):
    employee_id: str
    leave_type_id: str
    amount_minutes: int
    valid_from: date
    valid_to: date
    notes: Optional[str] = None


class BatchGrantAnnualLeaveRequest(BaseModel):
    company_id: str
    grants: List[SingleGrantItem]
    batch_notes: Optional[str] = "年度年資法定特別休假核發"


@router.post("/leave-entitlement/grant-batch")
def grant_batch_annual_leave(
    req: BatchGrantAnnualLeaveRequest,
    current_user: User = Depends(get_current_user),
    _perm: None = Depends(require_permissions("hr.employee.manage")),
    db: DbSession = Depends(get_db),
):
    """
    批次或單筆發放法定特休至假額不可變帳本 (GRANT)
    """
    created_entries = []
    for g in req.grants:
        entry = LeaveLedgerService.grant_leave(
            db=db,
            company_id=req.company_id,
            employee_id=g.employee_id,
            leave_type_id=g.leave_type_id,
            amount_minutes=g.amount_minutes,
            valid_from=g.valid_from,
            valid_to=g.valid_to,
            created_by=current_user.id,
            notes=g.notes or req.batch_notes,
        )
        created_entries.append(entry.id)
    return {
        "status": "success",
        "granted_count": len(created_entries),
        "ledger_ids": created_entries,
    }

