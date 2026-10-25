import io
import pytest
from datetime import datetime, date, time, timedelta, timezone
from decimal import Decimal
import openpyxl
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_token, hash_password
from app.core.errors import AppException
from app.models.auth import User, Role, UserRole, Session as UserSession
from app.models.hr import Company, Organization, Employee, Shift
from app.models.attendance import (
    ShiftAssignment,
    AttendanceImportBatch,
    AttendanceImportRow,
    AttendanceEvent,
    AttendanceCorrection,
    AttendanceDailySummary,
)
from app.core.attendance_service import AttendanceService


def setup_attendance_base_data(db: Session):
    """建立出勤模組基礎主檔資料"""
    # 建立公司主檔
    for comp_id, name, tz, curr in [
        ("ETJ-TW", "台灣總部", "Asia/Taipei", "TWD"),
        ("ETJ-JP", "福岡支社", "Asia/Tokyo", "JPY"),
    ]:
        if not db.get(Company, comp_id):
            db.add(Company(id=comp_id, name=name, default_timezone=tz, default_currency=curr))

    # 建立組織主檔
    if not db.get(Organization, "ORG-ATT-TW"):
        db.add(Organization(id="ORG-ATT-TW", company_id="ETJ-TW", code="ATT-TW", name="台北出勤測試部", level="DEPARTMENT"))
    if not db.get(Organization, "ORG-ATT-JP"):
        db.add(Organization(id="ORG-ATT-JP", company_id="ETJ-JP", code="ATT-JP", name="福岡出勤測試部", level="DEPARTMENT"))

    # 建立測試員工
    for emp_id, emp_no, comp_id, org_id, full_name, email in [
        ("EMP-ATT-01", "TW801", "ETJ-TW", "ORG-ATT-TW", "陳大同", "att01@etron.com"),
        ("EMP-ATT-02", "TW802", "ETJ-TW", "ORG-ATT-TW", "李小華", "att02@etron.com"),
        ("EMP-ATT-03", "JP801", "ETJ-JP", "ORG-ATT-JP", "佐藤健", "jp801@etron.com"),
    ]:
        if not db.get(Employee, emp_id):
            db.add(Employee(
                id=emp_id,
                employee_no=emp_no,
                company_id=comp_id,
                organization_id=org_id,
                full_name=full_name,
                email=email,
                hire_date=date(2026, 1, 1),
                status="ACTIVE",
            ))

    # 建立班別主檔 (常日班與跨夜大夜班)
    if not db.get(Shift, "SHIFT-STD-8H"):
        db.add(Shift(
            id="SHIFT-STD-8H",
            company_id="ETJ-TW",
            code="STD-8H",
            name="標準常日班",
            work_start_time="09:00",
            work_end_time="18:00",
            break_minutes=60,
            daily_standard_minutes=480,
            is_overnight=False,
        ))
    if not db.get(Shift, "SHIFT-NIGHT-TW"):
        db.add(Shift(
            id="SHIFT-NIGHT-TW",
            company_id="ETJ-TW",
            code="NIGHT-TW",
            name="跨夜大夜班",
            work_start_time="20:00",
            work_end_time="04:00",
            break_minutes=60,
            daily_standard_minutes=420,
            is_overnight=True,
        ))

    db.commit()


