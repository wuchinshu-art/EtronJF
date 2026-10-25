import hashlib
import os
import shutil
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.core.config import settings
from app.core.errors import AppException
from app.models.platform import AuditLog


SENSITIVE_FIELD_NAMES = {
    "password",
    "hashed_password",
    "password_hash",
    "token",
    "csrf_token",
    "session_token",
    "secret",
}


def mask_sensitive_payload(data: Any) -> Any:
    """遞迴遮罩敏感欄位 (密碼、Token、銀行帳號) 防止個資與機密外洩至日誌"""
    if isinstance(data, dict):
        masked = {}
        for k, v in data.items():
            k_lower = str(k).lower()
            if any(s in k_lower for s in SENSITIVE_FIELD_NAMES):
                masked[k] = "********"
            elif "account" in k_lower or "bank" in k_lower:
                str_v = str(v)
                if len(str_v) > 4:
                    masked[k] = f"{'*' * (len(str_v) - 4)}{str_v[-4:]}"
                else:
                    masked[k] = "****"
            elif isinstance(v, (dict, list)):
                masked[k] = mask_sensitive_payload(v)
            else:
                masked[k] = v
        return masked
    elif isinstance(data, list):
        return [mask_sensitive_payload(item) for item in data]
    return data


class AuditService:
    """系統安全稽核日誌服務 (Security Audit Service)"""

    @staticmethod
    def log_event(
        db: Session,
        company_id: str,
        actor_id: str,
        action: str,
        object_type: str,
        object_id: str,
        before_state: Optional[Dict[str, Any]] = None,
        after_state: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
        request_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> AuditLog:
        """純追加寫入安全稽核日誌 (Append-only Audit Log)"""
        masked_before = mask_sensitive_payload(before_state) if before_state else None
        masked_after = mask_sensitive_payload(after_state) if after_state else None

        audit_entry = AuditLog(
            company_id=company_id,
            actor_id=actor_id,
            action=action,
            object_type=object_type,
            object_id=object_id,
            before_state=masked_before,
            after_state=masked_after,
            reason=reason,
            request_id=request_id,
            ip_address=ip_address,
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit_entry)
        db.commit()
        db.refresh(audit_entry)
        return audit_entry


class BackupRestoreService:
    """SQLite WAL 線上零中斷備份與復原驗證服務 (SQLite Online Backup & Restore Service)"""

    @classmethod
    def get_backup_dir(cls) -> Path:
        backup_dir = settings.DATABASE_PATH.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        return backup_dir

    @classmethod
    def perform_online_backup(
        cls,
        db: Session,
        actor_id: str,
        company_id: str = "SYSTEM",
        tag: str = "manual",
    ) -> Dict[str, Any]:
        """執行 SQLite 線上在線備份 (WAL Online Backup - 零中斷，不鎖定讀寫)"""
        start_time = time.perf_counter()
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_filename = f"etronjf8_backup_{tag}_{timestamp_str}.db"
        target_path = cls.get_backup_dir() / backup_filename

        source_db_path = settings.DATABASE_PATH
        if not source_db_path.exists():
            raise AppException(code="SOURCE_DB_NOT_FOUND", message="原始資料庫檔案不存在", status_code=500)

        # 方式 1: 透過原生 sqlite3.Connection.backup 執行安全的在線備份
        try:
            src_conn = sqlite3.connect(str(source_db_path), timeout=10.0)
            dst_conn = sqlite3.connect(str(target_path), timeout=10.0)
            try:
                with dst_conn:
                    src_conn.backup(dst_conn, pages=100)
            finally:
                dst_conn.close()
                src_conn.close()
        except Exception as e:
            if target_path.exists():
                try:
                    os.remove(target_path)
                except Exception:
                    pass
            raise AppException(code="BACKUP_FAILED", message=f"線上備份失敗: {str(e)}", status_code=500)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        file_size = target_path.stat().st_size

        # 計算備份檔 SHA-256
        sha256 = hashlib.sha256()
        with open(target_path, "rb") as f:
            while chunk := f.read(65536):
                sha256.update(chunk)
        backup_hash = sha256.hexdigest()

        # 立即演練完整性驗證 (PRAGMA integrity_check)
        verify_ok, verify_msg, rto_ms = cls.verify_backup_integrity(target_path)
        if not verify_ok:
            raise AppException(code="BACKUP_VERIFICATION_FAILED", message=f"備份完整性驗證失敗: {verify_msg}", status_code=500)

        # 記錄安全稽核日誌
        AuditService.log_event(
            db=db,
            company_id=company_id,
            actor_id=actor_id,
            action="BACKUP",
            object_type="SYSTEM",
            object_id=backup_filename,
            after_state={
                "backup_filename": backup_filename,
                "file_size_bytes": file_size,
                "sha256": backup_hash,
                "duration_ms": duration_ms,
                "rto_ms": rto_ms,
                "status": "VERIFIED_OK",
            },
            reason=f"SQLite WAL 在線備份 (標記: {tag})",
        )

        return {
            "status": "SUCCESS",
            "backup_filename": backup_filename,
            "backup_path": str(target_path),
            "file_size_bytes": file_size,
            "sha256": backup_hash,
            "backup_duration_ms": duration_ms,
            "verification_rto_ms": rto_ms,
            "integrity_status": "OK",
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
        }

    @classmethod
    def verify_backup_integrity(cls, backup_path: Path) -> Tuple[bool, str, float]:
        """驗證備份檔之 SQLite 資料結構完整性 (PRAGMA integrity_check) 並測量 RTO 復原演練耗時"""
        start_time = time.perf_counter()
        if not backup_path.exists():
            return False, "備份檔案不存在", 0.0

        try:
            conn = sqlite3.connect(f"file:{backup_path.as_posix()}?mode=ro", uri=True, timeout=5.0)
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check;")
            res = cursor.fetchone()
            conn.close()

            rto_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if res and res[0] == "ok":
                return True, "ok", rto_ms
            else:
                return False, str(res), rto_ms
        except Exception as e:
            rto_ms = round((time.perf_counter() - start_time) * 1000, 2)
            return False, str(e), rto_ms
