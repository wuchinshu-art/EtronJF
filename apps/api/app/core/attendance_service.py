import csv
import hashlib
import io
import uuid
from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import List, Dict, Any, Optional, Tuple

import openpyxl
from sqlalchemy.orm import Session
from sqlalchemy import select, and_, or_, func

from app.core.errors import AppError
from app.core.time import parse_company_date_only
from app.models.hr import Company, Employee, Shift
from app.models.attendance import (
    ShiftAssignment,
    AttendanceImportBatch,
    AttendanceImportRow,
    AttendanceEvent,
    AttendanceCorrection,
    AttendanceDailySummary,
)


SUPPORTED_ENCODINGS = ["UTF-8", "UTF-8-SIG", "CP950", "Shift_JIS"]
VALID_EVENT_TYPES = {"CHECK_IN", "CHECK_OUT", "BREAK_START", "BREAK_END", "OTHER"}


class AttendanceService:
    """出勤匯入、驗證入庫與考勤查詢領域服務 (Attendance Import & Query Service)"""

    @staticmethod
    def _sanitize_csv_cell(value: Any) -> str:
        """防止 CSV 公式注入 (CSV Formula Injection Protection)
        若字串以 =, +, -, @ 開頭，添加單引號 ' 前綴以防止試算表軟體當作公式執行
        """
        if value is None:
            return ""
        str_val = str(value)
        if str_val and str_val[0] in ("=", "+", "-", "@", "\t", "\r"):
            return f"'{str_val}"
        return str_val

    @classmethod
    def upload_and_parse_batch(
        cls,
        db: Session,
        company_id: str,
        user_id: str,
        file_name: str,
        file_bytes: bytes,
        file_format: str,
        encoding: str = "UTF-8",
        source_timezone: str = "Asia/Taipei",
        datetime_format: str = "%Y-%m-%d %H:%M:%S",
        column_mapping: Optional[Dict[str, str]] = None,
    ) -> AttendanceImportBatch:
        """1. 上傳檔案、計算 Hash、依編碼解析並建立預覽待驗證批次 (Upload & Parse Batch)"""
        company = db.get(Company, company_id)
        if not company:
            raise AppError(code="COMPANY_NOT_FOUND", message=f"Company '{company_id}' not found", status_code=404)

        norm_encoding = encoding.strip().upper()
        # 規約：文字支援明確指定 UTF-8／UTF-8 BOM／CP950／Shift_JIS，不靜默用猜測結果入庫
        matched_enc = None
        for enc in SUPPORTED_ENCODINGS:
            if enc.upper() == norm_encoding or enc.replace("-", "").upper() == norm_encoding.replace("-", ""):
                matched_enc = enc
                break
        if not matched_enc:
            raise AppError(
                code="UNSUPPORTED_ENCODING",
                message=f"不支援的編碼 '{encoding}'。僅支援明確指定: {', '.join(SUPPORTED_ENCODINGS)}",
                status_code=400,
            )

        # 計算 SHA-256 檔案雜湊
        file_hash = hashlib.sha256(file_bytes).hexdigest()

        # 解析檔案內容
        file_format_upper = file_format.strip().upper()
        parsed_rows: List[Dict[str, Any]] = []

        if file_format_upper in ("CSV", "TSV", "TXT"):
            delimiter = "\t" if file_format_upper == "TSV" else ","
            try:
                text_content = file_bytes.decode(matched_enc)
            except UnicodeDecodeError as e:
                raise AppError(
                    code="INVALID_ENCODING",
                    message=f"檔案無法以指定編碼 '{matched_enc}' 正確解碼: {str(e)}",
                    status_code=400,
                )
            
            reader = csv.reader(io.StringIO(text_content), delimiter=delimiter)
            header = None
            for row_idx, row in enumerate(reader, start=1):
                if not row or not any(field.strip() for field in row):
                    continue
                if header is None:
                    header = [h.strip() for h in row]
                    continue
                row_dict = {}
                for col_idx, col_name in enumerate(header):
                    val = row[col_idx].strip() if col_idx < len(row) else ""
                    row_dict[col_name] = val
                parsed_rows.append(row_dict)

        elif file_format_upper in ("XLSX", "EXCEL"):
            try:
                wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
                ws = wb.active
                header = None
                for row_idx, row in enumerate(ws.iter_rows(values_only=True), start=1):
                    if not row or not any(field is not None for field in row):
                        continue
                    if header is None:
                        header = [str(h).strip() if h is not None else f"col_{i}" for i, h in enumerate(row)]
                        continue
                    row_dict = {}
                    for col_idx, col_name in enumerate(header):
                        val = row[col_idx] if col_idx < len(row) else None
                        row_dict[col_name] = str(val).strip() if val is not None else ""
                    parsed_rows.append(row_dict)
            except Exception as e:
                raise AppError(
                    code="INVALID_XLSX_FILE",
                    message=f"無法解析 Excel 檔案內容: {str(e)}",
                    status_code=400,
                )
        else:
            raise AppError(
                code="UNSUPPORTED_FORMAT",
                message=f"不支援的檔案格式 '{file_format}'。支援: CSV, XLSX, TSV, TXT",
                status_code=400,
            )

        if not parsed_rows:
            raise AppError(code="EMPTY_IMPORT_FILE", message="匯入檔案中無有效資料列", status_code=400)

        # 欄位映射對齊 (Mapping)
        mapping = column_mapping or {}
        # 預設名稱對照
        emp_col = mapping.get("employee_no") or "employee_no"
        time_col = mapping.get("event_at") or "event_at"
        type_col = mapping.get("event_type") or "event_type"
        dev_col = mapping.get("device_id") or "device_id"
        src_id_col = mapping.get("source_event_id") or "source_event_id"

        batch_id = str(uuid.uuid4())
        batch_no = f"ATT-BATCH-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

        batch = AttendanceImportBatch(
            id=batch_id,
            batch_no=batch_no,
            company_id=company_id,
            file_name=file_name,
            file_hash=file_hash,
            file_format=file_format_upper,
            encoding=matched_enc,
            source_timezone=source_timezone,
            datetime_format=datetime_format,
            status="PENDING_PREVIEW",
            total_rows=len(parsed_rows),
            created_by=user_id,
        )
        db.add(batch)

        for row_idx, r in enumerate(parsed_rows, start=1):
            emp_val = r.get(emp_col, "").strip()
            time_val = r.get(time_col, "").strip()
            type_val = r.get(type_col, "").strip().upper() if r.get(type_col) else "CHECK_IN"
            dev_val = r.get(dev_col, "").strip() if r.get(dev_col) else None
            src_id_val = r.get(src_id_col, "").strip() if r.get(src_id_col) else None

            row_entity = AttendanceImportRow(
                id=str(uuid.uuid4()),
                batch_id=batch_id,
                row_no=row_idx,
                raw_values=r,
                employee_no=emp_val,
                event_at_str=time_val,
                event_type=type_val,
                device_id=dev_val,
                source_event_id=src_id_val,
                status="VALID",
            )
            db.add(row_entity)

        db.commit()
        db.refresh(batch)
        return batch

    @classmethod
    def resolve_work_date_for_punch(
        cls,
        db: Session,
        company_id: str,
        employee_id: str,
        event_local_dt: datetime,
    ) -> Tuple[date, bool]:
        """判定打卡歸屬工作日與是否為跨夜班 (Resolve Work Date & Overnight attribution)
        規則：若員工所屬排班為跨夜班 (例如 20:00 ~ 04:00+1)，
        在凌晨 (00:00 至中午 12:00 前) 之打卡，依排班歸屬前一日之工作日曆 work_date
        """
        event_calendar_date = event_local_dt.date()
        prev_calendar_date = event_calendar_date - timedelta(days=1)

        # 優先查詢昨日之排班指派
        prev_assignment = db.scalar(
            select(ShiftAssignment).where(
                ShiftAssignment.company_id == company_id,
                ShiftAssignment.employee_id == employee_id,
                ShiftAssignment.work_date == prev_calendar_date,
            )
        )
        if prev_assignment:
            shift = db.get(Shift, prev_assignment.shift_id)
            if shift and shift.is_overnight:
                # 凌晨至午前打卡視為跨夜班打卡，歸屬前一天
                if event_local_dt.time() < time(12, 0):
                    return prev_calendar_date, True

        # 次之檢查今日之排班指派
        today_assignment = db.scalar(
            select(ShiftAssignment).where(
                ShiftAssignment.company_id == company_id,
                ShiftAssignment.employee_id == employee_id,
                ShiftAssignment.work_date == event_calendar_date,
            )
        )
        if today_assignment:
            shift = db.get(Shift, today_assignment.shift_id)
            if shift and shift.is_overnight:
                # 若為跨夜班且在排班起始時間之後
                return event_calendar_date, True

        return event_calendar_date, False

    @classmethod
    def preview_and_validate(
        cls,
        db: Session,
        batch_id: str,
        company_id: str,
    ) -> Dict[str, Any]:
        """2. 預覽與資料驗證 (Preview & Validation Pipeline)
        驗證員工工號、時間格式與時區轉換、打卡類型合法性、跨夜班排班歸屬、同批與歷史重複事件去重
        """
        batch = db.get(AttendanceImportBatch, batch_id)
        if not batch or batch.company_id != company_id:
            raise AppError(code="BATCH_NOT_FOUND", message=f"匯入批次 '{batch_id}' 不存在", status_code=404)

        if batch.status == "COMMITTED":
            raise AppError(code="BATCH_ALREADY_COMMITTED", message="該批次已確認入庫，不可重複預覽驗證", status_code=400)

        rows = db.scalars(
            select(AttendanceImportRow)
            .where(AttendanceImportRow.batch_id == batch_id)
            .order_by(AttendanceImportRow.row_no)
        ).all()

        try:
            tz = ZoneInfo(batch.source_timezone)
        except Exception:
            tz = ZoneInfo("Asia/Taipei")

        valid_count = 0
        invalid_count = 0
        duplicate_count = 0
        preview_items = []
        error_items = []

        # 批次內去重集合 (避免同一檔案多列重複打卡)
        seen_in_batch_events = set()
        seen_in_batch_devices = set()

        # 快取員工資料以優化大量驗證效能
        employees = {
            emp.employee_no: emp
            for emp in db.scalars(select(Employee).where(Employee.company_id == company_id)).all()
        }

        for r in rows:
            row_errors = []
            normalized = {}

            # 1. 檢查員工工號
            emp = employees.get(r.employee_no)
            if not emp:
                row_errors.append({"code": "EMPLOYEE_NOT_FOUND", "message": f"員工工號 '{r.employee_no}' 不存在或非屬該公司"})
            else:
                normalized["employee_id"] = emp.id
                normalized["employee_name"] = emp.full_name

            # 2. 檢查打卡時間
            event_utc_dt = None
            work_date = None
            is_overnight = False
            if not r.event_at_str:
                row_errors.append({"code": "MISSING_EVENT_TIME", "message": "打卡時間為必填欄位"})
            else:
                try:
                    local_dt = datetime.strptime(r.event_at_str, batch.datetime_format)
                    local_dt_tz = local_dt.replace(tzinfo=tz)
                    event_utc_dt = local_dt_tz.astimezone(timezone.utc)
                    normalized["event_at_utc"] = event_utc_dt.isoformat()
                    normalized["local_time"] = local_dt.strftime("%Y-%m-%d %H:%M:%S")

                    if emp:
                        work_date, is_overnight = cls.resolve_work_date_for_punch(
                            db, company_id, emp.id, local_dt
                        )
                        normalized["work_date"] = work_date.isoformat()
                        normalized["is_overnight"] = is_overnight
                except Exception as e:
                    row_errors.append({
                        "code": "INVALID_DATETIME_FORMAT",
                        "message": f"時間格式錯誤，無法以 '{batch.datetime_format}' 解析 '{r.event_at_str}': {str(e)}",
                    })

            # 3. 檢查打卡類型
            ev_type = r.event_type.upper() if r.event_type else "CHECK_IN"
            if ev_type not in VALID_EVENT_TYPES:
                row_errors.append({
                    "code": "INVALID_EVENT_TYPE",
                    "message": f"無效打卡類型 '{ev_type}'。支援: {', '.join(VALID_EVENT_TYPES)}",
                })
            normalized["event_type"] = ev_type

            # 4. 去重檢查 (De-duplication)
            is_duplicate = False
            if emp and event_utc_dt:
                # 設備識別碼去重
                if r.device_id and r.source_event_id:
                    dev_key = (r.device_id, r.source_event_id)
                    if dev_key in seen_in_batch_devices:
                        is_duplicate = True
                        row_errors.append({
                            "code": "DUPLICATE_DEVICE_EVENT_IN_BATCH",
                            "message": f"同批檔案內已存在相同設備事件 ID: {r.device_id}-{r.source_event_id}",
                        })
                    else:
                        seen_in_batch_devices.add(dev_key)
                        existing_dev_ev = db.scalar(
                            select(AttendanceEvent).where(
                                AttendanceEvent.company_id == company_id,
                                AttendanceEvent.device_id == r.device_id,
                                AttendanceEvent.source_event_id == r.source_event_id,
                            )
                        )
                        if existing_dev_ev:
                            is_duplicate = True
                            row_errors.append({
                                "code": "DUPLICATE_DEVICE_EVENT_HISTORICAL",
                                "message": f"歷史紀錄中已存在相同設備事件 ID: {r.device_id}-{r.source_event_id}",
                            })

                # 自然鍵去重 (company + employee + event_at_utc)
                nat_key = (emp.id, event_utc_dt)
                if nat_key in seen_in_batch_events:
                    is_duplicate = True
                    row_errors.append({
                        "code": "DUPLICATE_NATURAL_KEY_IN_BATCH",
                        "message": f"同批檔案內已存在員工相同時間之打卡事件",
                    })
                else:
                    seen_in_batch_events.add(nat_key)
                    existing_nat_ev = db.scalar(
                        select(AttendanceEvent).where(
                            AttendanceEvent.company_id == company_id,
                            AttendanceEvent.employee_id == emp.id,
                            AttendanceEvent.event_at == event_utc_dt,
                        )
                    )
                    if existing_nat_ev:
                        is_duplicate = True
                        row_errors.append({
                            "code": "DUPLICATE_NATURAL_KEY_HISTORICAL",
                            "message": "歷史紀錄中已存在該員工相同時間之打卡事件 (自然鍵重複)",
                        })

            # 更新該列狀態與正規化快照
            r.normalized_values = normalized
            if is_duplicate:
                r.status = "SKIPPED_DUPLICATE"
                r.error_codes = row_errors
                duplicate_count += 1
                error_items.append({"row_no": r.row_no, "errors": row_errors, "raw": r.raw_values})
            elif row_errors:
                r.status = "INVALID"
                r.error_codes = row_errors
                invalid_count += 1
                error_items.append({"row_no": r.row_no, "errors": row_errors, "raw": r.raw_values})
            else:
                r.status = "VALID"
                r.error_codes = None
                valid_count += 1
                if len(preview_items) < 50:  # 預覽最多回傳前 50 筆
                    preview_items.append({
                        "row_no": r.row_no,
                        "employee_no": r.employee_no,
                        "employee_name": normalized.get("employee_name"),
                        "event_at": normalized.get("local_time"),
                        "event_type": normalized.get("event_type"),
                        "work_date": normalized.get("work_date"),
                        "is_overnight": normalized.get("is_overnight"),
                        "device_id": r.device_id,
                    })

        # 計算唯一預覽版本號 (防止使用過期預覽快照提交入庫)
        preview_rev = f"REV-{hashlib.sha256(f'{batch_id}-{valid_count}-{datetime.now(timezone.utc).isoformat()}'.encode()).hexdigest()[:12]}"

        batch.valid_rows = valid_count
        batch.invalid_rows = invalid_count
        batch.duplicate_rows = duplicate_count
        batch.preview_revision = preview_rev
        batch.preview_data = preview_items
        batch.error_summary = error_items
        batch.status = "VALIDATED"

        db.commit()

        return {
            "batch_id": batch.id,
            "batch_no": batch.batch_no,
            "status": batch.status,
            "preview_revision": preview_rev,
            "total_rows": batch.total_rows,
            "valid_rows": valid_count,
            "invalid_rows": invalid_count,
            "duplicate_rows": duplicate_count,
            "preview_samples": preview_items,
            "errors": error_items,
        }

    @classmethod
    def commit_batch(
        cls,
        db: Session,
        batch_id: str,
        company_id: str,
        user_id: str,
        preview_revision: str,
    ) -> Dict[str, Any]:
        """3. 確認入庫 (Commit Batch)
        校驗預覽修訂版本，將 VALID 狀態之打卡列原子性寫入 attendance_events (不可覆寫原始事件)
        """
        batch = db.get(AttendanceImportBatch, batch_id)
        if not batch or batch.company_id != company_id:
            raise AppError(code="BATCH_NOT_FOUND", message=f"匯入批次 '{batch_id}' 不存在", status_code=404)

        if batch.status != "VALIDATED":
            raise AppError(
                code="BATCH_NOT_VALIDATED",
                message=f"批次狀態為 '{batch.status}'，必須先經過預覽驗證方可入庫",
                status_code=400,
            )

        if not batch.preview_revision or batch.preview_revision != preview_revision:
            raise AppError(
                code="STALE_PREVIEW_REVISION",
                message="預覽修訂版本已過期或不匹配，禁止直接入庫，請重新預覽驗證",
                status_code=400,
            )

        valid_rows = db.scalars(
            select(AttendanceImportRow)
            .where(
                AttendanceImportRow.batch_id == batch_id,
                AttendanceImportRow.status == "VALID",
            )
            .order_by(AttendanceImportRow.row_no)
        ).all()

        committed_count = 0
        affected_summaries = set()  # (company_id, employee_id, work_date)

        for r in valid_rows:
            norm = r.normalized_values or {}
            event_utc_str = norm.get("event_at_utc")
            work_date_str = norm.get("work_date")
            employee_id = norm.get("employee_id")

            if not event_utc_str or not work_date_str or not employee_id:
                continue

            event_utc_dt = datetime.fromisoformat(event_utc_str)
            work_date_obj = date.fromisoformat(work_date_str)

            event = AttendanceEvent(
                id=str(uuid.uuid4()),
                company_id=company_id,
                employee_id=employee_id,
                event_at=event_utc_dt,
                source_timezone=batch.source_timezone,
                raw_event_at_str=r.event_at_str,
                event_type=norm.get("event_type", "CHECK_IN"),
                device_id=r.device_id,
                source_event_id=r.source_event_id,
                work_date=work_date_obj,
                is_overnight=norm.get("is_overnight", False),
                batch_id=batch_id,
            )
            db.add(event)
            r.status = "COMMITTED"
            committed_count += 1
            affected_summaries.add((company_id, employee_id, work_date_obj))

        batch.committed_rows = committed_count
        batch.committed_at = datetime.now(timezone.utc)
        batch.committed_by = user_id
        batch.status = "COMMITTED"

        db.flush()

        # 更新 affected_summaries 之日報統計
        for comp_id, emp_id, w_date in affected_summaries:
            cls._update_daily_summary(db, comp_id, emp_id, w_date)

        db.commit()
        db.refresh(batch)

        return {
            "batch_id": batch.id,
            "batch_no": batch.batch_no,
            "status": batch.status,
            "committed_rows": committed_count,
            "skipped_duplicates": batch.duplicate_rows,
            "invalid_rows": batch.invalid_rows,
            "committed_at": batch.committed_at.isoformat() if batch.committed_at else None,
        }

    @classmethod
    def _update_daily_summary(
        cls,
        db: Session,
        company_id: str,
        employee_id: str,
        work_date: date,
    ) -> AttendanceDailySummary:
        """更新指定員工於特定工作日之出勤匯總 (Update Daily Summary)"""
        events = db.scalars(
            select(AttendanceEvent)
            .where(
                AttendanceEvent.company_id == company_id,
                AttendanceEvent.employee_id == employee_id,
                AttendanceEvent.work_date == work_date,
            )
            .order_by(AttendanceEvent.event_at)
        ).all()

        summary = db.scalar(
            select(AttendanceDailySummary).where(
                AttendanceDailySummary.company_id == company_id,
                AttendanceDailySummary.employee_id == employee_id,
                AttendanceDailySummary.work_date == work_date,
            )
        )
        if not summary:
            summary = AttendanceDailySummary(
                id=str(uuid.uuid4()),
                company_id=company_id,
                employee_id=employee_id,
                work_date=work_date,
            )
            db.add(summary)

        summary.total_punches = len(events)
        if events:
            summary.first_check_in = events[0].event_at
            summary.last_check_out = events[-1].event_at
            summary.status = "NORMAL"
        else:
            summary.first_check_in = None
            summary.last_check_out = None
            summary.status = "REST_DAY"

        return summary

    @classmethod
    def create_correction(
        cls,
        db: Session,
        company_id: str,
        employee_id: str,
        approver_id: str,
        work_date: date,
        correction_type: str,
        corrected_event_at: datetime,
        event_type: str,
        reason: str,
        original_event_id: Optional[str] = None,
    ) -> AttendanceCorrection:
        """4. 考勤修正登記 (Attendance Correction - 補打卡與時間調整留痕，不覆寫原始打卡)"""
        if original_event_id:
            orig = db.get(AttendanceEvent, original_event_id)
            if not orig or orig.company_id != company_id:
                raise AppError(code="EVENT_NOT_FOUND", message="原始打卡事件不存在", status_code=404)

        correction = AttendanceCorrection(
            id=str(uuid.uuid4()),
            company_id=company_id,
            employee_id=employee_id,
            original_event_id=original_event_id,
            work_date=work_date,
            correction_type=correction_type,
            corrected_event_at=corrected_event_at,
            event_type=event_type,
            reason=reason,
            status="APPROVED",
            approved_by=approver_id,
        )
        db.add(correction)
        db.commit()
        db.refresh(correction)
        return correction

    @classmethod
    def query_events(
        cls,
        db: Session,
        company_id: str,
        employee_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        is_abnormal: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """5. 出勤打卡事件查詢 (Query Attendance Events - 公司範圍隔離)"""
        stmt = (
            select(AttendanceEvent, Employee.employee_no, Employee.full_name)
            .join(Employee, AttendanceEvent.employee_id == Employee.id)
            .where(AttendanceEvent.company_id == company_id)
        )

        if employee_id:
            stmt = stmt.where(AttendanceEvent.employee_id == employee_id)
        if start_date:
            stmt = stmt.where(AttendanceEvent.work_date >= start_date)
        if end_date:
            stmt = stmt.where(AttendanceEvent.work_date <= end_date)
        if is_abnormal is not None:
            stmt = stmt.where(AttendanceEvent.is_abnormal == is_abnormal)

        total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0

        stmt = stmt.order_by(AttendanceEvent.event_at.desc()).offset(offset).limit(limit)
        results = db.execute(stmt).all()

        items = []
        for ev, emp_no, emp_name in results:
            items.append({
                "id": ev.id,
                "employee_id": ev.employee_id,
                "employee_no": emp_no,
                "employee_name": emp_name,
                "event_at": ev.event_at.isoformat(),
                "raw_event_at_str": ev.raw_event_at_str,
                "source_timezone": ev.source_timezone,
                "event_type": ev.event_type,
                "work_date": ev.work_date.isoformat(),
                "is_overnight": ev.is_overnight,
                "device_id": ev.device_id,
                "source_event_id": ev.source_event_id,
                "is_abnormal": ev.is_abnormal,
                "abnormal_reason": ev.abnormal_reason,
            })

        return items, total

    @classmethod
    def export_events_csv(
        cls,
        db: Session,
        company_id: str,
        employee_id: Optional[str] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> str:
        """6. 安全匯出出勤 CSV (防公式注入攻擊 - CSV Formula Injection Protection)"""
        items, _ = cls.query_events(
            db, company_id=company_id, employee_id=employee_id, start_date=start_date, end_date=end_date, limit=10000
        )

        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\r\n")

        # 標題列
        headers = [
            "Employee No",
            "Employee Name",
            "Event At (UTC)",
            "Local Raw Time",
            "Timezone",
            "Event Type",
            "Work Date",
            "Is Overnight",
            "Device ID",
            "Source Event ID",
            "Abnormal Reason",
        ]
        writer.writerow(headers)

        for row in items:
            writer.writerow([
                cls._sanitize_csv_cell(row["employee_no"]),
                cls._sanitize_csv_cell(row["employee_name"]),
                cls._sanitize_csv_cell(row["event_at"]),
                cls._sanitize_csv_cell(row["raw_event_at_str"]),
                cls._sanitize_csv_cell(row["source_timezone"]),
                cls._sanitize_csv_cell(row["event_type"]),
                cls._sanitize_csv_cell(row["work_date"]),
                cls._sanitize_csv_cell(str(row["is_overnight"])),
                cls._sanitize_csv_cell(row["device_id"]),
                cls._sanitize_csv_cell(row["source_event_id"]),
                cls._sanitize_csv_cell(row["abnormal_reason"]),
            ])

        return output.getvalue()