def test_attendance_multi_encoding_and_format_parsing(db_session: Session):
    """1. 多編碼 (UTF-8, UTF-8 BOM, CP950, Shift_JIS) 與多格式 (CSV, XLSX, TSV) 解析測試"""
    setup_attendance_base_data(db_session)

    # A. UTF-8 CSV
    csv_utf8 = "employee_no,event_at,event_type,device_id,source_event_id\nTW801,2026-10-24 08:55:00,CHECK_IN,DEV-01,EVT-001\n"
    batch_utf8 = AttendanceService.upload_and_parse_batch(
        db_session, "ETJ-TW", "USER-ADMIN", "test_utf8.csv", csv_utf8.encode("utf-8"), "CSV", encoding="UTF-8"
    )
    assert batch_utf8.total_rows == 1
    assert batch_utf8.status == "PENDING_PREVIEW"

    # B. UTF-8 BOM (utf-8-sig)
    csv_bom = "\ufeffemployee_no,event_at,event_type\nTW802,2026-10-24 09:02:00,CHECK_IN\n"
    batch_bom = AttendanceService.upload_and_parse_batch(
        db_session, "ETJ-TW", "USER-ADMIN", "test_bom.csv", csv_bom.encode("utf-8-sig"), "CSV", encoding="UTF-8-SIG"
    )
    assert batch_bom.total_rows == 1

    # C. CP950 (繁體中文 Big5/CP950 編碼)
    csv_cp950 = "工號,打卡時間,類型\nTW801,2026-10-24 18:05:00,CHECK_OUT\n"
    batch_cp950 = AttendanceService.upload_and_parse_batch(
        db_session,
        "ETJ-TW",
        "USER-ADMIN",
        "test_cp950.csv",
        csv_cp950.encode("cp950"),
        "CSV",
        encoding="CP950",
        column_mapping={"employee_no": "工號", "event_at": "打卡時間", "event_type": "類型"},
    )
    assert batch_cp950.total_rows == 1

    # D. Shift_JIS (日文 Shift_JIS 編碼)
    csv_sjis = "社員番号,打刻時刻,区分\nJP801,2026-10-24 08:50:00,CHECK_IN\n"
    batch_sjis = AttendanceService.upload_and_parse_batch(
        db_session,
        "ETJ-JP",
        "USER-ADMIN",
        "test_sjis.csv",
        csv_sjis.encode("shift_jis"),
        "CSV",
        encoding="Shift_JIS",
        source_timezone="Asia/Tokyo",
        column_mapping={"employee_no": "社員番号", "event_at": "打刻時刻", "event_type": "区分"},
    )
    assert batch_sjis.total_rows == 1

    # E. Excel XLSX 解析
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["employee_no", "event_at", "event_type", "device_id"])
    ws.append(["TW801", "2026-10-25 08:58:00", "CHECK_IN", "DEV-02"])
    xlsx_buf = io.BytesIO()
    wb.save(xlsx_buf)
    batch_xlsx = AttendanceService.upload_and_parse_batch(
        db_session, "ETJ-TW", "USER-ADMIN", "test.xlsx", xlsx_buf.getvalue(), "XLSX"
    )
    assert batch_xlsx.total_rows == 1

    # F. 錯誤編碼保護：嘗試用 UTF-8 解碼純 CP950 中文二進位位元組，嚴格拋出 INVALID_ENCODING
    raw_cp950_bytes = "工號,打卡時間\nTW801,2026-10-24 09:00:00\n".encode("cp950")
    with pytest.raises(AppException) as excinfo:
        AttendanceService.upload_and_parse_batch(
            db_session, "ETJ-TW", "USER-ADMIN", "bad_enc.csv", raw_cp950_bytes, "CSV", encoding="UTF-8"
        )
    assert excinfo.value.code == "INVALID_ENCODING"


def test_attendance_preview_validation_and_stale_commit_protection(db_session: Session):
    """2. 預覽驗證、錯誤報告與過期預覽禁止入庫保護 (Preview, Validation & Stale Protection)"""
    setup_attendance_base_data(db_session)

    # 構造混合資料：1 筆正常、1 筆未知工號、1 筆時間格式錯誤
    csv_data = (
        "employee_no,event_at,event_type\n"
        "TW801,2026-10-24 09:00:00,CHECK_IN\n"
        "TW99999_UNKNOWN,2026-10-24 09:10:00,CHECK_IN\n"
        "TW802,2026/10/24_BAD_FORMAT,CHECK_IN\n"
    )
    batch = AttendanceService.upload_and_parse_batch(
        db_session, "ETJ-TW", "USER-ADMIN", "mixed.csv", csv_data.encode("utf-8"), "CSV"
    )

    # 執行預覽與驗證
    preview_res = AttendanceService.preview_and_validate(db_session, batch.id, "ETJ-TW")
    assert preview_res["valid_rows"] == 1
    assert preview_res["invalid_rows"] == 2
    assert len(preview_res["errors"]) == 2
    err_codes = [e["errors"][0]["code"] for e in preview_res["errors"]]
    assert "EMPLOYEE_NOT_FOUND" in err_codes
    assert "INVALID_DATETIME_FORMAT" in err_codes

    valid_rev = preview_res["preview_revision"]
    assert valid_rev.startswith("REV-")

    # 測試過期 / 偽造之預覽修訂版本禁止入庫
    with pytest.raises(AppException) as excinfo:
        AttendanceService.commit_batch(db_session, batch.id, "ETJ-TW", "USER-ADMIN", preview_revision="REV-FAKE-STALE")
    assert excinfo.value.code == "STALE_PREVIEW_REVISION"

    # 以合法修訂版本提交入庫
    commit_res = AttendanceService.commit_batch(db_session, batch.id, "ETJ-TW", "USER-ADMIN", preview_revision=valid_rev)
    assert commit_res["status"] == "COMMITTED"
    assert commit_res["committed_rows"] == 1

    # 驗證資料庫中確實僅寫入 1 筆正常事件
    events = db_session.query(AttendanceEvent).filter_by(batch_id=batch.id).all()
    assert len(events) == 1
    assert events[0].employee_id == "EMP-ATT-01"
    assert events[0].work_date == date(2026, 10, 24)

    # 再次 commit 應被阻止
    with pytest.raises(AppException) as excinfo:
        AttendanceService.commit_batch(db_session, batch.id, "ETJ-TW", "USER-ADMIN", preview_revision=valid_rev)
    assert excinfo.value.code == "BATCH_NOT_VALIDATED"


