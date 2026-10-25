import json
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, status, Request, UploadFile, File, Form, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from app.core.database import get_db
from app.core.errors import AppException
from app.api.deps import get_current_user
from app.models.auth import User
from app.models.attendance import AttendanceImportBatch, AttendanceCorrection, AttendanceEvent
from app.models.hr import Company, Employee
from app.core.attendance_service import AttendanceService

router = APIRouter(prefix="/attendance", tags=["Attendance & Imports"])


# ==============================================================================
# Pydantic Schemas
# ==============================================================================
class AttendanceUploadJson(BaseModel):
    company_id: str
    file_name: str
    file_content_base64: Optional[str] = None
    file_text: Optional[str] = None
    file_format: str = "CSV"
    encoding: str = "UTF-8"
    source_timezone: str = "Asia/Taipei"
    datetime_format: str = "%Y-%m-%d %H:%M:%S"
    column_mapping: Optional[Dict[str, str]] = None


class AttendanceCommitRequest(BaseModel):
    preview_revision: str


class AttendanceCorrectionCreate(BaseModel):
    company_id: str
    employee_id: str
    work_date: date
    correction_type: str  # SUPPLEMENT, MODIFY, VOID
    corrected_event_at: datetime
    event_type: str
    reason: str
    original_event_id: Optional[str] = None


