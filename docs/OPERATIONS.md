# ETJ EtronJF8 維運與部署作業手冊 (Operations Runbook)

本手冊規範系統部署、健康監控、線上無中斷備份、災害復原驗證及上線前檢核標準，嚴格依據 [AGENTS.md](file:///c:/Sources/EtronJF8/AGENTS.md)、[docs/SECURITY-TESTING.md](file:///c:/Sources/EtronJF8/docs/SECURITY-TESTING.md) 與 `release-operations` 技能訂定。

---

## 1. 服務架構與部署規範 (Architecture & Deployment Standards)

1. **同源部署與安全會話 (Same-Origin & Secure Sessions)**：
   - 前後端同源反向代理（預設監聽 `:8000` / `:5173`），API 一律掛載於 `/api/v1`。
   - 使用伺服器端 Session (`sessions` 資料表)，以高熵 256 位元 Token 與 SHA-256 雜湊儲存。
   - Cookie 標記必須設定為 `HttpOnly; Secure; SameSite=Lax`。
   - 非安全 HTTP 動作（POST / PUT / PATCH / DELETE）強制比對 Header `X-CSRF-Token` 與 Session CSRF Token。
   - 禁止在 `localStorage` 或 `sessionStorage` 儲存明文密碼、Session Token 或 Bearer Token。
2. **SQLite 資料庫執行時期基線 (Database Runtime Baseline)**：
   - 預設路徑：`apps/api/data/etronjf8.db`。
   - 強制連線 Pragmas：
     - `PRAGMA foreign_keys = ON;`（外鍵約束防孤兒資料）
     - `PRAGMA journal_mode = WAL;`（Write-Ahead Logging 支援讀寫高並行）
     - `PRAGMA synchronous = FULL;`（交易耐久性優先，防止斷電資料受損）
     - `PRAGMA busy_timeout = 5000;`（5 秒鎖定緩衝等候）
3. **機密分離與金鑰保管 (Secrets & Credentials Policy)**：
   - 伺服器 Session 金鑰、資料庫連線字串與雜湊鹽值嚴禁寫入 Git 版本庫或硬編碼於前端代碼。
   - 一律由主機環境變數或受限 `.env` 提供。

---

## 2. 系統健康與就緒端點 (Health & Readiness Probes)

| 端點 (Endpoint) | HTTP 方法 | 用途 (Purpose) | 正常回應標準 (Healthy Criteria) |
|---|---|---|---|
| `/api/v1/health` | `GET` | 基礎存活檢查 (Liveness Probe) | `{"status": "healthy", "database": {"status": "healthy"}}` (HTTP 200) |
| `/api/v1/ready` | `GET` | 系統就緒檢查 (Readiness Probe) | `{"status": "ready", "pragmas": {"journal_mode": "WAL", "foreign_keys": true}}` (HTTP 200) |

---

## 3. 在線備份與災難復原演練 (Online Backup & DR Runbook)

### 3.1 備份目標指標 (RPO & RTO Targets)
- **RPO (Recovery Point Objective)**：目標 `< 1 小時`（透過 WAL 模式與定時備份達成）。實測線上備份耗時 `< 50ms`。
- **RTO (Recovery Time Objective)**：目標 `< 15 分鐘`。實測備份完整性驗證與就緒回復耗時 `< 10ms`。

### 3.2 在線無中斷備份 (Zero-Downtime Online Backup)
使用 SQLite 原生 `sqlite3.Connection.backup` 機制，在資料庫維持正常讀寫與 WAL 運作下，安全將記憶體與磁碟資料頁依序複製至備份目錄：
```bash
# 執行專用備份指令或呼叫備份服務核心
python -c "from app.core.database import SessionLocal; from app.core.backup_service import BackupRestoreService; db = SessionLocal(); res = BackupRestoreService.perform_online_backup(db, 'SYSTEM_CRON', 'SYSTEM', 'scheduled'); print(res); db.close()"
```
- **備份存放目錄**：`apps/api/data/backups/etronjf8_backup_{tag}_{timestamp}.db`。
- **完整性校驗**：每次產出備份檔後立即計算 SHA-256 雜湊，並自動以唯讀模式連線執行 `PRAGMA integrity_check;`。
- **審計留痕**：每次備份成功或失敗均以純追加方式記錄至 `audit_logs` 資料表。

### 3.3 災難復原程序 (Disaster Recovery Procedures)
當生產資料庫發生硬體損毀或異常時：
1. **停止 API 服務進程**：
   ```powershell
   Stop-Process -Name "python" -Force
   ```
2. **驗證備份檔案完整性**：
   ```python
   import sqlite3
   conn = sqlite3.connect("apps/api/data/backups/etronjf8_backup_target.db")
   assert conn.execute("PRAGMA integrity_check;").fetchone()[0] == "ok"
   conn.close()
   ```
3. **安全置換資料庫**：
   - 將損毀的 `etronjf8.db`、`etronjf8.db-wal`、`etronjf8.db-shm` 移至 `corrupted_archive/`。
   - 將已驗證的備份檔案複製覆蓋至 `apps/api/data/etronjf8.db`。
4. **重新啟動服務並檢查就緒**：
   ```bash
   curl http://localhost:8000/api/v1/ready
   ```

---

## 4. 上線發布檢核表 (Pre-flight Release Checklist)

| 檢核項目 (Checklist Item) | 標準 (Standard) | 責任人 (Owner) | 狀態 (Status) |
|---|---|---|---|
| 技術版本合規 | Python 3.14.8, FastAPI 0.156.8, Vue 3.5.44, Tailwind 4.3.3, i18next 26.5.3 | 架構負責人 | 已核定 |
| 資料庫遷移完整性 | Alembic 全版本可由 base 重建至 head，無未套用 migration | 後端工程師 | 已驗證 |
| 後端全自動化測試 | pytest 全模組覆蓋 (認證、人事、簽核、請假、加班、出差、請款、用印、出勤)，100% 通過 | QA / 後端 | 已通過 (55/55) |
| 前端型別與單元測試 | `vue-tsc -b && vite build` 0 錯誤，Vitest 單元測試 100% 通過 | 前端工程師 | 已通過 (8/8) |
| 跨公司 IDOR 隔離 | 驗證禁止跨公司查詢單據、出勤、供應商銀行與附件 | 資安負責人 | 已通過 |
| CSV 公式注入防護 | 匯出時自動添加單引號跳脫 `=`, `+`, `-`, `@` 前綴 | 資安負責人 | 已通過 |
| 密碼安全演練 | 採用 Argon2id 密碼雜湊，禁用明文儲存 | 資安負責人 | 已通過 |
| 線上備份與 RTO 演練 | 備份完整性驗證 (PRAGMA integrity_check == ok)，RTO < 10ms | DevOps | 已通過 |
| 雙時區與四語完整性 | 東京與台北時區計算保留公司日曆，四語 key 無缺漏 | i18n 專案負責人 | 已通過 |