def test_attendance_deduplication_in_batch_and_historical(db_session: Session):
    """3. 設備事件 ID 與自然鍵在同批及歷史檔案之去重機制 (De-duplication)"""
    setup_attendance_base_data(db_session)

    # 第一批：寫入正常事件
    csv_batch_1 = (
        "employee_no,event_at,event_type,device_id,source_event_id\n"
        "TW801,2026-10-24 09:00:00,CHECK_IN,DEV-01,EVT-HIST-100\n"
    )
    b1 = AttendanceService.upload_and_parse_batch(
        db_session, "ETJ-TW", "USER-ADMIN", "b1.csv", csv_batch_1.encode("utf-8"), "CSV"
    )
    p1 = AttendanceService.preview_and_validate(db_session, b1.id, "ETJ-TW")
    AttendanceService.commit_batch(db_session, b1.id, "ETJ-TW", "USER-ADMIN", p1["preview_revision"])

    # 第二批：
    # 列 1: 與歷史相同設備 ID (DEV-01, EVT-HIST-100) -> 歷史設備重複
    # 列 2: 與歷史相同員工與時間 (TW801, 2026-10-24 09:00:00) -> 歷史自然鍵重複
    # 列 3: 新增 TW802 09:30:00
    # 列 4: 故意於同一檔案內重複第 3 列 TW802 09:30:00 -> 同批自然鍵重複
    csv_batch_2 = (
        "employee_no,event_at,event_type,device_id,source_event_id\n"
        "TW802,2026-10-24 10:00:00,CHECK_IN,DEV-01,EVT-HIST-100\n"
        "TW801,2026-10-24 09:00:00,CHECK_IN,DEV-99,EVT-HIST-999\n"
        "TW802,2026-10-24 09:30:00,CHECK_IN,DEV-02,EVT-NEW-201\n"
        "TW802,2026-10-24 09:30:00,CHECK_IN,DEV-02,EVT-NEW-202\n"
    )
    b2 = AttendanceService.upload_and_parse_batch(
        db_session, "ETJ-TW", "USER-ADMIN", "b2.csv", csv_batch_2.encode("utf-8"), "CSV"
    )
    p2 = AttendanceService.preview_and_validate(db_session, b2.id, "ETJ-TW")

    assert p2["valid_rows"] == 1  # 僅第 3 列有效
    assert p2["duplicate_rows"] == 3  # 第 1, 2, 4 列均判定為重複

    # commit 成功入庫，僅新增 1 筆有效列
    c2 = AttendanceService.commit_batch(db_session, b2.id, "ETJ-TW", "USER-ADMIN", p2["preview_revision"])
    assert c2["committed_rows"] == 1

    total_evs = db_session.query(AttendanceEvent).filter_by(company_id="ETJ-TW").count()
    assert total_evs == 2  # 第一批 1 筆 + 第二批 1 筆


