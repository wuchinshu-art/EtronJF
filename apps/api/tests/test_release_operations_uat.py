import os
import io
import pytest
from datetime import datetime, date, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import hash_password, hash_token
from app.core.backup_service import BackupRestoreService, AuditService, mask_sensitive_payload
from app.models.auth import User, Role, UserRole, Session as UserSession
from app.models.hr import Company, Organization, Employee, Shift, LeaveType, LeaveLedger
from app.models.platform import Attachment, AuditLog
from app.models.leave import LeaveRequest
from app.models.seal_contract import Seal, SealRequest, Contract
from app.models.attendance import ShiftAssignment, AttendanceEvent, AttendanceDailySummary
from app.core.attendance_service import AttendanceService
from app.core.leave_service import LeaveService
from app.core.seal_contract_service import SealContractService
from app.main import app


def setup_uat_environment(db: Session):
    """建立 UAT 端到端綜合驗收環境主檔"""
    # 1. 公司
    for comp_id, name, tz, curr in [
        ("ETJ-TW", "台灣總部", "Asia/Taipei", "TWD"),
        ("ETJ-JP", "福岡支社", "Asia/Tokyo", "JPY"),
    ]:
        if not db.get(Company, comp_id):
            db.add(Company(id=comp_id, name=name, default_timezone=tz, default_currency=curr))

    # 2. 組織
    if not db.get(Organization, "ORG-TW-CORP"):
        db.add(Organization(id="ORG-TW-CORP", company_id="ETJ-TW", code="TW-CORP", name="台北營運處", level="DIVISION"))
    if not db.get(Organization, "ORG-JP-CORP"):
        db.add(Organization(id="ORG-JP-CORP", company_id="ETJ-JP", code="JP-CORP", name="福岡營業處", level="DIVISION"))

    # 3. 員工
    for emp_id, emp_no, comp_id, org_id, full_name, email in [
        ("EMP-UAT-TW01", "TW901", "ETJ-TW", "ORG-TW-CORP", "張總監", "tw901@etron.com"),
        ("EMP-UAT-TW02", "TW902", "ETJ-TW", "ORG-TW-CORP", "王經理", "tw902@etron.com"),
        ("EMP-UAT-JP01", "JP901", "ETJ-JP", "ORG-JP-CORP", "高橋健", "jp901@etron.com"),
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

    # 4. 班別
    if not db.get(Shift, "SHIFT-UAT-8H"):
        db.add(Shift(
            id="SHIFT-UAT-8H",
            company_id="ETJ-TW",
            code="UAT-8H",
            name="UAT 標準班",
            work_start_time="09:00",
            work_end_time="18:00",
            break_minutes=60,
            daily_standard_minutes=480,
            is_overnight=False,
        ))

    # 5. 假別
    if not db.get(LeaveType, "LT-UAT-ANNUAL"):
        db.add(LeaveType(
            id="LT-UAT-ANNUAL",
            company_id="ETJ-TW",
            code="UAT-ANNUAL",
            name="特別休假",
            unit="MINUTES",
            is_paid=True,
        ))

    db.commit()


def test_health_and_readiness_probes(client: TestClient, db_session: Session):
    """UAT 1: 驗證系統健康檢查 (/health) 與就緒性檢查 (/ready) 端點"""
    # 1. Health Probe
    resp_health = client.get("/api/v1/health")
    assert resp_health.status_code == 200
    data_h = resp_health.json()
    assert data_h["status"] == "healthy"
    assert data_h["database"]["status"] == "healthy"
    assert "sqlite_version" in data_h["database"]

    # 2. Ready Probe
    resp_ready = client.get("/api/v1/ready")
    assert resp_ready.status_code == 200
    data_r = resp_ready.json()
    assert data_r["status"] == "ready"
    assert data_r["pragmas"]["foreign_keys"] is True


def test_online_backup_and_recovery_integrity(db_session: Session):
    """UAT 2: 驗證 SQLite 線上在線備份與災難復原完整性校驗 (PRAGMA integrity_check)"""
    setup_uat_environment(db_session)

    # 建立臨時 SQLite 資料庫檔案作為在線備份來源
    temp_dir = Path("apps/api/data/test_temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    src_db_file = temp_dir / "uat_source.db"
    
    import sqlite3
    conn = sqlite3.connect(str(src_db_file))
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, note TEXT);")
    conn.execute("INSERT INTO test_table (note) VALUES ('UAT_VERIFY_DATA');")
    conn.commit()
    conn.close()

    # 備份前置重設路徑以利實測
    orig_path = settings.DATABASE_PATH
    try:
        settings.DATABASE_PATH = src_db_file

        backup_res = BackupRestoreService.perform_online_backup(
            db=db_session,
            actor_id="USER-UAT-ADMIN",
            company_id="ETJ-TW",
            tag="uat_test",
        )
        assert backup_res["status"] == "SUCCESS"
        assert backup_res["integrity_status"] == "OK"
        assert backup_res["verification_rto_ms"] >= 0.0
        assert len(backup_res["sha256"]) == 64

        # 驗證審計日誌中已留存備份紀錄
        audit = db_session.query(AuditLog).filter_by(action="BACKUP", actor_id="USER-UAT-ADMIN").first()
        assert audit is not None
        assert audit.after_state["status"] == "VERIFIED_OK"

        # 清理備份產物
        bk_path = Path(backup_res["backup_path"])
        if bk_path.exists():
            os.remove(bk_path)
    finally:
        settings.DATABASE_PATH = orig_path
        if src_db_file.exists():
            os.remove(src_db_file)
        wal_file = temp_dir / "uat_source.db-wal"
        shm_file = temp_dir / "uat_source.db-shm"
        if wal_file.exists():
            os.remove(wal_file)
        if shm_file.exists():
            os.remove(shm_file)
        try:
            temp_dir.rmdir()
        except Exception:
            pass


def test_audit_log_sensitive_data_masking(db_session: Session):
    """UAT 3: 驗證安全稽核日誌之敏感資訊 (密碼、金鑰、銀行帳號) 深度遮罩防護"""
    sensitive_dict = {
        "username": "super_admin",
        "password": "ClearTextPassword123!",
        "csrf_token": "SecretCsrfToken999",
        "bank_account_no": "98765432101234",
        "employee_info": {
            "name": "張經理",
            "hashed_password": "Argon2HashedSecret",
            "bank_account": "1122334455",
        },
    }

    audit_entry = AuditService.log_event(
        db=db_session,
        company_id="ETJ-TW",
        actor_id="USER-SEC-ADMIN",
        action="UPDATE_SECURITY",
        object_type="USER",
        object_id="USER-001",
        before_state={"status": "INITIAL"},
        after_state=sensitive_dict,
        reason="安全資訊變更測試",
    )
    assert audit_entry.id is not None

    saved_after = audit_entry.after_state
    # 核心斷言：密碼與 Token 必須被遮罩為 ********
    assert saved_after["password"] == "********"
    assert saved_after["csrf_token"] == "********"
    assert saved_after["employee_info"]["hashed_password"] == "********"

    # 核心斷言：銀行帳號僅保留末 4 碼，其餘遮罩
    assert saved_after["bank_account_no"] == "**********1234"
    assert saved_after["employee_info"]["bank_account"] == "******4455"


def test_end_to_end_cross_module_workflow_uat(client: TestClient, db_session: Session):
    """UAT 4: 端到端跨模組綜合業務驗收 (出勤 -> 請假帳本 -> 用印與合約 -> 安全防護)"""
    setup_uat_environment(db_session)

    # 1. 建立測試使用者與登入 Session
    user_tw = User(
        id="USER-UAT-TW01",
        username="uat_manager_tw",
        email="uat_mgr_tw@etron.com",
        hashed_password=hash_password("Password999!"),
        display_name="張總監",
        primary_company_id="ETJ-TW",
        is_active=True,
    )
    db_session.add(user_tw)

    raw_token = "UAT_RAW_SESSION_TOKEN_123"
    session_tw = UserSession(
        id="SESS-UAT-TW01",
        session_token_hash=hash_token(raw_token),
        user_id="USER-UAT-TW01",
        active_company_id="ETJ-TW",
        csrf_token="CSRF-UAT-TOKEN-123",
        ip_address="127.0.0.1",
        expires_at=datetime.now(timezone.utc) + timedelta(days=2),
        idle_expires_at=datetime.now(timezone.utc) + timedelta(hours=4),
        is_revoked=False,
    )
    db_session.add(session_tw)
    db_session.commit()

    client.cookies.set("etj_session", raw_token)
    auth_headers = {"X-CSRF-Token": "CSRF-UAT-TOKEN-123"}

    # 2. 出勤模組驗證：上傳打卡、預覽並確認入庫
    att_csv = (
        "employee_no,event_at,event_type,device_id,source_event_id\n"
        "TW901,2026-10-24 08:55:00,CHECK_IN,DEV-UAT-01,EVT-UAT-01\n"
        "TW901,2026-10-24 18:05:00,CHECK_OUT,DEV-UAT-01,EVT-UAT-02\n"
    )
    upload_res = client.post(
        "/api/v1/attendance/imports/upload",
        headers=auth_headers,
        json={
            "company_id": "ETJ-TW",
            "file_name": "uat_attendance.csv",
            "file_text": att_csv,
            "file_format": "CSV",
        },
    )
    assert upload_res.status_code == 201, upload_res.text
    batch_id = upload_res.json()["batch_id"]

    prev_res = client.post(f"/api/v1/attendance/imports/{batch_id}/preview", headers=auth_headers)
    assert prev_res.status_code == 200
    rev = prev_res.json()["preview_revision"]

    commit_res = client.post(
        f"/api/v1/attendance/imports/{batch_id}/commit",
        headers=auth_headers,
        json={"preview_revision": rev},
    )
    assert commit_res.status_code == 200
    assert commit_res.json()["committed_rows"] == 2

    # 3. 請假帳本模組驗證：給予 16 小時假額 (960 分鐘)
    ledger_grant = LeaveLedger(
        company_id="ETJ-TW",
        employee_id="EMP-UAT-TW01",
        leave_type_id="LT-UAT-ANNUAL",
        entry_type="GRANT",
        amount_minutes=960,
        balance_after_minutes=960,
        valid_from=date(2026, 1, 1),
        valid_to=date(2026, 12, 31),
        created_by="USER-UAT-TW01",
    )
    db_session.add(ledger_grant)
    db_session.commit()

    # 4. 用印與合約模組驗證：開立印鑑與用印申請單
    seal = SealContractService.create_seal(
        db=db_session,
        company_id="ETJ-TW",
        code="SEAL-UAT-01",
        name="UAT 總部合約專用章",
        seal_type="CONTRACT_SEAL",
        custodian_employee_id="EMP-UAT-TW01",
        effective_from=date(2026, 1, 1),
    )
    assert seal.id is not None

    seal_req = SealContractService.create_seal_request(
        db=db_session,
        company_id="ETJ-TW",
        employee_id="EMP-UAT-TW01",
        seal_id=seal.id,
        document_name="UAT 產學研發合作備忘錄",
        purpose="雙方技術驗證備忘錄用印",
        copies=2,
    )
    assert seal_req.status == "DRAFT"

    # 5. 安全性與物件授權隔離：TW 帳號跨公司查詢 JP 資料一律被 403 阻擋
    idor_res = client.get("/api/v1/attendance/events?company_id=ETJ-JP", headers=auth_headers)
    assert idor_res.status_code == 403
    assert idor_res.json()["error"]["code"] == "FORBIDDEN_COMPANY_SCOPE"

    # 6. CSRF 防護驗證：無 CSRF Token 之寫入請求遭遇 403 阻擋
    no_csrf_res = client.post(
        "/api/v1/attendance/imports/upload",
        json={"company_id": "ETJ-TW", "file_name": "no_csrf.csv", "file_text": "TW901,2026-10-24\n"},
    )
    assert no_csrf_res.status_code == 403
    assert no_csrf_res.json()["error"]["code"] == "CSRF_VERIFICATION_FAILED"