# ==============================================================================
# Endpoints
# ==============================================================================
@router.post("/imports/upload", status_code=status.HTTP_201_CREATED)
async def upload_attendance_file(
    request: Request,
    company_id: Optional[str] = Form(None),
    encoding: Optional[str] = Form("UTF-8"),
    source_timezone: Optional[str] = Form("Asia/Taipei"),
    datetime_format: Optional[str] = Form("%Y-%m-%d %H:%M:%S"),
    column_mapping: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
    db: DbSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """上傳出勤檔案 (支援 Multipart Form 與 JSON Base64/Text 兩種模式)"""
    file_bytes = b""
    file_name = "attendance.csv"
    file_format = "CSV"
    comp_id = company_id
    enc = encoding or "UTF-8"
    src_tz = source_timezone or "Asia/Taipei"
    dt_fmt = datetime_format or "%Y-%m-%d %H:%M:%S"
    mapping_dict = None

    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        body = await request.json()
        comp_id = body.get("company_id")
        file_name = body.get("file_name", "attendance.csv")
        file_format = body.get("file_format", "CSV")
        enc = body.get("encoding", "UTF-8")
        src_tz = body.get("source_timezone", "Asia/Taipei")
        dt_fmt = body.get("datetime_format", "%Y-%m-%d %H:%M:%S")
        mapping_dict = body.get("column_mapping")

        if body.get("file_text") is not None:
            file_bytes = body["file_text"].encode(enc)
        elif body.get("file_content_base64"):
            import base64
            file_bytes = base64.b64decode(body["file_content_base64"])
    elif file:
        file_name = file.filename
        file_bytes = await file.read()
        if file_name.lower().endswith(".xlsx"):
            file_format = "XLSX"
        elif file_name.lower().endswith(".tsv"):
            file_format = "TSV"
        elif file_name.lower().endswith(".txt"):
            file_format = "TXT"
        else:
            file_format = "CSV"
        if column_mapping:
            try:
                mapping_dict = json.loads(column_mapping)
            except Exception:
                mapping_dict = None

    if not comp_id:
        raise AppException(code="MISSING_COMPANY_ID", message="company_id 為必填欄位", status_code=400)

    # 權限隔離驗證：禁止跨越所屬公司權限
    if current_user.primary_company_id and current_user.primary_company_id != comp_id:
        raise AppException(code="FORBIDDEN_COMPANY_SCOPE", message="無權匯入非所屬公司之出勤檔案", status_code=403)

    batch = AttendanceService.upload_and_parse_batch(
        db=db,
        company_id=comp_id,
        user_id=current_user.id,
        file_name=file_name,
        file_bytes=file_bytes,
        file_format=file_format,
        encoding=enc,
        source_timezone=src_tz,
        datetime_format=dt_fmt,
        column_mapping=mapping_dict,
    )

    return {
        "batch_id": batch.id,
        "batch_no": batch.batch_no,
        "company_id": batch.company_id,
        "file_name": batch.file_name,
        "file_hash": batch.file_hash,
        "file_format": batch.file_format,
        "encoding": batch.encoding,
        "status": batch.status,
        "total_rows": batch.total_rows,
        "created_at": batch.created_at.isoformat(),
    }


@router.post("/imports/{batch_id}/preview")
def preview_and_validate_import(
    batch_id: str,
    db: DbSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """預覽與驗證匯入資料 (Preview & Validate Pipeline)"""
    batch = db.get(AttendanceImportBatch, batch_id)
    if not batch:
        raise AppException(code="BATCH_NOT_FOUND", message=f"匯入批次 '{batch_id}' 不存在", status_code=404)

    if current_user.primary_company_id and current_user.primary_company_id != batch.company_id:
        raise AppException(code="FORBIDDEN_COMPANY_SCOPE", message="無權操作非所屬公司之匯入批次", status_code=403)

    result = AttendanceService.preview_and_validate(db, batch_id=batch_id, company_id=batch.company_id)
    return result


@router.post("/imports/{batch_id}/commit")
def commit_attendance_import(
    batch_id: str,
    payload: AttendanceCommitRequest,
    db: DbSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """確認入庫 (Commit Batch - 必須具備未過期之預覽修訂版本號)"""
    batch = db.get(AttendanceImportBatch, batch_id)
    if not batch:
        raise AppException(code="BATCH_NOT_FOUND", message=f"匯入批次 '{batch_id}' 不存在", status_code=404)

    if current_user.primary_company_id and current_user.primary_company_id != batch.company_id:
        raise AppException(code="FORBIDDEN_COMPANY_SCOPE", message="無權操作非所屬公司之匯入批次", status_code=403)

    result = AttendanceService.commit_batch(
        db=db,
        batch_id=batch_id,
        company_id=batch.company_id,
        user_id=current_user.id,
        preview_revision=payload.preview_revision,
    )
    return result


@router.get("/imports/{batch_id}/errors")
def get_import_errors(
    batch_id: str,
    db: DbSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """取得匯入批次逐列錯誤報告 (Error Report)"""
    batch = db.get(AttendanceImportBatch, batch_id)
    if not batch:
        raise AppException(code="BATCH_NOT_FOUND", message=f"匯入批次 '{batch_id}' 不存在", status_code=404)

    if current_user.primary_company_id and current_user.primary_company_id != batch.company_id:
        raise AppException(code="FORBIDDEN_COMPANY_SCOPE", message="無權存取非所屬公司之錯誤報告", status_code=403)

    return {
        "batch_id": batch.id,
        "batch_no": batch.batch_no,
        "total_rows": batch.total_rows,
        "invalid_rows": batch.invalid_rows,
        "duplicate_rows": batch.duplicate_rows,
        "errors": batch.error_summary or [],
    }


@router.get("/events")
def query_attendance_events(
    company_id: str,
    employee_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    is_abnormal: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: DbSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """查詢出勤打卡事件列表 (公司範圍物件授權隔離)"""
    if current_user.primary_company_id and current_user.primary_company_id != company_id:
        raise AppException(code="FORBIDDEN_COMPANY_SCOPE", message="無權查詢非所屬公司之出勤事件", status_code=403)

    items, total = AttendanceService.query_events(
        db=db,
        company_id=company_id,
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
        is_abnormal=is_abnormal,
        limit=limit,
        offset=offset,
    )
    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/events/export")
def export_attendance_events_csv(
    company_id: str,
    employee_id: Optional[str] = Query(None),
    start_date: Optional[date] = Query(None),
    end_date: Optional[date] = Query(None),
    db: DbSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """匯出出勤事件 CSV (具備 CSV 公式注入防護)"""
    if current_user.primary_company_id and current_user.primary_company_id != company_id:
        raise AppException(code="FORBIDDEN_COMPANY_SCOPE", message="無權匯出非所屬公司之出勤資料", status_code=403)

    csv_data = AttendanceService.export_events_csv(
        db=db,
        company_id=company_id,
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
    )

    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=attendance_events_{company_id}.csv"
        },
    )


@router.post("/corrections", status_code=status.HTTP_201_CREATED)
def create_attendance_correction(
    payload: AttendanceCorrectionCreate,
    db: DbSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """登記考勤打卡修正 (補打卡 / 時間調整，原始事件不可覆寫)"""
    if current_user.primary_company_id and current_user.primary_company_id != payload.company_id:
        raise AppException(code="FORBIDDEN_COMPANY_SCOPE", message="無權操作非所屬公司之考勤修正", status_code=403)

    corr = AttendanceService.create_correction(
        db=db,
        company_id=payload.company_id,
        employee_id=payload.employee_id,
        approver_id=current_user.id,
        work_date=payload.work_date,
        correction_type=payload.correction_type,
        corrected_event_at=payload.corrected_event_at,
        event_type=payload.event_type,
        reason=payload.reason,
        original_event_id=payload.original_event_id,
    )
    return {
        "id": corr.id,
        "company_id": corr.company_id,
        "employee_id": corr.employee_id,
        "work_date": corr.work_date.isoformat(),
        "correction_type": corr.correction_type,
        "corrected_event_at": corr.corrected_event_at.isoformat(),
        "event_type": corr.event_type,
        "reason": corr.reason,
        "status": corr.status,
        "created_at": corr.created_at.isoformat(),
    }


class AttendancePunchRequest(BaseModel):
    company_id: str
    employee_id: Optional[str] = None
    event_type: str = "CHECK_IN"  # CHECK_IN (上班), CHECK_OUT (下班)
    source_timezone: Optional[str] = "Asia/Taipei"


@router.post("/punch", status_code=status.HTTP_201_CREATED)
def punch_attendance(
    payload: AttendancePunchRequest,
    db: DbSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """即時在線打卡 (上班 CHECK_IN / 下班 CHECK_OUT)"""
    comp = db.get(Company, payload.company_id)
    if not comp:
        raise AppException(code="COMPANY_NOT_FOUND", message="查無所屬公司", status_code=404)

    emp_id = payload.employee_id or current_user.employee_id
    if not emp_id:
        # 若未指定且帳號未綁定，找該公司任一在職員工
        emp = db.query(Employee).filter(Employee.company_id == payload.company_id, Employee.status == "ACTIVE").first()
        if not emp:
            raise AppException(code="NO_EMPLOYEE_FOUND", message="該公司尚無在職員工", status_code=400)
        emp_id = emp.id

    from zoneinfo import ZoneInfo
    tz_str = payload.source_timezone or comp.timezone or "Asia/Taipei"
    tz = ZoneInfo(tz_str)
    now_utc = datetime.now(timezone.utc)
    now_local = now_utc.astimezone(tz)

    event = AttendanceEvent(
        company_id=payload.company_id,
        employee_id=emp_id,
        event_at=now_utc,
        source_timezone=tz_str,
        raw_event_at_str=now_local.strftime("%Y-%m-%d %H:%M:%S"),
        event_type=payload.event_type,
        device_id="WEB_PORTAL",
        work_date=now_local.date(),
        is_overnight=False,
        is_abnormal=False,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return {
        "status": "success",
        "id": event.id,
        "employee_id": event.employee_id,
        "event_type": event.event_type,
        "event_at": event.event_at.isoformat(),
        "local_time_str": event.raw_event_at_str,
        "work_date": event.work_date.isoformat(),
        "source_timezone": event.source_timezone,
    }