def test_night_shift_work_date_attribution(db_session: Session):
    """4. 跨夜班工作日排班歸屬演算法測試 (Night Shift Work Date Attribution)"""
    setup_attendance_base_data(db_session)

    # 指派員工 TW801 於 2026-10-25 上跨夜班 (20:00 ~ 04:00+1)
    shift_assign = ShiftAssignment(
        company_id="ETJ-TW",
        employee_id="EMP-ATT-01",
        shift_id="SHIFT-NIGHT-TW",
        work_date=date(2026, 10, 25),
    )
    db_session.add(shift_assign)
    db_session.commit()

    # 模擬兩筆打卡：
    # 1. 2026-10-25 19:55:00 上班打卡
    # 2. 2026-10-26 04:05:00 凌晨下班打卡 (曆日為 10-26，但排班歸屬 10-25)
    csv_night = (
        "employee_no,event_at,event_type\n"
        "TW801,2026-10-25 19:55:00,CHECK_IN\n"
        "TW801,2026-10-26 04:05:00,CHECK_OUT\n"
    )
    batch = AttendanceService.upload_and_parse_batch(
        db_session, "ETJ-TW", "USER-ADMIN", "night.csv", csv_night.encode("utf-8"), "CSV"
    )
    p = AttendanceService.preview_and_validate(db_session, batch.id, "ETJ-TW")
    assert p["valid_rows"] == 2

    sample_in = p["preview_samples"][0]
    sample_out = p["preview_samples"][1]

    assert sample_in["work_date"] == "2026-10-25"
    assert sample_in["is_overnight"] is True

    # 核心驗證：凌晨下班打卡歸屬工作日必須為 2026-10-25，且標記為跨夜班
    assert sample_out["work_date"] == "2026-10-25"
    assert sample_out["is_overnight"] is True

    # 入庫後驗證每日匯總
    AttendanceService.commit_batch(db_session, batch.id, "ETJ-TW", "USER-ADMIN", p["preview_revision"])
    summary = db_session.query(AttendanceDailySummary).filter_by(
        company_id="ETJ-TW",
        employee_id="EMP-ATT-01",
        work_date=date(2026, 10, 25),
    ).first()
    assert summary is not None
    assert summary.total_punches == 2


def test_immutable_events_multiple_punches_and_corrections(db_session: Session):
    """5. 多次打卡支援與不可覆寫原始事件、考勤修正留痕 (Immutable & Corrections)"""
    setup_attendance_base_data(db_session)

    # 同一天 4 次打卡 (上班、外出、返回、下班)
    csv_multi = (
        "employee_no,event_at,event_type\n"
        "TW802,2026-10-24 08:58:00,CHECK_IN\n"
        "TW802,2026-10-24 12:02:00,BREAK_START\n"
        "TW802,2026-10-24 12:59:00,BREAK_END\n"
        "TW802,2026-10-24 18:03:00,CHECK_OUT\n"
    )
    batch = AttendanceService.upload_and_parse_batch(
        db_session, "ETJ-TW", "USER-ADMIN", "multi.csv", csv_multi.encode("utf-8"), "CSV"
    )
    p = AttendanceService.preview_and_validate(db_session, batch.id, "ETJ-TW")
    AttendanceService.commit_batch(db_session, batch.id, "ETJ-TW", "USER-ADMIN", p["preview_revision"])

    events = db_session.query(AttendanceEvent).filter_by(
        company_id="ETJ-TW", employee_id="EMP-ATT-02", work_date=date(2026, 10, 24)
    ).order_by(AttendanceEvent.event_at).all()
    assert len(events) == 4
    assert [e.event_type for e in events] == ["CHECK_IN", "BREAK_START", "BREAK_END", "CHECK_OUT"]

    # 登記考勤修正 (例如下午忘記打卡補打卡)
    first_ev_id = events[0].id
    corr = AttendanceService.create_correction(
        db=db_session,
        company_id="ETJ-TW",
        employee_id="EMP-ATT-02",
        approver_id="USER-HR-APPROVER",
        work_date=date(2026, 10, 24),
        correction_type="SUPPLEMENT",
        corrected_event_at=datetime(2026, 10, 24, 15, 0, 0, tzinfo=timezone.utc),
        event_type="CHECK_IN",
        reason="公出開會忘記補刷卡",
        original_event_id=first_ev_id,
    )
    assert corr.id is not None
    assert corr.status == "APPROVED"

    # 核心驗證：原始 4 筆 attendance_events 毫無變更或被覆寫
    recheck_events = db_session.query(AttendanceEvent).filter_by(
        company_id="ETJ-TW", employee_id="EMP-ATT-02", work_date=date(2026, 10, 24)
    ).all()
    assert len(recheck_events) == 4


def test_csv_formula_injection_protection_and_company_idor(client: TestClient, db_session: Session):
    """6. CSV 公式注入安全防護與跨公司 IDOR 隔離防護 (Formula Injection & Scope)"""
    setup_attendance_base_data(db_session)

    # 建立 TW 使用者與工作階段
    user_tw = User(
        id="USER-ATT-TW",
        username="att_admin_tw",
        email="att_admin_tw@etron.com",
        hashed_password=hash_password("Pass123!"),
        display_name="TW考勤管理員",
        primary_company_id="ETJ-TW",
        is_active=True,
    )
    db_session.add(user_tw)

    raw_token = "TEST_RAW_SESSION_TOKEN_TW_123"
    session_tw = UserSession(
        id="SESS-ATT-TW",
        session_token_hash=hash_token(raw_token),
        user_id="USER-ATT-TW",
        active_company_id="ETJ-TW",
        csrf_token="CSRF-ATT-TW-TOKEN",
        ip_address="127.0.0.1",
        expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        idle_expires_at=datetime.now(timezone.utc) + timedelta(hours=4),
        is_revoked=False,
    )
    db_session.add(session_tw)
    db_session.commit()

    client.cookies.set("etj_session", raw_token)
    headers = {"X-CSRF-Token": "CSRF-ATT-TW-TOKEN"}

    # A. 匯入帶有試算表惡意公式的打卡事件 (=cmd|'/c calc'!A0, +123, -SUM(1,2), @echo)
    malicious_csv = (
        "employee_no,event_at,event_type,device_id,source_event_id\n"
        "TW801,2026-10-24 09:00:00,CHECK_IN,=cmd|'/c calc'!A0,+123456\n"
    )
    upload_resp = client.post(
        "/api/v1/attendance/imports/upload",
        headers=headers,
        json={
            "company_id": "ETJ-TW",
            "file_name": "malicious.csv",
            "file_text": malicious_csv,
            "file_format": "CSV",
        },
    )
    assert upload_resp.status_code == 201, upload_resp.text
    batch_id = upload_resp.json()["batch_id"]

    prev_resp = client.post(f"/api/v1/attendance/imports/{batch_id}/preview", headers=headers)
    assert prev_resp.status_code == 200, prev_resp.text
    rev = prev_resp.json()["preview_revision"]

    commit_resp = client.post(
        f"/api/v1/attendance/imports/{batch_id}/commit",
        headers=headers,
        json={"preview_revision": rev},
    )
    assert commit_resp.status_code == 200, commit_resp.text

    # B. 匯出 CSV 驗證公式注入防護
    export_resp = client.get("/api/v1/attendance/events/export?company_id=ETJ-TW", headers=headers)
    assert export_resp.status_code == 200, export_resp.text
    csv_content = export_resp.text
    # 關鍵斷言：以 = 開頭的設備 ID 必須被轉義為 '=cmd... 防止 Excel 執行
    assert "'=cmd|'/c calc'!A0" in csv_content
    assert "'+123456" in csv_content

    # C. 跨公司 IDOR 權限隔離測試：TW 帳號嘗試存取 JP 公司資料
    idor_upload = client.post(
        "/api/v1/attendance/imports/upload",
        headers=headers,
        json={
            "company_id": "ETJ-JP",  # 跨公司越權
            "file_name": "hack.csv",
            "file_text": "employee_no,event_at\nJP801,2026-10-24 09:00:00\n",
        },
    )
    assert idor_upload.status_code == 403
    assert idor_upload.json()["error"]["code"] == "FORBIDDEN_COMPANY_SCOPE"

    idor_export = client.get("/api/v1/attendance/events/export?company_id=ETJ-JP", headers=headers)
    assert idor_export.status_code == 403
    assert idor_export.json()["error"]["code"] == "FORBIDDEN_COMPANY_SCOPE"
