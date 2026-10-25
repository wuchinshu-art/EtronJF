# ETJ EtronJF8 規劃與 Skills 文件包

先讀 START-HERE.md。

- docs/PROJECT-PLAN.md
- docs/DECISIONS.md
- docs/WORKFLOW-RULES.md
- docs/ARCHITECTURE.md
- docs/UI-I18N-TIME.md
- docs/SECURITY-TESTING.md
- docs/ATTENDANCE-IMPORT.md
- AGENTS.md
- docs/TASKS.md
- docs/VERSION-CHECK.md
- START-HERE.md

## Skills

- project-bootstrap：驗證技術版本、建立單體專案骨架與工具鏈
- architecture-spec：維護架構規格、API 契約及任務邊界
- ui-i18n-time：建立天藍 UI、四語及東京台北時區
- auth-rbac：實作帳號、工作階段與物件層權限
- hr-master：建立人事主檔與假額帳本
- workflow-engine：建立版本化條件簽核與待辦
- leave-overtime：實作請假及加班垂直切片
- travel-settlement：實作出差、預支及結報
- expense-payment：實作報支、供應商及請款
- seal-contract：實作用印與合約版本
- attendance-import：實作可重跑的出勤匯入及查詢
- database-migration：管理 SQLite schema 與資料遷移
- security-audit：審查個資、附件、session 及稽核
- test-review：執行測試及獨立程式審查
- release-operations：建立部署、備份、回復與維運

## 設計過程與技術驗證紀錄 (Design & Technical Verification Process)

### 任務 T00：版本與決策核定 (Version and Decision Approval)

- **執行時間**：2026-10-23
- **執行原則**：嚴格遵守 [AGENTS.md](file:///c:/Sources/EtronJF8/AGENTS.md) 規範，先驗證真實環境與依賴版本，不擅自降版，不靜默替代，不產生未經核准的應用程式骨架。

#### 1. 實際驗證命令與輸出摘要 (Executed Commands & Output Summary)

1. **Python 解譯器與執行環境**：
   - 執行命令：`python --version`
   - 實際輸出：`Python 3.14.8`
   - 執行路徑：`C:\Python\py314\python.exe`
2. **SQLite Runtime 版本檢驗**：
   - 執行命令：`python -c "import sys,sqlite3; print(sys.executable); print(sqlite3.sqlite_version)"`
   - 實際輸出：`sqlite_version = 3.50.4`
   - 狀態分析：目標為 `SQLite 3.54.x`，但 Python 3.14.8 官方 Windows 二進位綁定之 SQLite 核心版本為 `3.50.4`。依規約「不為滿足數字替換不明 sqlite DLL」，列為阻擋待核定決策 (D01)。
3. **FastAPI 版本相容性驗證**：
   - 執行命令：`python -m pip index versions fastapi`
   - 實際輸出：PyPI 上存在 `0.156.8`（最新為 `0.161.1`）。
   - 相依性演練：`python -m pip install fastapi==0.156.8 --dry-run` 成功解析，相容 Starlette 0.50.0 與 Pydantic 2.12.5。
4. **Node.js / npm 環境**：
   - 執行命令：`node --version; npm --version`
   - 實際輸出：`Node.js v26.8.1` / `npm 11.19.0`
5. **前端框架與套件驗證**：
   - `npm view vue@3.5.44 version peerDependencies --json`：版本存在，相容 TypeScript。
   - `npm view tailwindcss@4.3 version engines --json`：存在 `4.3.0` 至 `4.3.3`，建議鎖定 `4.3.3`。
   - `npm view i18next@26.5.3 version engines --json`：精確匹配 `26.5.3`。
   - `npm view vue-i18n version --json`：最新版為 `11.4.16`（確認無 26.5.x 分支）。
   - `npm view i18next-vue version peerDependencies --json`：`i18next-vue@5.4.0` 支援 `i18next >=23` 與 `vue ^3.4.38`，可與 Vue 3.5.44 及 i18next 26.5.3 完美配接。

#### 2. 技術版本鎖定清單建議 (Recommended Locklist)

| 技術項目 (Technology) | 目標版本 (Target) | 驗證結果 (Verified) | 建議鎖定版本 (Locked Version) | 狀態 (Status) |
| --- | --- | --- | --- | --- |
| Python | 3.14.8 | 3.14.8 | `3.14.8` | 通過 (Pass) |
| SQLite Runtime | 3.54.x | 3.50.4 | 待核定 `3.50.4` 或特定建置 | 待核定決策 (Approval Gate) |
| FastAPI | 0.156.8 | 0.156.8 可安裝 | `0.156.8` | 通過 (Pass) |
| SQLAlchemy | 2.0.x | 2.0.44 | `2.0.44` | 通過 (Pass) |
| Alembic | 1.17.x | 1.17.2 | `1.17.2` | 通過 (Pass) |
| Pydantic | 2.12.x | 2.12.5 | `2.12.5` | 通過 (Pass) |
| Node.js | LTS/Current | v26.8.1 | `26.8.1` | 通過 (Pass) |
| npm | 11.x | 11.19.0 | `11.19.0` | 通過 (Pass) |
| Vue | 3.5.44 | 3.5.44 | `3.5.44` | 通過 (Pass) |
| Tailwind CSS | 4.3.x | 4.3.3 | `4.3.3` | 通過 (Pass) |
| i18n 引擎 | 26.5.3 | i18next 26.5.3 | `i18next@26.5.3` | 通過 (Pass) |
| i18n Vue 適配器 | 相容 Vue 3.5 | i18next-vue 5.4.0 | `i18next-vue@5.4.0` | 通過 (Pass) |

#### 3. 核心決策與阻擋事項 (Decision Gates & Blockers)

- **決策 D01 (SQLite 執行時期版本)**：Python 3.14.8 官方發行所攜帶的 `sqlite3` C 程式庫版本為 `3.50.4`。規格指定之 `3.54.x` 需確認是否接受以官方二進位之 `3.50.4` 實施，避免任意替換不明來源的 DLL 造成執行不穩定。
- **決策 D02 (幣別與簽核金額換算)**：費用報支與請款之門檻（5,000 / 100,000 / 500,000）需正式核定幣別（公司基準幣 TWD/JPY 或原幣）、匯率取用基準日與含稅/未稅口徑。
- **決策 D04 (請假天數換算)**：請假 3 天 / 10 天門檻依工作分鐘換算標準工時（例如 1 天 = 480 分鐘）之計算基線需經業務核准。

### 任務 T01：骨架建立與工具鏈配置 (Project Scaffold & CI Setup)

- **執行時間**：2026-10-23
- **架構原則**：採模組化單體 (Modular Monolith)、前後端分離架構，所有 API 以 `/api/v1` 提供同源整合。

#### 1. 完成工作項目 (Completed Deliverables)

1. **後端骨架 (Backend Scaffold - FastAPI + SQLite)**：
   - 建立 [apps/api/pyproject.toml](file:///c:/Sources/EtronJF8/apps/api/pyproject.toml)，鎖定 `fastapi==0.156.8`、`sqlalchemy==2.0.44`、`alembic==1.17.2`、`pydantic==2.12.5`。
   - 核心設定 [apps/api/app/core/config.py](file:///c:/Sources/EtronJF8/apps/api/app/core/config.py)：時區支援 Asia/Taipei 與 Asia/Tokyo。
   - 資料庫連線引擎 [apps/api/app/core/database.py](file:///c:/Sources/EtronJF8/apps/api/app/core/database.py)：
     - 強制啟用 SQLite 外鍵檢查：`PRAGMA foreign_keys = ON;`
     - 啟用 WAL 模式：`PRAGMA journal_mode = WAL;`
     - 設定交易完整性：`PRAGMA synchronous = FULL;`
     - 設定鎖定等候逾時：`PRAGMA busy_timeout = 5000;`
   - 安全與統一錯誤規格 [apps/api/app/core/errors.py](file:///c:/Sources/EtronJF8/apps/api/app/core/errors.py)：標準化 `error.code`、`field_errors`、`request_id`，遮罩內部伺服器 Traceback 資訊。
   - 健康檢查端點 [apps/api/app/api/v1/health.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/health.py)：實測 SQLite `SELECT 1` 連線並回傳 UTC ISO-8601 時間戳記。
   - 遷移框架：[apps/api/alembic.ini](file:///c:/Sources/EtronJF8/apps/api/alembic.ini) 及 [apps/api/alembic/env.py](file:///c:/Sources/EtronJF8/apps/api/alembic/env.py)。
2. **前端骨架 (Frontend Scaffold - Vue 3.5.44 + Tailwind 4 + i18next)**：
   - 建立 [apps/web/package.json](file:///c:/Sources/EtronJF8/apps/web/package.json)，鎖定 `vue@3.5.44`、`tailwindcss@4.3.3`、`i18next@26.5.3`、`i18next-vue@5.4.0`。
   - 樣式與設計代幣 (Design Tokens) [apps/web/src/styles/index.css](file:///c:/Sources/EtronJF8/apps/web/src/styles/index.css)：天藍主色 `#0284C7`、次色 `#0369A1`、淺底 `#F0F9FF`、裝飾 `#87CEEB`。
   - 多語系基線 [apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts)：完整涵蓋 `zh-TW`、`ja-JP`、`en-US`、`zh-CN` 四語結構。
   - 主應用視圖 [apps/web/src/App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue)：提供語言切換按鈕與即時健康狀態查詢卡片。
   - 建置配置 [apps/web/vite.config.ts](file:///c:/Sources/EtronJF8/apps/web/vite.config.ts)：配置 `/api` 反向代理至後端。
3. **專案工程基礎與 CI (Project Toolchain & CI)**：
   - 環境變數範本 [.env.example](file:///c:/Sources/EtronJF8/.env.example)。
   - 版本控制忽略配置 [.gitignore](file:///c:/Sources/EtronJF8/.gitignore)。
   - 自動化流程 [.github/workflows/ci.yml](file:///c:/Sources/EtronJF8/.github/workflows/ci.yml)：配置後端 pytest 測試與前端 typecheck / vitest / build 流程。

#### 2. 測試命令與實際執行結果 (Test Commands & Verified Execution)

- **後端自動化測試 (Backend Automated Tests)**：
  - 指令：`python -m pytest apps/api/tests -v`
  - 結果：`4 passed in 0.11s`
    - `test_standard_app_exception_response` 通過 (200/403 統一錯誤規格)
    - `test_unhandled_exception_sanitization` 通過 (500 錯誤遮罩與 request_id 產生)
    - `test_health_check_endpoint` 通過 (SQLite 連線 healthy)
    - `test_root_endpoint` 通過
- **前端自動化測試 (Frontend Automated Tests)**：
  - 指令：`npm run test` (Vitest)
  - 結果：`2 passed in 1.78s` (驗證四語鍵值結構對齊與語言動態切換)
- **前端型別檢查與生產打包 (Frontend Typecheck & Production Build)**：
  - 指令：`npm run build` (`vue-tsc -b && vite build`)
  - 結果：無任何型別錯誤，產出 HTML/CSS/JS 靜態資源 (built in 1.10s)。
- **資料庫遷移環境驗證 (Database Migration Check)**：
  - 指令：`python -m alembic current`
  - 結果：`Context impl SQLiteImpl. Will assume non-transactional DDL.` 成功連線。

#### 3. 本地啟動指令 (Local Startup Commands)

- **後端 API 伺服器**：

  ```powershell
  cd C:\sources\EtronJF8\apps\api
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
  ```

- **前端開發伺服器**：

  ```powershell
  cd C:\sources\EtronJF8\apps\web
  npm run dev
  ```

### 任務 T02：UI 共用元件、四語字典與雙時區服務 (ui-i18n-time)

- **執行時間**：2026-10-23
- **架構原則**：共用元件與天藍色系 Design Tokens 作為全系統單一視覺事實來源；事件儲存一律採 UTC ISO-8601，顯示端與業務日曆獨立解耦支援台北與東京雙時區；四語鍵值 100% 遞迴結構對齊。

#### 1. 完成工作項目 (Completed Deliverables)

1. **天藍 UI 共用元件庫 (Common Components)**：
   - [apps/web/src/components/common/AppShell.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/AppShell.vue)：全域應用框架，頂端整合公司選擇、獨立時區切換、四語切換與待辦數量標記；側邊模組導覽列支援收合與行動端響應。
   - [apps/web/src/components/common/PageHeader.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/PageHeader.vue)：標準頁面標題列，含層級麵包屑導航與操作按鈕槽。
   - [apps/web/src/components/common/DataTable.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/DataTable.vue)：支援水平捲動、欄位排序標記、分頁控制、Loading 骨架及 Empty 空狀態槽。
   - [apps/web/src/components/common/FilterBar.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/FilterBar.vue)：複合條件篩選列，含關鍵字輸入、自訂過濾條件插槽及重設按鈕。
   - [apps/web/src/components/common/FormField.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/FormField.vue)：表單欄位包裝元件，整合必填標記、提示說明及表單驗證錯誤 (Validation Error)。
   - [apps/web/src/components/common/MoneyInput.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/MoneyInput.vue)：金額輸入元件，支援多幣別前綴 (TWD, JPY, USD)，嚴格遵循規格採純字串 Decimal 輸入，防止浮點數精度遺失。
   - [apps/web/src/components/common/DateTimeInput.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/DateTimeInput.vue)：支援 date-only 純業務日期模式與 datetime-local 時區感知模式。
   - [apps/web/src/components/common/StatusBadge.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/StatusBadge.vue)：狀態標籤，映射 draft / in_review / approved / returned / rejected 等流程狀態至 Design Tokens 語義色彩。
   - [apps/web/src/components/common/EmptyState.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/EmptyState.vue)：查無資料時之友善空狀態引導面板。
   - [apps/web/src/components/common/ErrorPanel.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/ErrorPanel.vue)：標準錯誤展示面板，支援錯誤代碼標籤、欄位錯誤清單展開、Request ID 追蹤碼與一鍵複製。
2. **前後端時間與雙時區核心服務 (Time & Timezone Core Service)**：
   - 前端工具 [apps/web/src/utils/time.ts](file:///c:/Sources/EtronJF8/apps/web/src/utils/time.ts)：原生標準 Intl 實作 UTC instant (ISO-8601) 與 `Asia/Taipei` (UTC+8) / `Asia/Tokyo` (UTC+9) 雙向轉換，提供 date-only 純日期防污染驗證。
   - 後端核心 [apps/api/app/core/time.py](file:///c:/Sources/EtronJF8/apps/api/app/core/time.py)：Python zoneinfo 驅動之 UTC instant 生成、時區轉換與業務純日期解析器。
3. **四語在地化字典與完整性保證 (Quad-language Localization)**：
   - 擴充 [apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts)，完整提供 `zh-TW`、`ja-JP`、`en-US`、`zh-CN` 之導覽、狀態、共用操作、表單與錯誤字典。
   - 建立 [apps/web/tests/i18n-completeness.test.ts](file:///c:/Sources/EtronJF8/apps/web/tests/i18n-completeness.test.ts)，使用遞迴深度檢查確保所有語言字典之 Key 結構 100% 吻合，無任何缺漏。

#### 2. 測試命令與實際執行結果 (Test Commands & Verified Execution)

- **前端自動化測試 (Vitest)**：
  - 指令：`npm run test`
  - 結果：`3 test files passed, 8 passed in 2.18s`
    - `i18n-completeness.test.ts` (3 tests passed)：四語系無缺 key、無多餘 key。
    - `i18n.test.ts` (2 tests passed)：動態語系切換正常。
    - `time.test.ts` (3 tests passed)：台北與東京同 instant 顯示精確無誤、本地輸入轉回 UTC 準確、date-only 隔離驗證通過。
- **前端型別檢查與生產打包 (vue-tsc & vite build)**：
  - 指令：`npm run build`
  - 結果：所有共用元件之 TypeScript 型別完全符合嚴格模式，建置成功 (145 kB JS / 20 kB CSS)。
- **後端時間服務測試 (pytest)**：
  - 指令：`python -m pytest apps/api/tests -v`
  - 結果：`7 passed in 0.10s` (新增 3 項時間測試均通過)。

### 任務 T03：帳號、工作階段與物件層權限 (auth-rbac)

- **執行時間**：2026-10-23
- **架構原則**：採用伺服器端 Session Cookie (HttpOnly/SameSite) 認證，密碼使用高強度 Argon2id 雜湊演算法；權限採 RBAC + 公司範圍 (Company Scope) + 物件層級授權 (Object-level Authorization)，徹底防禦水平越權 (IDOR) 與 CSRF 跨站請求偽造。

#### 1. 完成工作項目 (Completed Deliverables)

1. **密碼安全性與 Token 生成模組**：
   - [apps/api/app/core/security.py](file:///c:/Sources/EtronJF8/apps/api/app/core/security.py)：整合 `argon2-cffi`，以 `Type.ID` (Argon2id) 演算法進行密碼雜湊與驗證；支援 256 位元高熵不透明 Session Token 與 CSRF Token 產生。
2. **帳號與權限資料庫模型 (Models)**：
   - [apps/api/app/models/auth.py](file:///c:/Sources/EtronJF8/apps/api/app/models/auth.py)：
     - `users`：帳號、Argon2id 密碼、姓名、信箱、主所屬公司、帳號與員工分離設計 (`employee_id` 可為空)、停用狀態 (`is_active`)、首次登入標記 (`is_first_login`)、樂觀鎖版本號 (`version`)。
     - `sessions`：伺服器端工作階段，以 SHA-256 儲存 `session_token_hash`，具備絕對過期時間、閒置過期時間、已撤銷標記與 CSRF 權杖。
     - `roles` 與 `permissions`：角色與權限代碼定義（如 `leave.create`, `hr.employee.manage`, `payment.bank_account.view` 等）。
     - `user_roles` 與 `role_permissions`：使用者角色與權限映射，角色綁定於特定生效公司。
     - `user_scopes`：使用者資料存取範圍（公司 / 部門 / 本人級別）。
     - `password_reset_tokens`：限時一次性密碼重設 Token。
3. **資料庫結構遷移 (Alembic Migration)**：
   - 生成並套用遷移腳本 `alembic/versions/f75644f7bdde_create_auth_and_rbac_tables.py`，完整建立上述 8 張關聯資料表與複合索引。
4. **鑑權相依性與資安防護攔截 (Auth Dependencies & IDOR Protection)**：
   - [apps/api/app/api/deps.py](file:///c:/Sources/EtronJF8/apps/api/app/api/deps.py)：
     - `get_current_session`：檢驗 Cookie、Session 雜湊、帳號啟用狀態、絕對與閒置逾時，以及非安全 HTTP 方法的 `X-CSRF-Token` 標頭驗證。
     - `require_permissions`：檢查使用者於當前公司是否具有指定權限碼。
     - `require_company_scope`：跨公司防 IDOR 核心驗證，阻擋跨公司資源未授權存取。
5. **API 端點 (API Endpoints)**：
   - 驗證端點 [apps/api/app/api/v1/auth.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/auth.py)：
     - `POST /api/v1/auth/login`：驗證登入、設置 HttpOnly Cookie、回傳 CSRF Token 與首次登入狀態。
     - `POST /api/v1/auth/logout`：登出並立即在伺服器端撤銷 Session、刪除 Cookie。
     - `GET /api/v1/auth/me`：取得目前使用者之角色、權限及公司資訊。
     - `POST /api/v1/auth/first-time-password`：首次登入強制密碼初始化。
     - `POST /api/v1/auth/change-password`：登入中變更密碼。
   - 使用者與公司資源端點 [apps/api/app/api/v1/users.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/users.py)：
     - `POST /api/v1/users`：新增使用者。
     - `POST /api/v1/users/{id}/suspend`：停用帳號並**立即撤銷該使用者所有正在進行中的 Session**。
     - `GET /api/v1/users/companies/{company_id}/sensitive-data`：受公司資料範圍嚴格保護之敏感資料端點。

#### 2. 測試命令與實際執行結果 (Test Commands & Verified Execution)

- **後端鑑權與資安整合測試 (pytest)**：
  - 指令：`python -m pytest apps/api/tests -v`
  - 結果：`12 passed in 2.12s`
    - `test_login_and_logout_flow`：通過 (登入寫入 HttpOnly Cookie、取得 CSRF Token、登出立即撤銷)。
    - `test_first_time_password_initialization`：通過 (首次密碼設定成功，狀態轉為正式)。
    - `test_user_suspension_immediate_session_revocation`：通過 (帳號停用後，原有 Session 存取立即遭 403 阻擋)。
    - `test_cross_company_idor_forbidden`：通過 (台灣總部使用者存取福岡支社敏感資料遭 403 跨公司拒絕)。
    - `test_csrf_protection_enforcement`：通過 (非安全寫入缺少 CSRF Token 遭 403 攔截)。
    - 健康檢查、標準錯誤防護與雙時區測試全數維持通過。

### 任務 T04：人事主檔及日曆 (hr-master)

- **執行時間**：2026-10-23
- **架構原則**：公司獨立日曆與幣別；組織與主管關係在寫入層進行有向無環圖 (DAG) 循環檢驗，禁止階層循環；假額採**不可變流水帳本 (Immutable Ledger)**，嚴格禁止直接修改剩餘值，確保給予、預占、扣抵與釋放具備完整審計軌跡與防超支保障。

#### 1. 完成工作項目 (Completed Deliverables)

1. **人事主檔與假額資料模型 (Models)**：
   - [apps/api/app/models/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/models/hr.py)：
     - `companies`：台灣總部 (`ETJ-TW`, TWD, Asia/Taipei) 與福岡支社 (`ETJ-JP`, JPY, Asia/Tokyo)。
     - `organizations`：支援樹狀部、處、課組織階層，具備自參照關聯。
     - `employees`：員工編號、公司與組織歸屬、到職與離職日、在職狀態 (`ACTIVE`, `ON_LEAVE`, `RESIGNED`)。
     - `manager_relations`：直屬主管鏈，具備關係類型與生效起訖日期。
     - `employee_changes`：報到、調職、離職生效歷程，記錄異動前組織與異動後組織。
     - `shifts`：工作起訖時間、休息分鐘、每日標準工時分鐘數 (預設 480 分鐘)、跨夜班標記。
     - `calendar_days`：公司獨立工作日曆 (date-only)，標記例假日與國定假日。
     - `leave_types`：假別定義（特別休假、普通傷病假、事假等），支援計量單位與附件要求設定。
     - `leave_ledger`：**假額不可變帳本**，以流水帳紀錄 `GRANT` (發放)、`HOLD` (假單預占)、`COMMIT` (核准扣抵)、`RELEASE` (退回釋放) 與 `CANCEL` (沖銷)。
2. **組織與主管防循環檢驗及帳本核心 (Rules & Ledger Service)**：
   - [apps/api/app/core/hr_rules.py](file:///c:/Sources/EtronJF8/apps/api/app/core/hr_rules.py)：
     - `check_organization_cycle`：組織階層寫入前沿父鏈向上遍歷，偵測到環路即拋出 `400 ORGANIZATION_CYCLE_DETECTED`。
     - `check_manager_cycle`：主管鏈設定前向上遍歷主管鏈，防止互相核決死循環，拋出 `400 MANAGER_CYCLE_DETECTED`。
     - `LeaveLedgerService`：
       - `get_available_balance`：精確計算有效期間內可用假額分鐘數。
       - `grant_leave`：原子寫入發放分錄。
       - `hold_leave`：送簽時預占假額，餘額不足時拋出 `400 INSUFFICIENT_LEAVE_BALANCE` 阻擋超支。
       - `commit_leave`：核准時扣抵分錄。
       - `release_leave`：退回撤銷時釋放預占額度。
3. **資料庫遷移腳本 (Alembic Migration)**：
   - 生成並套用遷移腳本 `alembic/versions/2cf11a60e41b_create_hr_master_and_leave_ledger_tables.py`，完整建立 9 張關聯資料表與複合索引。
4. **人事與帳本 API 端點 (API Endpoints)**：
   - [apps/api/app/api/v1/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/hr.py)：
     - `POST /api/v1/hr/companies` / `GET /api/v1/hr/companies`：公司主檔管理。
     - `POST /api/v1/hr/organizations` / `GET /api/v1/hr/organizations`：組織建立與查詢（含循環檢驗）。
     - `POST /api/v1/hr/employees` / `GET /api/v1/hr/employees`：員工建立與查詢。
     - `POST /api/v1/hr/employees/{id}/manager`：主管設定（含循環檢驗）。
     - `POST /api/v1/hr/employees/{id}/transfer`：員工調職與歷程記錄。
     - `POST /api/v1/hr/shifts`：班別建立。
     - `POST /api/v1/hr/calendar-days`：公司工作日曆建立。
     - `POST /api/v1/hr/leave-types`：假別建立。
     - `POST /api/v1/hr/leave-ledger/grant`：假額發放。
     - `GET /api/v1/hr/leave-ledger/balance`：即時可用假額查詢（換算標準天數與分鐘數）。

#### 2. 測試命令與實際執行結果 (Test Commands & Verified Execution)

- **後端人事與假額帳本測試 (pytest)**：
  - 指令：`python -m pytest apps/api/tests -v`
  - 結果：`16 passed in 3.61s`
    - `test_organization_cycle_detection`：通過 (組織階層循環 A -> B -> A 檢測成功並阻擋)。
    - `test_manager_cycle_detection`：通過 (主管鏈循環 A ↔ B 檢測成功並阻擋)。
    - `test_employee_transfer_and_history`：通過 (員工調職部門更新且版本號自增，異動歷程正確留存)。
    - `test_leave_ledger_atomic_lifecycle_and_overdraw_protection`：通過 (GRANT 4800分 -> HOLD 480分 -> 餘額不足超支防護成功拋出 400 -> COMMIT 扣抵 -> RELEASE 釋放結算無誤)。

### 任務 T05：簽核引擎核心 (workflow-engine)

- **執行時間**：2026-10-23
- **架構原則**：
  1. **送簽時快照凍結 (Approval Pipeline Snapshotting)**：表單送簽時解析主管鏈並過濾金額/條件門檻，將組織結構、主管鏈受派人、條件門檻凍結寫入節點快照 (`snapshot_data`)。後續組織異動或調職不影響進行中的簽核流。
  2. **防自簽機制 (Self-Approval Prevention)**：嚴格禁止申請人簽核自身送出的單據。若節點候選受派人為申請人本人，依據節點規則 (`AUTO_SKIP` 自動跳過或 `ESCALATE_TO_MANAGER` 自動上呈至上一層主管)，杜絕自審自批漏洞。
  3. **防雙重核決與原子推進 (State Machine Atomicity)**：簽核動作採樂觀鎖版本號 (`version`) 推進，節點簽核採原子更新；防止同節點多受派人重複簽核或競爭覆蓋。
  4. **安全條件運算式 (Safe Condition DSL)**：條件跳關使用 AST 抽象語法樹白名單剖析器，嚴格禁止 `eval()`，僅允許安全的布林與比較運算（如 `amount > 50000`）。
  5. **主管鏈斷鏈阻擋 (Broken Chain Blocker)**：若流程要求 N 層主管但組織人事關聯中斷，送簽前拋出 `400 WORKFLOW_MISSING_APPROVER` 阻擋提交，避免表單流落幽靈節點。

#### 1. 完成工作項目 (Completed Deliverables)

1. **簽核引擎資料模型 (Models)**：
   - [apps/api/app/models/workflow.py](file:///c:/Sources/EtronJF8/apps/api/app/models/workflow.py)：
     - `workflow_definitions`：流程定義（模組別、表單類型、所屬公司）。
     - `workflow_versions`：流程版本控制，記錄版本號與節點定義 JSON (`nodes_definition`)。
     - `workflow_instances`：流程實例（實例狀態 `DRAFT`, `IN_PROGRESS`, `APPROVED`, `REJECTED`, `CANCELLED`, `RETURNED`，含關聯業務主檔鍵與樂觀鎖版本號）。
     - `workflow_node_instances`：流程節點實例，儲存凍結之快照資料 (`snapshot_data`) 與節點執行狀態。
     - `approval_assignments`：待辦與簽核受派紀錄（受派人、代理人、派工狀態 `PENDING`, `COMPLETED`, `SKIPPED`, `CANCELLED`）。
     - `approval_actions`：不可變簽核歷史軌跡（記錄動作 `SUBMIT`, `APPROVE`, `REJECT`, `RETURN`, `DELEGATE` 與簽核意見）。
     - `delegations`：職務代理人設定。
2. **簽核核心引擎與規則解析服務 (Workflow Engine Service)**：
   - [apps/api/app/core/workflow_engine.py](file:///c:/Sources/EtronJF8/apps/api/app/core/workflow_engine.py)：
     - `SafeConditionEvaluator`：以 AST 為基底之沙盒條件評估器。
     - `WorkflowEngineService.submit_workflow`：
       - 主管鏈節點解析（直屬主管 `DIRECT_MANAGER`、第 N 層主管 `MANAGER_LEVEL_N`、指定角色 `ROLE`、部處長 `DEPT_HEAD`）。
       - 門檻與條件過濾（過濾無須執行的節點）。
       - 送簽時快照保存（凍結主管鏈與條件）。
       - 主管鏈斷鏈檢核（防遺漏受派人）。
       - 防自簽解析（自動跳關或上呈）。
     - `WorkflowEngineService.process_approval_action`：
       - 簽核權限驗證（受派人或有效代理人）。
       - 防自審自批檢查。
       - 原子狀態機推進（`APPROVE` 推進至下一節點或完簽；`REJECT` 終止駁回；`RETURN` 退回前一節點或起單人）。
3. **資料庫結構遷移 (Alembic Migration)**：
   - 生成並套用遷移腳本 `alembic/versions/d94f647ca61e_create_workflow_engine_tables.py`，建立 7 張核心簽核資料表與複合索引。
4. **簽核引擎 API 端點 (API Endpoints)**：
   - [apps/api/app/api/v1/workflow.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/workflow.py)：
     - `POST /api/v1/workflow/definitions`：建立流程定義。
     - `POST /api/v1/workflow/versions`：發布流程版本。
     - `POST /api/v1/workflow/instances/submit`：送簽與主管鏈管線解析。
     - `POST /api/v1/workflow/instances/{id}/actions`：執行簽核動作 (APPROVE, REJECT, RETURN)。
     - `GET /api/v1/workflow/inbox`：個人簽核待辦清單 (Inbox)。
     - `GET /api/v1/workflow/instances/{id}`：流程實例詳情與節點軌跡查詢。

#### 2. 測試命令與實際執行結果 (Test Commands & Verified Execution)

- **後端簽核引擎專屬測試 (pytest)**：
  - 指令：`python -m pytest apps/api/tests/test_workflow_engine.py -v`
  - 結果：`5 passed in 1.67s`
    - `test_workflow_threshold_pipeline_resolution`：通過 (門檻條件過濾管線解析正確：金額 20,000 跳過二級主管直接由直屬主管簽核，金額 80,000 成功解析兩層主管鏈)。
    - `test_missing_approver_blocked`：通過 (主管鏈斷鏈時安全阻擋送簽，拋出 `400 WORKFLOW_MISSING_APPROVER`)。
    - `test_self_approval_prevention`：通過 (主管送簽自身申請單時觸發防自簽機制，自動跳關或拒絕自審自批)。
    - `test_workflow_lifecycle_approve_reject_return`：通過 (送簽 -> 核准流轉至次節點 -> 退回至前節點 -> 重新送簽 -> 駁回生命週期原子推進完整驗證)。
    - `test_workflow_unauthorized_approver_rejection`：通過 (非指定受派人執行簽核操作遭 403 阻擋)。
- **全套後端測試回歸驗證 (pytest)**：
  - 指令：`python -m pytest apps/api/tests -v`
  - 結果：`21 passed in 5.28s` (鑑權、日曆、人事主檔、假額帳本、簽核引擎全部通過)。
- **前端測試與型別檢查建置**：
  - 指令：`npm run test` (Vitest：8 passed in 2.51s)
  - 指令：`npm run build` (vue-tsc -b && vite build：0 錯誤，生產環境打包成功)。

### 任務 T06：請假垂直切片 (leave-overtime)

- **執行時間**：2026-10-23
- **架構原則**：
  1. **動態工時折算與日曆排班 (Dynamic Work-Minute Calculation)**：
     - 嚴格禁止「全公司一律預設 8 小時」；依據員工當前所屬班別 ([shifts](file:///c:/Sources/EtronJF8/apps/api/app/models/hr.py#L125)) 之實際上下班時段、休息時間 (`break_minutes`) 與每日標準工時 (`daily_standard_minutes`) 精確折算。
     - 遍歷請假跨越之當地日曆日期，自動跳過公司工作日曆 ([calendar_days](file:///c:/Sources/EtronJF8/apps/api/app/models/hr.py#L143)) 之例假日與國定假日 (`is_working_day == False`)。
     - 等效天數以 `總工作分鐘數 / 班別標準日工時` 進行高精度計算。
  2. **門檻臨界主管鏈管線解析 (3-Day & 10-Day Threshold Boundaries)**：
     - 依據 `docs/WORKFLOW-RULES.md` 標準路徑：`代理人 → 直屬主管 → 第二層主管 (>= 3天) → 第三層主管 (>= 10天) → 人事窗口`。
     - 嚴格實測 3天 (1,440分鐘) 與 10天 (4,800分鐘) 臨界值，包含小於門檻、等於臨界值時的動態管線生成。
  3. **假單時段重疊防護 (Overlap Collision Protection)**：
     - 同一員工在相同起訖時段內，嚴格禁止重複提交請假申請；若與現有審核中 (`SUBMITTED`, `IN_REVIEW`) 或已核准 (`APPROVED`) 的假單交疊，立即拋出 `400 LEAVE_REQUEST_OVERLAP` 阻擋。
  4. **假額帳本不可變原子連動 (Immutable Ledger Lifecycle)**：
     - **送審 (Submit)**：折算工時後呼叫 [LeaveLedgerService.hold_leave](file:///c:/Sources/EtronJF8/apps/api/app/core/hr_rules.py#L161) 預占假額；若可用餘額不足即刻拋出 `400 INSUFFICIENT_LEAVE_BALANCE` 阻擋送審；送審成功後將假額凍結並啟動 T05 簽核引擎。
     - **完簽核准 (Approved)**：人事窗口完簽後觸發業務回呼，假單狀態改為 `APPROVED`，帳本自動寫入 `COMMIT` 正式扣抵，並寫入 `RELEASE` 結清並沖銷先前的 `HOLD` 預占分錄，可用餘額維持為扣抵後之正確數值。
     - **駁回／退回／抽單 (Reject/Return/Cancel)**：寫入 `RELEASE` 分錄釋放預占額度，假額全數歸還至可用餘額。

#### 1. 完成工作項目 (Completed Deliverables)

1. **請假主檔資料模型 (Models)**：
   - [apps/api/app/models/leave.py](file:///c:/Sources/EtronJF8/apps/api/app/models/leave.py)：
     - `leave_requests`：申請編號、員工歸屬、假別、起訖 UTC、實際工作分鐘數 (`total_minutes`)、換算天數 (`calculated_days`)、代理人、附件、簽核實例外鍵與修訂版號 (`revision`)。
2. **資料庫遷移腳本 (Alembic Migration)**：
   - 生成並套用遷移腳本 `alembic/versions/f67772d01a5e_create_leave_requests_table.py`，建立 `leave_requests` 資料表與複合查詢索引。
3. **工時折算與重疊防護核心 (Calculators)**：
   - [apps/api/app/core/leave_calculator.py](file:///c:/Sources/EtronJF8/apps/api/app/core/leave_calculator.py)：
     - `calculate_leave_minutes_and_days`：跨時區、班別時段交集、扣除午休、跳過週末與國定假日之精確工時計算。
     - `check_leave_overlap`：申請單時間區段交疊碰撞檢驗。
4. **請假業務與帳本簽核連動核心 (Leave Service)**：
   - [apps/api/app/core/leave_service.py](file:///c:/Sources/EtronJF8/apps/api/app/core/leave_service.py)：
     - `LeaveService.create_leave_request`：建立草稿並試算工時。
     - `LeaveService.submit_leave_request`：防超支 HOLD 預占 + 啟動 T05 簽核引擎。
     - `LeaveService.process_approval`：核准完簽 COMMIT 扣抵 / 駁回退回 RELEASE 釋放。
     - `LeaveService.cancel_leave_request`：申請人抽單釋放。
5. **請假 RESTful API 路由 (API Endpoints)**：
   - [apps/api/app/api/v1/leave.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/leave.py) 與 [apps/api/app/api/v1/router.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/router.py)：
     - `POST /api/v1/leave/calculate`：工時折算試算端點。
     - `POST /api/v1/leave/requests`：建立請假單草稿。
     - `POST /api/v1/leave/requests/{id}/submit`：送審請假單。
     - `GET /api/v1/leave/requests/{id}`：請假單詳情與簽核快照查詢。
     - `POST /api/v1/leave/requests/{id}/cancel`：撤銷請假單。
     - `POST /api/v1/leave/assignments/{id}/action`：簽核動作推進。

#### 2. 測試命令與實際執行結果 (Test Commands & Verified Execution)

- **請假垂直切片專屬測試 (pytest)**：
  - 指令：`python -m pytest apps/api/tests/test_leave_vertical_slice.py -v`
  - 結果：`5 passed in 0.83s` (100% 通過)
    - `test_leave_work_minute_and_rest_deduction`：通過 (精確折算整天 480分/1天、半天扣午休 180分、跨週末排除週六週日計 960分/2天)。
    - `test_leave_threshold_boundaries_3_and_10_days`：通過 (2.5天排除二級主管；剛好3天成功生成二級主管節點；達到10天成功生成二級與三級主管完整鏈)。
    - `test_leave_ledger_atomic_lifecycle_approve_and_reject`：通過 (GRANT 4800分 -> HOLD 1440分剩餘3360分 -> 代理/直屬/二級/人事四級完簽 -> COMMIT 扣抵與沖銷預占 -> 餘額維持3360分)。
    - `test_leave_overdraw_protection_and_overlap_rejection`：通過 (假額不足 400 INSUFFICIENT_LEAVE_BALANCE 攔截成功；重疊請假 400 LEAVE_REQUEST_OVERLAP 攔截成功)。
    - `test_leave_http_api_flow`：通過 (RESTful API 端到端工時試算、建立草稿、CSRF 驗證、送審啟動流程與詳情快照查詢)。
- **全套後端測試回歸驗證 (pytest)**：
  - 指令：`python -m pytest apps/api/tests -v`
  - 結果：`26 passed in 4.11s` (全模組 100% 通過)。
- **前端測試與型別檢查建置**：
  - 指令：`npm run test` (Vitest：8 passed in 2.20s)。
  - 指令：`npm run build` (vue-tsc -b && vite build：0 錯誤，生產環境打包成功)。

### 任務 T07：加班模組 (leave-overtime)

- **執行時間**：2026-10-23
- **架構原則**：
  1. **日曆屬性與加班級距折算 (Overtime Calculation & Tier Rates)**：
     - 比對公司工作日曆 ([CalendarDay](file:///c:/Sources/EtronJF8/apps/api/app/models/hr.py#L143))，自動辨識該日為**平日延長工時 (`REGULAR`)**、**休息日 (`REST_DAY`)** 或**例假日／國定假日 (`REGULAR_HOLIDAY`, `NATIONAL_HOLIDAY`)**。
     - 扣除用餐與休息時間 (`rest_minutes`) 計算淨工時，並分段計算前 2 小時、第 3~4 小時或休假日對應之級距分鐘數。
  2. **加班補償意向 (Compensation Choice: Pay vs. Compensatory Leave)**：
     - `PAY` (加班費)：完簽後標記待計薪清冊，不寫入假額帳本。
     - `COMPENSATORY_LEAVE` (轉補休)：完簽核准後自動將核定之補休分鐘數以 **給予 (GRANT)** 分錄寫入 [leave_ledger](file:///c:/Sources/EtronJF8/apps/api/app/models/hr.py#L178) 假額不可變帳本（有效期限自加班日起 1 年），可用補休額度即刻增加，無縫銜接 T04 假額查詢與 T06 請假抵扣！
  3. **主管鏈簽核管線 (Workflow Pipeline)**：
     - 依據 `docs/WORKFLOW-RULES.md` 規範路徑：`直屬主管 (DIRECT_MANAGER) → 人事窗口 (HR_OFFICER)`。
  4. **防時段重疊碰撞 (Overlap Collision Protection)**：
     - 同一員工在相同起訖時段內禁止重複提交加班申請，遭 `400 OVERTIME_REQUEST_OVERLAP` 攔截。

#### 1. 完成工作項目 (Completed Deliverables)

1. **加班主檔資料模型 (Models)**：
   - [apps/api/app/models/overtime.py](file:///c:/Sources/EtronJF8/apps/api/app/models/overtime.py)：
     - `overtime_requests`：申請單號、員工、起訖 UTC、休息分鐘、淨工時 (`total_minutes`)、日別屬性 (`day_type`)、補償意向 (`compensation_type`)、補休分鐘 (`comp_leave_minutes`)、簽核實例外鍵與修訂版號。
2. **資料庫遷移腳本 (Alembic Migration)**：
   - 生成並套用遷移腳本 `alembic/versions/693aea05a77e_create_overtime_requests_table.py`，建立 `overtime_requests` 資料表與複合查詢索引。
3. **時數折算與防重疊核心 (Calculators)**：
   - [apps/api/app/core/overtime_calculator.py](file:///c:/Sources/EtronJF8/apps/api/app/core/overtime_calculator.py)：
     - `calculate_overtime_minutes`：平日/休息日/假日日曆判定、扣除休息時間與級距折算。
     - `check_overtime_overlap`：申請單時段交疊碰撞檢驗。
4. **加班業務與假額帳本連動核心 (Overtime Service)**：
   - [apps/api/app/core/overtime_service.py](file:///c:/Sources/EtronJF8/apps/api/app/core/overtime_service.py)：
     - `OvertimeService.create_overtime_request`：建立草稿並試算工時。
     - `OvertimeService.submit_overtime_request`：送審並啟動 T05 簽核引擎 (`直屬主管 → 人事窗口`)。
     - `OvertimeService.process_approval`：核准完簽自動 GRANT 補休假額入帳、駁回與退回狀態更新。
     - `OvertimeService.cancel_overtime_request`：申請人抽單處理。
5. **加班 RESTful API 路由 (API Endpoints)**：
   - [apps/api/app/api/v1/overtime.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/overtime.py) 與 [apps/api/app/api/v1/router.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/router.py)：
     - `POST /api/v1/overtime/calculate`：加班時數試算端點。
     - `POST /api/v1/overtime/requests`：建立加班單草稿。
     - `POST /api/v1/overtime/requests/{id}/submit`：送審加班單。
     - `GET /api/v1/overtime/requests/{id}`：加班單詳情與簽核快照查詢。
     - `POST /api/v1/overtime/requests/{id}/cancel`：撤銷加班單。
     - `POST /api/v1/overtime/assignments/{id}/action`：簽核動作推進。

#### 2. 測試命令與實際執行結果 (Test Commands & Verified Execution)

- **加班垂直切片專屬測試 (pytest)**：
  - 指令：`python -m pytest apps/api/tests/test_overtime_vertical_slice.py -v`
  - 結果：`5 passed in 1.02s` (100% 通過)
    - `test_overtime_calculation_regular_and_holiday`：通過 (平日延長扣除休息折算 210分、休息日折算 480分與級距分段驗證正確)。
    - `test_overtime_comp_leave_grant_to_leave_ledger`：通過 (選擇補休 240分 -> 直屬主管審核 -> 人事窗口完簽 -> 自動在 leave_ledger 產生 GRANT 240分入帳，可用補休餘額增加 240分)。
    - `test_overtime_pay_choice_no_leave_granted`：通過 (選擇加班費 PAY -> 完簽狀態 APPROVED，帳本不增加補休假額)。
    - `test_overtime_overlap_protection`：通過 (同時段重複申請加班遭 400 OVERTIME_REQUEST_OVERLAP 攔截)。
    - `test_overtime_http_api_flow`：通過 (RESTful API 端到端試算、建立草稿、CSRF 驗證、送審啟動主管鏈與詳情快照查詢)。
- **全套後端測試回歸驗證 (pytest)**：
  - 指令：`python -m pytest apps/api/tests -v`
  - 結果：`31 passed in 6.89s` (全模組 100% 通過)。
- **前端測試與型別檢查建置**：
  - 指令：`npm run test` (Vitest：8 passed in 2.47s)。
  - 指令：`npm run build` (vue-tsc -b && vite build：0 錯誤，生產環境打包成功)。

### 任務 T08：出差及結報 (travel-settlement)

- **執行時間**：2026-10-23
- **架構原則**：
  1. **出差申請與預支款差異化動態管線 (Travel Pipeline Dynamic Resolution)**：
     - 無預支款 (`has_advance==false`)：`工作代理人 (AGENT) → 直屬主管 (DIRECT_MANAGER) → 人事窗口 (HR_OFFICER)`（共 3 關，自動排除會計窗口）。
     - 有預支款 (`has_advance==true`)：`工作代理人 (AGENT) → 直屬主管 (DIRECT_MANAGER) → 會計窗口 (FINANCE_OFFICER) → 人事窗口 (HR_OFFICER)`（共 4 關，啟動會計審核預支款合理性）。
  2. **多幣別匯率折算與預支沖銷精確核算 (Multi-currency & Advance Offset)**：
     - 嚴格禁用浮點數，全面採用高精度 `Numeric(14, 4)` / Python `Decimal`。
     - 費用明細支援多幣別（如 JPY、USD、EUR 等），每筆獨立記錄原始金額與折合本位幣匯率。
     - 結報單自動折算總支出折合本位幣 (`total_actual_twd`)，扣除出差申請預支款折算抵扣額 (`advance_offset_amount`)，精確計算應補發（正數）或應退繳繳回（負數）金額 (`net_payable_amount`)。
  3. **出差結報單生命週期與防重複報支 (Anti-Duplicate & Settlement Lifecycle)**：
     - 只有狀態為 `APPROVED` 且結報狀態為 `UNSETTLED` 之出差單才可開立結報單。
     - 開立結報單後出差單狀態轉為 `SETTLING`，禁止任何重複開立結報行為（遭 `400 TRAVEL_ALREADY_SETTLED_OR_SETTLING` 攔截）。
     - 結報單簽核管線為：`直屬主管 (DIRECT_MANAGER) → 會計窗口 (FINANCE_OFFICER)`。
     - 結報單完簽核准後出差單狀態轉為 `SETTLED`，結報單進入 `payment_status == UNPAID` 等待財務出納付款／沖銷。
  4. **會計付款結清與財務拋轉準備 (Payment Confirmation & Accounting Ready)**：
     - 會計窗口執行 `confirm_payment`，記錄付款單據流水號 (`paid_reference`) 與付款時間戳記 (`paid_at`)，結報單轉為 `PAID`。已付款單據嚴格禁止重複確認。

#### 1. 完成工作項目 (Completed Deliverables)

1. **出差及結報主檔模型 (Models)**：
   - [apps/api/app/models/travel.py](file:///c:/Sources/EtronJF8/apps/api/app/models/travel.py)：
     - `travel_requests`：出差單號 (`TR-YYYYMMDD-XXXX`)、員工、起訖日期、預估天數、交通方式、職務代理人、預支款標記 (`has_advance`)、預支幣別與金額 (`Numeric(14, 4)`)、簽核狀態與結報狀態 (`UNSETTLED`, `SETTLING`, `SETTLED`)。
     - `travel_settlements`：結報單號 (`TS-YYYYMMDD-XXXX`)、關聯出差單外鍵、幣別與匯率快照、總支出本位幣金額、預支沖銷額、應補退淨額 (`net_payable_amount`)、單據收據張數、付款狀態 (`UNPAID`, `PAID`)、付款參照號與付款時間。
     - `travel_expense_items`：費用項目明細（交通、住宿、餐飲、什支等）、原始幣別與金額、折算匯率、折合本位幣金額 (`amount_twd`)、發票憑證號碼、說明與附件 URL。
2. **資料庫遷移腳本 (Alembic Migration)**：
   - 生成並套用遷移腳本 `alembic/versions/0b0b5605781c_create_travel_and_settlement_tables.py`，建立 `travel_requests`, `travel_settlements`, `travel_expense_items` 資料表與外鍵約束。
3. **出差及結報領域服務核心 (Travel Service)**：
   - [apps/api/app/core/travel_service.py](file:///c:/Sources/EtronJF8/apps/api/app/core/travel_service.py)：
     - `create_travel_request`、`submit_travel_request`：出差申請與有／無預支差異化簽核管線動態解析。
     - `create_travel_settlement`：結報開立、出差單完簽檢驗、防重複報支、多幣別匯率換算與淨應補退計算。
     - `submit_travel_settlement`：結報送審主管鏈（主管 → 會計窗口）。
     - `confirm_payment`：會計付款結清確認與沖銷防呆。
4. **出差及結報 RESTful API 路由 (API Endpoints)**：
   - [apps/api/app/api/v1/travel.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/travel.py) 與 [apps/api/app/api/v1/router.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/router.py)：
     - `POST /api/v1/travel/requests`：建立出差單。
     - `GET /api/v1/travel/requests`：查詢出差單列表。
     - `POST /api/v1/travel/requests/{id}/submit`：送審出差單。
     - `GET /api/v1/travel/requests/{id}`：出差單詳情與簽核快照查詢。
     - `POST /api/v1/travel/settlements`：建立結報單。
     - `POST /api/v1/travel/settlements/{id}/submit`：送審結報單。
     - `GET /api/v1/travel/settlements/{id}`：結報單明細與審批快照查詢。
     - `POST /api/v1/travel/settlements/{id}/confirm-payment`：會計付款結清確認。
     - `POST /api/v1/travel/assignments/{id}/travel-action`、`settlement-action`：簽核動作推進。

#### 2. 測試命令與實際執行結果 (Test Commands & Verified Execution)

- **出差垂直切片專屬測試 (pytest)**：
  - 指令：`python -m pytest apps/api/tests/test_travel_vertical_slice.py -v`
  - 結果：`6 passed in 2.88s` (100% 通過)
    - `test_travel_pipeline_without_advance`：通過 (無預支出差單管線為：工作代理人審核 -> 直屬主管審核 -> 人事窗口核備，共 3 關)。
    - `test_travel_pipeline_with_advance`：通過 (有預支出差單管線為：工作代理人審核 -> 直屬主管審核 -> 會計窗口審核 (有預支款) -> 人事窗口核備，共 4 關)。
    - `test_travel_settlement_multicurrency_and_advance_offset`：通過 (JPY、USD、TWD 多幣別匯率換算、預支款折合本位幣抵扣、應補發正數與應繳回退款負數之 Decimal 精確計算無失真)。
    - `test_travel_anti_duplicate_settlement`：通過 (未完簽出差單禁止結報；已結報出差單禁止重複開立結報單遭 400 攔截)。
    - `test_travel_settlement_approval_and_payment_confirmation`：通過 (結報管線直屬主管 -> 會計窗口核准完簽後狀態為 APPROVED，會計執行 confirm_payment 成功轉為 PAID，重複確認遭 400 ALREADY_PAID 攔截)。
    - `test_travel_http_api_flow`：通過 (RESTful API 端到端認證、CSRF 防護、出差單建立、查詢列表、送審啟動工作流與詳情快照查詢)。
- **全套後端測試回歸驗證 (pytest)**：
  - 指令：`python -m pytest apps/api/tests -v`
  - 結果：`37 passed in 9.59s` (全模組 37 項測試 100% 通過)。
- **前端測試與型別檢查建置**：
  - 指令：`npm run test` (Vitest：8 passed in 2.45s)。
  - 指令：`npm run build` (vue-tsc -b && vite build：0 錯誤，生產環境打包成功)。

### 任務 T09：費用、供應商及請款 (expense-payment)

- **執行時間**：2026-10-23
- **架構原則**：
  1. **費用報支門檻主管鏈管線 (Expense Threshold Pipeline)**：
     - `< 5000`：`直屬主管 (DIRECT_MANAGER) → 會計窗口 (FINANCE_WINDOW)`。
     - `>= 5000 且 < 100000`：`直屬主管 (DIRECT_MANAGER) → 第二層主管 (MANAGER_L2, >=5000) → 會計窗口 (FINANCE_WINDOW)`。
     - `>= 100000`：`直屬主管 (DIRECT_MANAGER) → 第二層主管 (MANAGER_L2, >=5000) → 第三層主管 (MANAGER_L3, >=100000) → 會計窗口 (FINANCE_WINDOW)`。
  2. **可能重複憑證警示機制 (Potential Duplicate Invoice Warning)**：
     - 規格明確規範：「建立可能重複憑證警示，不能單用發票號碼做全公司絕對唯一」。
     - 系統在建立或送審時，搜尋公司內是否有其他非取消/駁回單據中存在相同 `invoice_number` 且金額相同之憑證，若有則標記 `has_duplicate_warning = True`，輔助會計窗口重點複核。
  3. **供應商銀行資料遮罩與受款快照不可變性 (Vendor Bank Masking & Snapshot Immutability)**：
     - 非財會人員查詢供應商時，銀行帳號自動遮罩（末4碼顯示，其餘星號，如 `*********7890`）。
     - 規格嚴格要求：「單據保存送簽時供應商及銀行快照，主檔更新不得偷偷改變已核准付款資料」。請款單開立時立馬建立 `vendor_snapshot`，主檔後續異動完全不影響已請款單據之受款資料！
  4. **供應商請款大額多級管線 (Payment Request Multi-level Pipeline)**：
     - `< 5000`：`直屬主管 → 會計窗口`。
     - `>= 5000 且 < 100000`：`直屬主管 → 部級主管 (ORG_DEPT_HEAD, >=5000) → 會計窗口`。
     - `>= 100000 且 < 500000`：`直屬主管 → 部級主管 (ORG_DEPT_HEAD, >=5000) → 處級主管 (ORG_DIV_HEAD, >=100000) → 會計窗口`。
     - `>= 500000`：`直屬主管 → 部級主管 (ORG_DEPT_HEAD, >=5000) → 處級主管 (ORG_DIV_HEAD, >=100000) → 總經理 (GM, >=500000) → 會計窗口`。
  5. **匯兌損益差額核算與 ERP 總帳拋轉準備 (Exchange Gain/Loss Adjustment for GL Readiness)**：
     - 呼應用戶風險提示：「跨國匯率目前以結報／請款當下快照匯率折算，未來若串接 ERP 財務系統拋轉總帳 (GL)，需支援月結結帳匯率差額調整機制 (Exchange Gain/Loss Adjustment)」。
     - 會計人員執行 `confirm_payment` 時，支援輸入實際結算匯率 (`settlement_exchange_rate`)，系統自動精確核算 `exchange_gain_loss = amount * (settlement_exchange_rate - exchange_rate)`，並具備 `gl_posted` 拋轉追蹤欄位。

#### 1. 完成工作項目 (Completed Deliverables)

1. **主檔與單據資料模型 (Models)**：
   - [apps/api/app/models/payment.py](file:///c:/Sources/EtronJF8/apps/api/app/models/payment.py)：
     - `vendors`：供應商代碼、名稱、統編/法人番號、付款條件、銀行帳戶欄位、遮罩方法 `masked_account_number()` 與樂觀鎖。
     - `expense_claims`：費用報銷單號 (`EXP-YYYYMMDD-XXXX`)、員工、幣別匯率、本位幣金額 (`Numeric(14, 4)`)、稅額、成本中心、重複憑證警示標記、付款狀態與匯兌損益。
     - `expense_claim_items`：費用項目明細、發票/收據號碼、原始幣別金額與折合本位幣金額。
     - `payment_requests`：請款單號 (`PAY-YYYYMMDD-XXXX`)、供應商外鍵、**供應商與受款銀行不可變快照 (`vendor_snapshot`)**、請款金額、預計付款日、付款方式、簽核狀態、付款狀態與匯兌損益。
2. **資料庫遷移腳本 (Alembic Migration)**：
   - 生成並套用遷移腳本 `alembic/versions/0a582276b3e1_create_expense_and_payment_tables.py`，建立 `vendors`, `expense_claims`, `expense_claim_items`, `payment_requests` 資料表與複合索引。
3. **業務領域服務核心 (Payment Service)**：
   - [apps/api/app/core/payment_service.py](file:///c:/Sources/EtronJF8/apps/api/app/core/payment_service.py)：
     - 供應商維護與遮罩查詢。
     - 費用報銷建立、重複憑證偵測、門檻送審、審核推進與付款確認。
     - 供應商請款建立、不可變快照擷取、大額多級送審（主管/部/處/GM/會計）、審核推進與會計付款結清（自動計算匯兌損益）。
4. **RESTful API 端點 (API Endpoints)**：
   - [apps/api/app/api/v1/payment.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/payment.py) 與 [apps/api/app/api/v1/router.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/router.py)：
     - `POST /api/v1/vendors`、`GET /api/v1/vendors`、`GET /api/v1/vendors/{id}`。
     - `POST /api/v1/expense/claims`、`GET /api/v1/expense/claims`、`POST /api/v1/expense/claims/{id}/submit`、`GET /api/v1/expense/claims/{id}`、`POST /api/v1/expense/claims/{id}/confirm-payment`。
     - `POST /api/v1/payment/requests`、`GET /api/v1/payment/requests`、`POST /api/v1/payment/requests/{id}/submit`、`GET /api/v1/payment/requests/{id}`、`POST /api/v1/payment/requests/{id}/confirm-payment`。

#### 2. 測試命令與實際執行結果 (Test Commands & Verified Execution)

- **費用與請款垂直切片專屬測試 (pytest)**：
  - 指令：`python -m pytest apps/api/tests/test_payment_vertical_slice.py -v`
  - 結果：`6 passed in 2.47s` (100% 通過)
    - `test_expense_claim_threshold_boundaries`：通過 (費用報銷 <5000, >=5000, >=100000 門檻管線解析與簽核推進正確)。
    - `test_expense_claim_duplicate_warning_and_payment`：通過 (相同發票號碼與金額觸發 has_duplicate_warning=True，會計確認付款轉為 PAID，重複確認遭 400 攔截)。
    - `test_vendor_bank_masking_and_snapshot_immutability`：通過 (非財會查詢帳號遮罩為 *********7890；請款單生成時儲存快照，主檔被竄改後請款單內快照完全不受影響)。
    - `test_payment_request_threshold_pipeline`：通過 (供應商請款 <5000, >=5000 部級, >=100000 處級, >=500000 總經理管線階層解析正確，依序核准至完簽)。
    - `test_multicurrency_exchange_gain_loss_for_erp_gl`：通過 (USD 10,000 請款匯率 32.0000，實際付款匯率 32.5000，精確核算 exchange_gain_loss = +5000.0000 TWD)。
    - `test_payment_and_expense_http_api_flow`：通過 (RESTful API 端到端認證、CSRF 防護、供應商建立與遮罩查詢、費用報銷建立與送審、供應商請款建立與送審)。
  - 結果：`43 passed in 11.85s` (全模組 43 項測試 100% 通過)。
- **前端測試與型別檢查建置**：
  - 指令：`npm run test` (Vitest：8 passed in 2.47s)。
  - 指令：`npm run build` (vue-tsc -b && vite build：0 錯誤，生產環境打包成功)。

### 任務 T10：用印及合約 (seal-contract)

- **執行時間**：2026-10-23
- **架構原則**：
  1. **印鑑清冊主檔與保管人交接審計留痕 (Seal Registry & Handover Audit)**：
     - 印鑑主檔記錄類型（公司大印、代表人章、合約專用章、財務章）、所屬公司、保管人員工 ID 與生效起訖日期。
     - 保管人異動執行合規交接 (`handover_seal`)，原子記錄原保管人、新保管人、交接日期與理由 (`seal_handovers`)，樂觀鎖版本遞增，杜絕印鑑責任真空。
  2. **用印申請簽核與實體用印登記狀態機分離 (Seal Request & Physical Execution Decoupling)**：
     - 規格核心原則：「**簽核核准不等於已用印**，保管人執行後記錄日期、份數、實際執行者與完成文件」。
     - 用印申請管線：`直屬主管 (DIRECT_MANAGER) → 印鑑保管人 (SEAL_CUSTODIAN)`。
     - 簽核完畢後狀態為 `APPROVED`，但實體用印狀態為 `NOT_SEALED`（待用印）。
     - 由印鑑保管人實體用印後登記執行紀錄 (`execute_seal`)，填寫實際蓋印份數與正式完成掃描件 URL，狀態轉為 `SEALED`。已用印單據嚴禁重複登記。
  3. **合約金額門檻與動態用印管線 (Contract Threshold & Dynamic Seal Pipeline)**：
     - `< 5000` (如無金額 NDA)：`直屬主管 → 法務窗口`。
     - `>= 5000 且 < 100000`：`直屬主管 → 第二層主管 (>=5000) → 法務窗口`。
     - `>= 100000`：`直屬主管 → 第二層主管 (>=5000) → 第三層主管 (>=100000) → 法務窗口`。
     - **動態用印節點串接**：若合約標記 `needs_seal == true`，法務審查後自動動態推進至 `印鑑保管人執行 (需用印)` 節點；若無須用印則於法務窗口核准後直接完簽！
  4. **法務意見留痕與合約生命週期歸檔 (Legal Opinion & Lifecycle Archive)**：
     - 法務審查時同步於合約主檔寫入正式法律審查意見 (`legal_opinion`)。
     - 完簽核准後合約狀態轉為 `ACTIVE`。
     - 雙方簽署完成後執行歸檔作業 (`archive_contract`)，儲存雙方用印簽署掃描件 (`signed_document_url`) 與歸檔日期。
     - 支援續約合約關聯 (`renewed_from_contract_id`)，完整串聯跨年度採購與服務協議歷程。

#### 1. 完成工作項目 (Completed Deliverables)

1. **主檔與單據資料模型 (Models)**：
   - [apps/api/app/models/seal_contract.py](file:///c:/Sources/EtronJF8/apps/api/app/models/seal_contract.py)：
     - `seals`：印鑑代碼、名稱、類型、保管人外鍵、生效起訖與樂觀鎖。
     - `seal_handovers`：印鑑保管人更換交接審計日誌。
     - `seal_requests`：用印申請單號 (`SEAL-YYYYMMDD-XXXX`)、文件名稱、版本、用途、申請份數、簽核狀態 (`APPROVED`)、實體用印狀態 (`NOT_SEALED` / `SEALED`)、實際用印時間、實際份數與完成件 URL。
     - `contracts`：合約編號 (`CTR-YYYYMMDD-XXXX`)、相對人、標題、合約類型、金額幣別、期限起訖、自動續約、是否需用印 (`needs_seal`)、法務意見 (`legal_opinion`)、生命週期狀態 (`ACTIVE`)、簽署掃描件與續約關聯。
2. **資料庫遷移腳本 (Alembic Migration)**：
   - 生成並套用遷移腳本 `alembic/versions/22c1c4a76b4d_create_seal_and_contract_tables.py`，建立 `seals`, `seal_handovers`, `seal_requests`, `contracts` 資料表與外鍵索引。
3. **業務領域服務核心 (Seal & Contract Service)**：
   - [apps/api/app/core/seal_contract_service.py](file:///c:/Sources/EtronJF8/apps/api/app/core/seal_contract_service.py)：
     - 印鑑主檔維護、保管人交接與歷史查詢。
     - 用印申請開立、直屬主管與保管人送審、審批推進、保管人實體用印登記（簽核與實體用印狀態分離）。
     - 合約審查申請、金額門檻管線解析、法務審查意見錄入、需用印動態管線推進、合約歸檔與續約關聯追蹤。
4. **RESTful API 端點 (API Endpoints)**：
   - [apps/api/app/api/v1/seal_contract.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/seal_contract.py) 與 [apps/api/app/api/v1/router.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/router.py)：
     - `POST /api/v1/seals`、`GET /api/v1/seals`、`POST /api/v1/seals/{id}/handover`、`GET /api/v1/seals/{id}/handovers`。
     - `POST /api/v1/seal/requests`、`GET /api/v1/seal/requests`、`POST /api/v1/seal/requests/{id}/submit`、`GET /api/v1/seal/requests/{id}`、`POST /api/v1/seal/requests/{id}/execute`。
     - `POST /api/v1/contracts`、`GET /api/v1/contracts`、`POST /api/v1/contracts/{id}/submit`、`GET /api/v1/contracts/{id}`、`POST /api/v1/contracts/{id}/archive`、`POST /api/v1/contracts/assignments/{id}/action`。

#### 2. 測試命令與實際執行結果 (Test Commands & Verified Execution)

- **用印與合約垂直切片專屬測試 (pytest)**：
  - 指令：`python -m pytest apps/api/tests/test_seal_contract_vertical_slice.py -v`
  - 結果：`6 passed in 1.91s` (100% 通過)
    - `test_seal_registry_and_handover_audit`：通過 (印鑑主檔建立、保管人交接審計留痕、交接歷史紀錄與錯誤保管人交接防呆)。
    - `test_seal_request_pipeline_and_execution`：通過 (用印管線直屬主管 -> 印鑑保管人審核；簽核核准後狀態為 APPROVED 但 NOT_SEALED，保管人實體用印後轉為 SEALED，防重複登記)。
    - `test_contract_threshold_pipeline`：通過 (合約 <5000, >=5000, >=100000 門檻主管鏈管線解析與送審正確)。
    - `test_contract_needs_seal_dynamic_pipeline_and_legal_opinion`：通過 (needs_seal=True 自動串接印鑑保管人節點，法務審查意見 legal_opinion 成功保存，合約完簽轉為 ACTIVE)。
    - `test_contract_archive_and_renewal_linkage`：通過 (完簽合約歸檔上傳簽署文件與歸檔時間，建立新合約精確關聯 renewed_from_contract_id)。
    - `test_seal_and_contract_http_api_flow`：通過 (RESTful API 端到端認證、CSRF 防護、印鑑建立、用印申請送審、合約建立送審與詳情查詢)。
- **全套後端測試回歸驗證 (pytest)**：
  - 指令：`python -m pytest apps/api/tests -v`
  - 結果：`49 passed in 13.86s` (全模組 49 項測試 100% 通過)。
- **前端測試與型別檢查建置**：
  - 指令：`npm run test` (Vitest：8 passed in 2.39s)。
  - 指令：`npm run build` (vue-tsc -b && vite build：0 錯誤，生產環境打包成功)。

#### 3. 風險提示與 ERP 總帳拋轉架構備忘 (Risk Notes & ERP GL Integration)

- **跨國請款與外幣費用報銷 ERP 總帳拋轉 (ERP GL Posting & FX Valuation)**：
  - 本系統已在費用報銷 (`expense_reports`) 與請款申請 (`payment_requests`) 全面建置 `settlement_exchange_rate`、`exchange_gain_loss` 與 `gl_posted` 核心財務欄位，並驗證多幣別實際兌換損益精確核算（禁用浮點數，全採 `Numeric(14, 4)` / `Decimal`）。
  - **未來串接外部 ERP（如 SAP、Oracle 或鼎新）之前置要件**：
    1. 需由財務部門核定「匯兌損益會計科目編號（GL Account）」以及拋轉總帳對應借貸分錄邏輯。
    2. 核定月底「未實現匯兌評價（Unrealized FX Valuation）」之批次拋轉排程與匯率取用基準日（月底評價基準匯率 vs 請款日快照匯率）。
  - 已將此架構決策同步收錄於 [docs/DECISIONS.md](file:///c:/Sources/EtronJF8/docs/DECISIONS.md) `D16`。

### 任務 T11：出勤匯入與查詢 (attendance-import)

- **執行時間**：2026-10-23
- **架構原則**：
  1. **多編碼與多格式明確指定解析 (Explicit Multi-encoding & Multi-format Parsing)**：
     - 支援 `CSV`、`XLSX`、`TSV`、`TXT` 格式。
     - 文字檔明確支援指定 `UTF-8`、`UTF-8-SIG` (BOM)、`CP950` (繁中 Big5)、`Shift_JIS` (日文)，**嚴格拒絕靜默猜測**編碼入庫；遭遇非法編碼位元組時明確拋出 `INVALID_ENCODING` 400 錯誤。
     - 計算 SHA-256 檔案雜湊 (`file_hash`) 記錄於批次主檔，防重複檔案誤傳。
  2. **標準匯入管線與過期預覽防護 (Lifecycle Pipeline & Stale Preview Protection)**：
     - 管線階段：`上傳 (Upload)` → `解析 (Parse)` → `欄位映射 (Mapping)` → `時區與時間格式解析 (Timezone & Datetime Format)` → `預覽與驗證 (Preview & Validation)` → `確認入庫 (Commit)` → `錯誤報告 (Error Report)`。
     - 預覽驗證時計算 `preview_revision` 快照修訂雜湊，入庫時必須匹配未過期之修訂版號，過期或未驗證之預覽禁止直接 commit 入庫 (`STALE_PREVIEW_REVISION`)。
  3. **設備識別與自然鍵雙層去重 (De-duplication in Batch & Historical)**：
     - 優先依賴設備打卡事件識別碼 (`device_id` + `source_event_id`) 進行同檔與跨歷史檔案去重。
     - 次之依賴自然鍵 (`company_id` + `employee_id` + `event_at_utc`) 去重，重複列自動標註為 `SKIPPED_DUPLICATE` 並記錄錯誤摘要，不阻斷其他合法列正常入庫。
  4. **跨夜班工作日排班歸屬演算法 (Night Shift Work Date Attribution)**：
     - 員工排跨夜班（如 20:00 ~ 04:00+1，`is_overnight == True`）時，次日凌晨 00:00 至中午前之打卡事件，透過演算法查詢昨日排班指派 (`shift_assignments`)，將其業務工作日 (`work_date`) 歸屬至前一日排班日期，而非直接取 UTC 或曆日。
  5. **多次打卡支援與不可覆寫原始事件 (Multiple Punches & Immutable Raw Events)**：
     - 打卡不限於上下班兩次，支援同一天多次打卡 (上班、午休外出、返回、下班等)，完整保留於 `attendance_events`。
     - 原始打卡事實不可竄改覆寫；若有忘刷或異常補登，透過獨立之考勤修正主檔 (`attendance_corrections`) 審計留痕。
  6. **安全性防護與公司物件授權 (Security, Formula Injection Protection & IDOR Isolation)**：
     - CSV 匯出防公式注入：針對 `=`, `+`, `-`, `@` 開頭之字串自動添加單引號跳脫前綴，防止試算表軟體（Excel / Calc）執行任意公式。
     - 嚴格落實多租戶公司範圍隔離 (`FORBIDDEN_COMPANY_SCOPE`)，跨公司存取批次、錯誤報告或匯出考勤皆遭 403 阻擋。

#### 1. 完成工作項目 (Completed Deliverables)

1. **主檔與單據資料模型 (Models)**：
   - [apps/api/app/models/attendance.py](file:///c:/Sources/EtronJF8/apps/api/app/models/attendance.py)：
     - `shift_assignments`：排班指派主檔，支援個別日期特定班別指派與跨夜判定。
     - `attendance_import_batches`：匯入批次記錄 (狀態、編碼、時區、預覽版本快照、統計列數)。
     - `attendance_import_rows`：逐列明細快照 (原始值、正規化值、錯誤碼、行號)。
     - `attendance_events`：原始打卡事件 (不可覆寫、UTC instant、來源時區、原始時間字串、歸屬工作日、跨夜標記、設備 ID、外部事件 ID)。
     - `attendance_corrections`：打卡修正記錄 (補打卡/修改時間/作廢標記審計留痕)。
     - `attendance_daily_summaries`：每日出勤匯總 (打卡次數、首末刷時間、出勤狀態)。
2. **資料庫遷移腳本 (Alembic Migration)**：
   - 生成並套用遷移腳本 `alembic/versions/103ad21b497a_create_attendance_tables.py`，建立 6 張出勤相關資料表與外鍵去重複合索引。
3. **業務領域服務核心 (Attendance Service)**：
   - [apps/api/app/core/attendance_service.py](file:///c:/Sources/EtronJF8/apps/api/app/core/attendance_service.py)：
     - 支援 CSV, XLSX, TSV, TXT 多格式與 UTF-8, UTF-8-SIG, CP950, Shift_JIS 顯式編碼解析。
     - 預覽驗證管線、跨夜班排班歸屬判定、去重過濾與修訂版本生成。
     - 原子性入庫與日報匯總聯動。
     - 防公式注入之安全 CSV 匯出引擎。
4. **RESTful API 端點 (API Endpoints)**：
   - [apps/api/app/api/v1/attendance.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/attendance.py) 與 [apps/api/app/api/v1/router.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/router.py)：
     - `POST /api/v1/attendance/imports/upload` (支援 Multipart 與 JSON Base64/Text 兩種模式)
     - `POST /api/v1/attendance/imports/{id}/preview` (預覽驗證)
     - `POST /api/v1/attendance/imports/{id}/commit` (確認入庫)
     - `GET /api/v1/attendance/imports/{id}/errors` (逐列錯誤報告)
     - `GET /api/v1/attendance/events` (出勤打卡事件查詢與條件篩選)
     - `GET /api/v1/attendance/events/export` (防公式注入 CSV 匯出)
     - `POST /api/v1/attendance/corrections` (考勤打卡修正留痕)

#### 2. 測試命令與實際執行結果 (Test Commands & Verified Execution)

- **出勤垂直切片專屬測試 (pytest)**：
  - 指令：`python -m pytest apps/api/tests/test_attendance_vertical_slice.py -v`
  - 結果：`6 passed in 1.34s` (100% 通過)
    - `test_attendance_multi_encoding_and_format_parsing`：通過 (UTF-8, UTF-8 BOM, CP950, Shift_JIS 與 XLSX, CSV, TSV 均正確解析，非法編碼嚴格拋出 INVALID_ENCODING)。
    - `test_attendance_preview_validation_and_stale_commit_protection`：通過 (未知工號與錯誤時間格式精確回報，過期/偽造預覽版本遭 STALE_PREVIEW_REVISION 攔截，合法版本成功入庫)。
    - `test_attendance_deduplication_in_batch_and_historical`：通過 (同批與跨歷史檔案之設備事件 ID 及自然鍵重複列均自動跳過，不中斷其他有效列)。
    - `test_night_shift_work_date_attribution`：通過 (跨夜大夜班 20:00~04:00+1，次日凌晨下班打卡精準歸屬至前一日工作日期，每日匯總計算正確)。
    - `test_immutable_events_multiple_punches_and_corrections`：通過 (單日 4 次打卡完整保留，補打卡考勤修正寫入審計記錄，原始打卡事件不受任何覆寫破壞)。
    - `test_csv_formula_injection_protection_and_company_idor`：通過 (CSV 匯出自動跳脫 =、+、-、@ 開頭字元；跨公司上傳與匯出遭 403 阻擋)。
- **全套後端測試回歸驗證 (pytest)**：
  - 指令：`python -m pytest apps/api/tests -v`
  - 結果：`55 passed in 15.62s` (全模組 55 項測試 100% 通過)。
- **前端測試與型別檢查建置**：
  - 指令：`npm run test` (Vitest：8 passed in 2.63s)。
  - 指令：`npm run build` (`vue-tsc -b && vite build`：0 錯誤，生產環境打包成功)。

### 任務 T12：安全、UAT與發布 (release-operations)

- **執行時間**：2026-10-23
- **架構原則**：
  1. **系統健康與就緒檢查探針 (Health & Readiness Probes)**：
     - `/api/v1/health`：提供 Liveness 存活檢查，驗證應用程式與 SQLite 資料庫連線狀態。
     - `/api/v1/ready`：提供 Readiness 就緒檢查，驗證 WAL 日誌模式 (`PRAGMA journal_mode=WAL`)、外鍵約束 (`PRAGMA foreign_keys=ON`) 與鎖定逾時 (`busy_timeout=5000`) 正常。
  2. **SQLite WAL 在線零中斷備份與 RTO 復原演練 (Online Backup & RTO Verification)**：
     - 使用原生 `sqlite3.Connection.backup()` 於背景執行在線熱備份，不中斷既有連線讀寫，產出時間戳備份檔並計算 SHA-256 雜湊。
     - 每次備份立即自動執行復原演練，以唯讀模式連線執行 `PRAGMA integrity_check;` 驗證資料頁完整性。
     - 實測備份耗時 `< 50ms` (RPO < 1小時)，完整性校驗與就緒復原耗時 `< 10ms` (RTO < 15分鐘)。
  3. **安全審計日誌與深度個資遮罩 (Audit Logging & Data Masking)**：
     - 建立系統層級安全稽核日誌 (`audit_logs`)，純追加寫入，紀錄操作者、公司、動作、對象、前後狀態、原因、request_id 與 UTC 時間。
     - 遞迴遮罩演算法：自動過濾密碼 (`password`, `hashed_password`)、權杖 (`csrf_token`, `token`) 遮罩為 `********`；銀行帳號僅保留末 4 碼（如 `******7890`），杜絕機密洩漏。
  4. **全模組端到端綜合 UAT 驗收 (Comprehensive Multi-Module UAT)**：
     - 橫跨台北總部與福岡支社，綜合驗收人事組織、打卡出勤、請假帳本、加班補休、出差結報多幣別換算、費用報銷門檻管線、用印合約簽核與實體用印登記。
     - 驗證跨公司 IDOR 權限隔離、CSRF 防護機制與 Session 登出即時撤銷。

#### 1. 完成工作項目 (Completed Deliverables)

1. **平台安全與審計資料模型 (Platform Models)**：
   - [apps/api/app/models/platform.py](file:///c:/Sources/EtronJF8/apps/api/app/models/platform.py)：`Attachment` (隨機儲存識別碼、MIME 與大小驗證)、`AuditLog` (純追加安全稽核日誌)。
2. **資料庫遷移腳本 (Alembic Migration)**：
   - 生成並套用遷移腳本 `alembic/versions/173ef1db1ffc_create_platform_attachments_and_audit_.py`，建立 `attachments` 與 `audit_logs` 資料表與索引。
3. **在線備份與稽核領域服務 (Backup & Audit Service)**：
   - [apps/api/app/core/backup_service.py](file:///c:/Sources/EtronJF8/apps/api/app/core/backup_service.py)：實作在線 WAL 零中斷備份、`PRAGMA integrity_check` 完整性演練與敏感資料遞迴遮罩審計。
4. **維運與部署手冊 (Operations Runbook)**：
   - [docs/OPERATIONS.md](file:///c:/Sources/EtronJF8/docs/OPERATIONS.md)：詳訂同源 HTTPS、SQLite WAL 基準、金鑰隔離、備份命令、災難復原程序與上線發布檢核表。
5. **端到端跨模組綜合 UAT 測試套件 (UAT Test Suite)**：
   - [apps/api/tests/test_release_operations_uat.py](file:///c:/Sources/EtronJF8/apps/api/tests/test_release_operations_uat.py)：4 項全流程綜合情境測試全部通過。

#### 2. 測試命令與實際執行結果 (Test Commands & Verified Execution)

- **T12 專案發布與 UAT 驗收測試 (pytest)**：
  - 指令：`python -m pytest apps/api/tests/test_release_operations_uat.py -v`
  - 結果：`4 passed in 0.98s` (100% 通過)
    - `test_health_and_readiness_probes`：通過 (驗證 /health 與 /ready 探針，SQLite WAL 與 Foreign Keys 正確回傳)。
    - `test_online_backup_and_recovery_integrity`：通過 (在線熱備份生成、SHA-256 驗證、PRAGMA integrity_check 回傳 ok，RTO 測量正常並寫入 audit_logs)。
    - `test_audit_log_sensitive_data_masking`：通過 (密碼遮罩為 ********，銀行帳號遮罩為 ******7890，機密不進日誌)。
    - `test_end_to_end_cross_module_workflow_uat`：通過 (出勤打卡入庫、請假帳本給假、用印合約開立、跨公司 IDOR 阻擋、CSRF 拒絕驗證全數通過)。
- **全套後端測試回歸驗證 (pytest)**：
  - 指令：`python -m pytest apps/api/tests -v`
  - 結果：`59 passed in 16.73s` (涵蓋 T00 至 T12 全部 59 項測試 100% 通過)。
- **前端測試與型別檢查建置**：
  - 指令：`npm run test` (Vitest：8 passed in 2.60s)。
  - 指令：`npm run build` (`vue-tsc -b && vite build`：0 錯誤，生產環境打包成功)。

### 人事系統全模組實施規劃設計 (HR System Full Modules Planning)

- **規劃時間**：2026-10-23
- **業務範疇**：依據 `/plan` 指令，規劃建立完整人事系統（HR System），涵蓋八大核心子模組：
  1. 公司基本資料管理 (Company Master: 台北 ETJ-TW / 福岡 ETJ-JP、法定時區與基準幣別)
  2. 部門基本資料管理 (Department & Organization Tree: 處/部/課多層級、DAG 組織防環驗證)
  3. 員工基本資料管理 (Employee Master: 工號、職務、主管鏈關係與防循環檢驗)
  4. 報到作業 (Employee Onboarding: 基本資料建置、到職分錄、同步開通登入帳號與初始密碼 Argon2id 雜湊)
  5. 員工異動作業 (Employee Change: 部門調動、主管變更、離職安全連動與 Session 立即撤銷、異動歷史時間軸)
  6. 班別設定管理 (Shift Management: 標準工時 480 分鐘、起訖時間、休息時數、跨夜班標記)
  7. 假別主檔管理 (Leave Type Master: 特休、病假、事假、給薪屬性與檢附附件要求)
  8. 員工假別可用天數管理 (Leave Quota Management: 不可變帳本 Immutable Ledger 流水、As-of-Date 可用天數/工時即時換算)
- **產出詳細規格計畫書**：已建立獨立 Artifact [hr_system_implementation_plan.md](file:///C:/Users/wuchi/.gemini/antigravity-ide/brain/56eba4bf-8f97-4ce1-b716-3e3cd5ddbdf4/hr_system_implementation_plan.md)，詳述各模組 API 規格、前端 Vue 元件架構與測試矩陣。

#### 人事系統第一階段：後端 API 補完與規則加固 (Phase 1 Backend Implementation & Rules Hardening)

- **執行時間**：2026-10-23
- **完成項目**：
  1. **員工報到一站式開通 (Onboarding & Account Provisioning)**：
     - 在 [apps/api/app/core/hr_rules.py](file:///c:/Sources/EtronJF8/apps/api/app/core/hr_rules.py) 實作 `onboard_employee`，建立員工主檔並寫入 `ONBOARD` 異動分錄。
     - 支援 `create_user_account=True` 連動在 `users` 表開通帳號，使用 Argon2id 雜湊初始密碼，設定 `is_first_login=True` 強制首登修改密碼，並指派公司範圍 (`UserScope`)。
  2. **員工離職安全聯動與 Session 立即撤銷 (Resignation & Session Revocation)**：
     - 實作 `process_employee_resignation`，將狀態切換為 `RESIGNED`，留存 `RESIGN` 異動歷程。
     - 自動停用關聯使用者帳號 (`is_active = False`)，並**立即撤銷該使用者在伺服器端的所有有效 Session (`is_revoked = True`, `revoked_at = utc_now()`)**，其後續請求拋出 `401 Unauthorized (SESSION_REVOKED)`。
  3. **假額可用天數與帳本流水服務 (Leave Ledger & Quota Calculation)**：
     - 在 `LeaveLedgerService` 實作 `get_ledger_entries` 查詢審計流水（倒序排列）。
     - 實作 `get_leave_quota_summary`，以 480 分鐘（8 小時標準工時）為標準換算可用天數與剩餘分鐘數。
  4. **API 端點全數補完 (API Endpoints)**：
     - [apps/api/app/api/v1/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/hr.py)：
       - `POST /api/v1/hr/employees` (支援報到連動開帳號)
       - `GET /api/v1/hr/employees/{id}` (員工詳情與直屬主管)
       - `GET /api/v1/hr/employees/{id}/changes` (員工異動歷程時間軸)
       - `POST /api/v1/hr/employees/{id}/resign` (離職作業)
       - `GET /api/v1/hr/shifts` (班別清單查詢)
       - `GET /api/v1/hr/calendar-days` (工作日曆查詢)
       - `GET /api/v1/hr/leave-types` (假別清單查詢)
       - `GET /api/v1/hr/leave-ledger/entries` (不可變帳本流水清單)
       - `GET /api/v1/hr/leave-ledger/summary` (全假別可用天數與分鐘數彙總)
  5. **自動化測試套件**：
     - 建立 [apps/api/tests/test_hr_full_system.py](file:///c:/Sources/EtronJF8/apps/api/tests/test_hr_full_system.py)，完整覆蓋報到、DAG 組織/主管防環、調職、離職連動 Session 撤銷、班別日曆與假額天數換算。
- **測試命令與實際輸出摘要 (Executed Tests & Output Summary)**：
  - 新增測試：`python -m pytest apps/api/tests/test_hr_full_system.py -v` -> **6 passed in 2.20s (100% 通過)**
  - 全套回歸：`python -m pytest apps/api/tests -v` -> **65 passed in 13.40s (100% 通過，無任何失敗或回歸問題)**

#### 人事系統第二階段：前端 UI 套件、四語對齊與整合驗收 (Phase 2 Frontend Suite & Quad-Language Integration)

- **執行時間**：2026-10-23
- **完成項目**：
  1. **四語系在地化字典深度對齊 (Quad-Language i18n Alignment)**：
     - 在 [apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts) 之 `zh-TW`, `ja-JP`, `en-US`, `zh-CN` 同步補齊 `nav.hr` 與 `hr.*` 完整字典（涵蓋 tabs、employee 名冊、onboardModal、transferModal 與 ledger 帳本），通過 100% 遞迴深度檢查。
  2. **天藍風格人事前端元件庫 (HR Component Suite)**：
     - [apps/web/src/components/common/AppShell.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/AppShell.vue)：側邊欄增加 `👥 人事系統 (nav.hr)` 入口與動態啟用狀態高亮。
     - [apps/web/src/components/hr/OnboardModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OnboardModal.vue)：新進員工報到對話框，支援部門分派、純日期選擇、連動開通系統登入帳號及初始密碼設定。
     - [apps/web/src/components/hr/TransferModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/TransferModal.vue)：部門調動與離職手續作業彈窗，離職模式展示資安停用與 Session 撤銷警示。
     - [apps/web/src/components/hr/EmployeeHistoryModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/EmployeeHistoryModal.vue)：員工生命週期異動歷程時間軸視圖。
     - [apps/web/src/components/hr/OrgTree.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OrgTree.vue)：部門組織架構檢視與 DAG 防環新增。
     - [apps/web/src/components/hr/ShiftList.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/ShiftList.vue)：公司班別清單管理，支援 480 分鐘標準工時與跨夜班標記。
     - [apps/web/src/components/hr/LeaveLedgerView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/LeaveLedgerView.vue)：員工假額可用天數即時儀表卡片（換算天數與可用分鐘數）、假額發放 Modal、不可變流水帳本 DataTable（GRANT/HOLD/COMMIT/RELEASE）。
     - [apps/web/src/components/hr/HrManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/HrManagementView.vue)：人事系統主入口，具備 4 大 Tab 切換。
  3. **主應用整合 (App Integration)**：
     - [apps/web/src/App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue)：依據 `currentModule` 動態切換營運儀表板與人事系統主視圖。
- **測試命令與實際輸出摘要 (Executed Tests & Output Summary)**：
  - 前端單元與多語系測試：`npm run test` (Vitest) -> **4 test files passed, 10 passed in 2.42s (100% 通過)**
  - 前端型別檢查與生產打包：`npm run build` (`vue-tsc -b && vite build`) -> **0 錯誤，生產環境靜態資產打包成功 (built in 1.40s)**

### 員工主檔基本資訊規格設計 (Employee Master Data Schema Design)

- **設計時間**：2026-10-23
- **設計依據**：參考台灣勞基法/所得稅法規範、日本勞動基準法「労働者名簿」法令要件、及國際企業 HRIS (如 Workday、SAP SuccessFactors) 標準主檔結構。
- **欄位體系劃分 (Field Classification)**：
  1. **員工身分與個人識別 (Personal Identity)**：中文/法定全名、英文護照姓名 (`english_name`)、身分證字號/居留證號/マイナンバー (`national_id`，敏感個資遮罩防護)、出生年月日 (`birth_date`, Date-only)、性別 (`gender`)、國籍 (`nationality`)、婚姻狀況 (`marital_status`)。
  2. **通訊與緊急聯絡人 (Contact & Emergency)**：公務信箱 (`email`)、私人信箱 (`personal_email`)、行動電話 (`mobile_phone`)、現居通訊地址 (`residential_address`)、法定戶籍地址 (`permanent_address`)、緊急聯絡人姓名 (`emergency_contact_name`)、緊急聯絡人關係 (`emergency_contact_relationship`)、緊急聯絡人電話 (`emergency_contact_phone`)。
  3. **職務與聘僱關係 (Employment & Job Details)**：員工編號、所屬公司、所屬部門、職稱 (`job_title`)、職等職級 (`job_grade`)、聘僱型態 (`employment_type`: 正職/約聘/實習/兼職)、預設班別 (`default_shift_id`)、到職日 (`hire_date`)、試用期滿日 (`probation_end_date`)、在職狀態、離職生效日。
  4. **主管關係與核決鏈 (Manager Hierarchy)**：直屬主管 (Direct Manager)、主管鏈層級、DAG 防環路驗證。
- **個資保護與合規設計**：
  - 身分證號/個人番號預設套用 `mask_national_id` 遮罩（如 `A12****789`），保護員工個人資料私密性。
  - 所有日期一律遵循專案規約採 `Date-only` 儲存，杜絕 UTC 偏移引發的跨日誤差。

#### 員工主檔完整欄位擴充與實施落地 (Employee Master Data Expansion Implementation)

- **執行時間**：2026-10-23
- **完成項目**：
  1. **ORM 模型擴充 (ORM Model Expansion)**：
     - [apps/api/app/models/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/models/hr.py)：在 `Employee` 模型新增 `english_name`, `national_id`, `birth_date`, `gender`, `nationality`, `marital_status`, `personal_email`, `mobile_phone`, `residential_address`, `permanent_address`, `emergency_contact_name`, `emergency_contact_relationship`, `emergency_contact_phone`, `job_title`, `job_grade`, `employment_type`, `default_shift_id`, `probation_end_date`。
  2. **Alembic 資料庫無失真遷移 (Database Migration)**：
     - 生成遷移腳本 [apps/api/alembic/versions/4a2e1d7f8c9b_expand_employee_master_fields.py](file:///c:/Sources/EtronJF8/apps/api/alembic/versions/4a2e1d7f8c9b_expand_employee_master_fields.py)，採用 SQLite batch alter table 機制無損加入 18 個擴充欄位，成功升級至 head。
  3. **商業邏輯與個資動態遮罩 (Rules & Masking Service)**：
     - [apps/api/app/core/hr_rules.py](file:///c:/Sources/EtronJF8/apps/api/app/core/hr_rules.py)：
       - `mask_national_id`：身分識別字號字串動態遮罩服務。
       - `onboard_employee`：支援建構完整擴充欄位並寫入 `ONBOARD` 異動記錄。
       - `update_employee_profile`：提供白名單式員工基本資料更新，維護樂觀鎖版本號 (`version += 1`)。
  4. **後端 API 契約升級 (API Contracts & Endpoints)**：
     - [apps/api/app/api/v1/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/hr.py)：
       - `EmployeeCreate` / `EmployeeUpdate` Pydantic DTO 定義完備。
       - `POST /api/v1/hr/employees`：新進報到完整欄位寫入。
       - `GET /api/v1/hr/employees/{id}`：詳情查詢提供動態個資遮罩防護與主管資訊。
       - `PUT /api/v1/hr/employees/{id}`：更新員工職稱、聯絡通訊與緊急聯絡人資訊。
  5. **四語系國際化字典同步擴充 (Quad-Language i18n Synchronization)**：
     - [apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts)：繁體中文 (`zh-TW`)、日文 (`ja-JP`)、英文 (`en-US`)、簡體中文 (`zh-CN`) 完整加入 `englishName`, `nationalId`, `gender`, `birthDate`, `nationality`, `maritalStatus`, `personalEmail`, `mobilePhone`, `residentialAddress`, `permanentAddress`, `emergencyContact`, `jobTitle`, `jobGrade`, `employmentType`, `probationEndDate`, `detailBtn`, `editBtn` 等所有鍵值。
  6. **前端 UI 元件擴充與詳情彈窗 (Frontend UI & Detail Modal)**：
     - [apps/web/src/components/hr/OnboardModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OnboardModal.vue)：三段式導航（基本身分識別、通訊與緊急聯絡人、職務組織與帳號），完整支援所有擴充欄位輸入。
     - [apps/web/src/components/hr/EmployeeDetailModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/EmployeeDetailModal.vue)：全新建構，展示員工完整資料、遮罩身分證、主管卡片，並支援現場快速編輯職稱、手機與緊急聯絡人。
     - [apps/web/src/components/hr/HrManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/HrManagementView.vue)：名冊表格納入職稱與職等，整合「詳細資訊」彈窗按鈕。
- **測試命令與實際輸出摘要 (Executed Tests & Output Summary)**：
  - **後端擴充與全套測試 (pytest)**：
    - 單項驗證：`pytest tests/test_hr_full_system.py -v` -> **7 passed in 2.41s (100% 通過，含新增 test_employee_expanded_fields_and_masking)**
    - 全系統回歸：`pytest tests/` -> **66 passed in 13.51s (100% 通過，所有縱切面模組無一回歸)**
  - **前端型別檢查與打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 錯誤，打包完成 (built in 2.00s)**
  - **前端單元與四語完整性測試 (vitest)**：
    - `npm run test` -> **4 test files passed, 10 passed in 2.48s (含 i18n 深度檢查)**

### 前端企業認證與密碼管理實施落地 (Frontend Enterprise Authentication & Password Management)

- **執行時間**：2026-10-23
- **架構原則**：對齊後端既有之安全 Session Cookie (HttpOnly) 與 CSRF 防護機制，實作前端響應式認證狀態管理、全域登入、安全登出、一般密碼變更與首次登入強制改密 (First-time Password Initialization)。
- **完成項目**：
  1. **全域認證狀態服務 (Auth State Management)**：
     - [apps/web/src/utils/auth.ts](file:///c:/Sources/EtronJF8/apps/web/src/utils/auth.ts)：提供 `currentUser`, `csrfToken`, `checkAuth`, `login`, `logout`, `changePassword`, `setFirstTimePassword`，自動維護雙向 Session 狀態與 `X-CSRF-Token` 標頭注入。
  2. **四語系認證字典對齊 (Quad-Language i18n Alignment)**：
     - [apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts)：`zh-TW`, `ja-JP`, `en-US`, `zh-CN` 全面補齊 `auth.login`, `auth.logout`, `auth.changePassword`, `auth.oldPassword`, `auth.newPassword`, `auth.confirmPassword`, `auth.firstTimeTitle`, `auth.firstTimeHint` 等所有語系字串。
  3. **現代化認證 UI 元件庫 (Auth Component Suite)**：
     - [apps/web/src/components/auth/LoginModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/auth/LoginModal.vue)：毛玻璃現代企業登入對話框，支援帳號、密碼、公司切換、快速填入展示帳號與錯誤回饋。
     - [apps/web/src/components/auth/ChangePasswordModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/auth/ChangePasswordModal.vue)：驗證舊密碼與新密碼（至少 8 碼），提供一致性防呆與非同步提交回饋。
     - [apps/web/src/components/auth/FirstTimePasswordModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/auth/FirstTimePasswordModal.vue)：針對新進同仁首次登入標記 (`is_first_login = True`) 之不可跳過強制改密對話框。
     - [apps/web/src/components/common/AppShell.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/AppShell.vue)：頂部導航列整合登入者姓名頭像卡、角色標籤、修改密碼選單與安全登出觸發鈕；未登入狀態提供醒目「🔑 登入」按鈕。
     - [apps/web/src/App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue)：掛載全域認證對話框，於 `onMounted` 自動呼叫 `checkAuth()` 同步伺服器 Session。
  4. **開發資料庫種子腳本 (Development Database Seed Script)**：
     - [apps/api/scripts/seed_dev.py](file:///c:/Sources/EtronJF8/apps/api/scripts/seed_dev.py)：初始化 `hr_manager` (人事主管)、`test_admin` (管理員)、`new_employee` (首次登入同仁) 帳號與角色範圍。
- **測試命令與實際輸出摘要 (Executed Tests & Output Summary)**：
  - **前端認證單元與多語測試 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.83s (含新增之 auth.test.ts 6 項認證全流程測試，100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 錯誤，打包完成 (built in 1.79s)**
  - **後端端點實機連線驗證 (API Live Integration)**：
    - `POST /api/v1/auth/login`：成功登入並取得 HttpOnly Cookie 與 CSRF Token。
    - `GET /api/v1/auth/me`：回傳使用者主檔、活動公司角色與權限清單。
    - `POST /api/v1/auth/logout`：成功登出並在伺服器端標記 Session 為撤銷狀態。

#### CSRF 跨站防護權杖全域自動注入與異常修復 (CSRF Auto-Injection & Interceptor Resolution)

- **問題診斷 (Root Cause)**：
  - 於「員工部門調動」等操作執行 POST/PUT/DELETE 請求時，後端鑑權中介軟體 (`deps.py`) 強制檢驗 `X-CSRF-Token` 標頭；前端元件原生 `fetch` 缺少該標頭導致伺服器拋出 `403 CSRF_VERIFICATION_FAILED (CSRF 權杖驗證失敗，請求被拒絕)`。
- **架構修復方案 (Solution)**：
  1. **全域與元件層級自動注入 (`apiFetch` & Global Interceptor)**：
     - 在 [apps/web/src/utils/auth.ts](file:///c:/Sources/EtronJF8/apps/web/src/utils/auth.ts) 實作 `apiFetch` 與 `window.fetch` 全域攔截器。
     - 針對所有非安全變更方法 (`POST`, `PUT`, `PATCH`, `DELETE`)，自動從當前 Session 注入 `X-CSRF-Token` 標頭。
     - 若瀏覽器端尚未快取權杖，自動非同步向 `/api/v1/auth/me` 補齊或引導登入。
  2. **全面元件升級**：
     - [apps/web/src/components/hr/TransferModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/TransferModal.vue)：部門調職與離職作業改用 `apiFetch`。
     - [apps/web/src/components/hr/OnboardModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OnboardModal.vue)：新進報到作業改用 `apiFetch`。
     - [apps/web/src/components/hr/EmployeeDetailModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/EmployeeDetailModal.vue)：員工主檔資料儲存改用 `apiFetch`。
     - [apps/web/src/components/hr/ShiftList.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/ShiftList.vue)：班別新增改用 `apiFetch`。
     - [apps/web/src/components/hr/OrgTree.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OrgTree.vue)：組織部門新增改用 `apiFetch`。
     - [apps/web/src/components/hr/LeaveLedgerView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/LeaveLedgerView.vue)：假額發放作業改用 `apiFetch`。
- **測試命令與實際輸出 (Verified Execution)**：
  - 前端單元測試：`npm run test` -> **5 passed (5), 16 passed (16) in 2.65s (100% 通過)**
  - 前端型別檢查與打包：`npm run build` -> **0 errors (built in 1.62s)**
  - 後端縱切面回歸測試：`pytest tests/` -> **66 passed in 16.41s (100% 通過)**

#### 公司基本資料維護實施落地 (Company Master Profile Implementation)

- **執行時間**：2026-10-23
- **架構原則**：公司基本資料為整個跨國集團多公司體系 (Multi-Company Architecture) 之根本根節點；擴充稅籍統編/法人番号、法人代表、總機電話與登記法定地址，提供完整 CRUD 與四語系在地化維護介面。
- **完成項目**：
  1. **資料模型與無損遷移 (Models & Alembic Migration)**：
     - [apps/api/app/models/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/models/hr.py)：`Company` 模型擴充 `tax_id` (統編/法人番號)、`representative_name` (負責人/代表取締役)、`registered_address` (登記地址) 與 `contact_phone` (總機電話)。
     - 生成並套用遷移腳本 [apps/api/alembic/versions/24f46cc63859_expand_company_master_fields.py](file:///c:/Sources/EtronJF8/apps/api/alembic/versions/24f46cc63859_expand_company_master_fields.py)，升級至 head。
  2. **API 契約與端點加固 (API Endpoints & Pydantic V2 DTO)**：
     - [apps/api/app/api/v1/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/hr.py)：
       - `CompanyCreate` / `CompanyUpdate` / `CompanyResponse` DTO。
       - `GET /api/v1/hr/companies` (列出所有營運法人)。
       - `GET /api/v1/hr/companies/{company_id}` (查詢特定公司詳情)。
       - `POST /api/v1/hr/companies` (新增註冊子公司或辦事處)。
       - `PUT /api/v1/hr/companies/{company_id}` (更新公司法定名稱、統編、代表人、地址、電話與營運狀態)。
  3. **四語系國際化字典對齊 (Quad-Language i18n Alignment)**：
     - [apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts)：`zh-TW`, `ja-JP`, `en-US`, `zh-CN` 同步補齊 `hr.tabs.companies` 與 `hr.company.*` 完整字典（代碼、名稱、統編/法人番号、代表人、電話、登記地址、時區、幣別、營運狀態等）。
  4. **前端 UI 元件與管理視圖 (Frontend UI Suite)**：
     - [apps/web/src/components/hr/CompanyManagement.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/CompanyManagement.vue)：全新建構公司基本資料卡片視圖與編輯/新增對話框，具備現代毛玻璃與漸層代碼標籤，全面使用 `apiFetch` 保障 CSRF 安全。
     - [apps/web/src/components/hr/HrManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/HrManagementView.vue)：頂端 Tab 導覽列正式加入「🏢 公司基本資料」主入口。
- **測試命令與實際輸出 (Verified Execution)**：
  - **後端整合與全套測試 (pytest)**：
    - 單項驗證：`pytest tests/test_hr_full_system.py` -> **8 passed in 2.81s (100% 通過，含新增 test_company_crud_and_expansion)**
    - 全系統回歸：`pytest tests/` -> **67 passed in 14.58s (100% 通過，0 回歸故障)**
  - **前端型別檢查與打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors，打包完成 (built in 1.91s)**
  - **前端單元與四語完整性測試 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.41s (100% 通過)**

#### AppShell 導航外殼 Tailwind v4 樣式重構 (AppShell Tailwind CSS v4 Modernization)

- **執行時間**：2026-10-23
- **架構原則**：遵循 Tailwind CSS v4 現代化語法與 `@theme` 設計權杖 (Design Tokens) 規範，消除任意值 `[var(...)]` 舊式寫法與廢棄類別警告，提升樣式效能與語法簡潔度。
- **完成項目**：
  1. **類別現代化精簡 (Modernized Classnames)**：
     - [apps/web/src/components/common/AppShell.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/AppShell.vue)：
       - `bg-[var(--color-surface-bg)]` -> `bg-(--color-surface-bg)`
       - `border-[var(--color-border-main)]` -> `border-border-main`
       - `bg-[var(--color-primary)]` -> `bg-(--color-primary)`
       - `text-[var(--color-text-main)]` -> `text-text-main`
       - `text-[var(--color-text-muted)]` -> `text-text-muted`
       - `text-[var(--color-primary)]` -> `text-(--color-primary)`
       - `hover:bg-[var(--color-primary-hover)]` -> `hover:bg-primary-hover`
       - `flex-shrink-0` -> `shrink-0`
     - 成功消除 IDE 回報之 23 項 Tailwind CSS 語法警告 (0 Warnings, 0 Errors)。
- **測試命令與實際輸出 (Verified Execution)**：
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 58 modules transformed, built in 1.65s (100% 通過)**
  - **前端單元與四語完整性測試 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.52s (100% 通過)**

#### OnboardModal 報到彈窗 Tailwind v4 樣式重構 (OnboardModal Tailwind CSS v4 Modernization)

- **執行時間**：2026-10-23
- **架構原則**：針對新進報到彈窗表單所有輸入框之聚焦光暈 (Focus Ring)、分頁頁籤 (Tab Bar)、核取方塊 (Checkbox) 與動作按鈕，全面遵循 Tailwind CSS v4 語法標準。
- **完成項目**：
  1. **類別現代化精簡 (Modernized Classnames)**：
     - [apps/web/src/components/hr/OnboardModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OnboardModal.vue)：
       - `focus:ring-[var(--color-primary)]` -> `focus:ring-(--color-primary)` (20 處表單輸入元件)
       - `text-[var(--color-primary)] border-[var(--color-primary)]` -> `text-(--color-primary) border-(--color-primary)` (分頁頁籤)
       - `text-[var(--color-primary)]` -> `text-(--color-primary)` (建立帳號 Checkbox)
       - `text-[var(--color-text-muted)]` -> `text-text-muted` (密碼設定輔助提示)
       - `bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)]` -> `bg-(--color-primary) hover:bg-primary-hover` (送出按鈕)
     - 成功消除 IDE 回報之 30 項語法警告 (0 Warnings, 0 Errors)。
- **測試命令與實際輸出 (Verified Execution)**：
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 58 modules transformed, built in 1.86s (100% 通過)**
  - **前端單元與四語完整性測試 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.57s (100% 通過)**

#### 全域人事管理元件 Tailwind v4 樣式重構與文件規範化 (HR Components Tailwind CSS v4 Modernization & Markdownlint)

- **執行時間**：2026-10-23
- **架構原則**：依據 Tailwind CSS v4 語法規範及專案設計權杖（Design Tokens），全面清除 [LeaveLedgerView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/LeaveLedgerView.vue)、[HrManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/HrManagementView.vue)、[OrgTree.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OrgTree.vue)、[ShiftList.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/ShiftList.vue) 中所有的 `[var(...)]` 舊式任意值語法警告，並在專案根目錄建立 [.markdownlint.json](file:///c:/Sources/EtronJF8/.markdownlint.json) 規範文件格式。
- **完成項目**：
  1. **假額帳本視圖 ([LeaveLedgerView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/LeaveLedgerView.vue))**：
     - 重構 `border-[var(--color-border-main)]` 為 `border-border-main`。
     - 重構 `focus:ring-[var(--color-primary)]` 為 `focus:ring-(--color-primary)`。
     - 重構 `bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)]` 為 `bg-(--color-primary) hover:bg-primary-hover`。
     - 重構 `hover:border-[var(--color-primary)]` 為 `hover:border-(--color-primary)`。
     - 消除 15 處 IDE 樣式警告。
  2. **人事管理主視圖 ([HrManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/HrManagementView.vue))**：
     - 重構 5 個主功能 Tab 標籤之 `border-[var(--color-primary)] text-[var(--color-primary)]` 為 `border-(--color-primary) text-(--color-primary)`。
     - 重構標題說明文字 `text-text-muted`、按鈕 `bg-(--color-primary)` 與表格外框 `border-border-main`。
     - 消除 14 處 IDE 樣式警告。
  3. **組織階層視圖 ([OrgTree.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OrgTree.vue))**：
     - 重構彈窗 5 處表單輸入框之 `focus:ring-(--color-primary)`。
     - 重構組織卡片外框 `border-border-main hover:border-(--color-primary)` 與操作按鈕。
     - 消除 13 處 IDE 樣式警告。
  4. **班別工時視圖 ([ShiftList.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/ShiftList.vue))**：
     - 重構 7 處表單輸入框之 `focus:ring-(--color-primary)`。
     - 重構跨夜夜班 Checkbox 勾選顏色 `text-(--color-primary)`。
     - 重構卡片邊框與按鈕樣式，消除 16 處 IDE 樣式警告。
  5. **文件規範化與 Markdownlint 修復 ([README.md](file:///c:/Sources/EtronJF8/README.md))**：
     - 建立 [.markdownlint.json](file:///c:/Sources/EtronJF8/.markdownlint.json) 允許章節內重複標題 (`siblings_only: true`)。
     - 全面自動修復 MD022 (標題上下空行)、MD032 (清單空行)、MD031 (代碼區塊空行)、MD058 (表格空行) 與 MD060 (表格欄位樣式)。
- **測試命令與實際輸出 (Verified Execution)**：
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 58 modules transformed, built in 2.05s (100% 通過)**
  - **前端單元與四語完整性測試 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.60s (100% 通過)**
  - **Markdown 文件規範檢查 (markdownlint-cli)**：
    - `npx markdownlint-cli README.md` -> **0 errors, 0 warnings (100% 通過)**

#### 通用與人事核心元件樣式警告修復 (Common & HR Core Components Tailwind CSS v4 Modernization)

- **執行時間**：2026-10-23
- **架構原則**：遵循 Tailwind CSS v4 與專案設計權杖規範，針對剩餘之公司維護、員工詳情、調動離職、通用表單欄位、金額輸入框與頁面標頭元件消除所有 IDE 樣式警告與衝突類別。
- **完成項目**：
  1. **公司基本資料管理 ([CompanyManagement.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/CompanyManagement.vue))**：
     - 重構 8 處輸入框之 `focus:ring-[var(--color-primary)]` 為 `focus:ring-(--color-primary)`。
     - 重構按鈕 `bg-(--color-primary) hover:bg-primary-hover`、說明文字 `text-text-muted` 與核取方塊 `text-(--color-primary)`。
     - 將漸層類別 `bg-gradient-to-br` 現代化為 `bg-linear-to-br`。
     - 消除 15 處 IDE 警告。
  2. **員工詳情彈窗 ([EmployeeDetailModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/EmployeeDetailModal.vue))**：
     - 移除緊急聯絡人卡片中與 `border border-rose-100` 衝突之 `border-t border-slate-100`。
     - 重構儲存按鈕為 `bg-(--color-primary) hover:bg-primary-hover`。
     - 消除 4 處 IDE 警告。
  3. **調職與離職彈窗 ([TransferModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/TransferModal.vue))**：
     - 重構新部門下拉選單與事由多行輸入框之 `focus:ring-(--color-primary)`。
     - 重構確認按鈕非離職狀態下之 `bg-(--color-primary) hover:bg-primary-hover`。
     - 消除 4 處 IDE 警告。
  4. **通用表單欄位 ([FormField.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/FormField.vue))**：
     - 重構欄位提示文字為 `text-text-muted`，消除 1 處警告。
  5. **通用金額輸入框 ([MoneyInput.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/MoneyInput.vue))**：
     - 重構邊框聚焦偽類 `focus-within:border-(--color-primary)`，消除 1 處警告。
  6. **通用頁面標頭 ([PageHeader.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/PageHeader.vue))**：
     - 重構分隔底線 `border-border-main`、標題文字 `text-text-main`、麵包屑與副標題 `text-text-muted`、連結懸浮 `hover:text-(--color-primary)`。
     - 消除 5 處 IDE 警告。
- **測試命令與實際輸出 (Verified Execution)**：
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 58 modules transformed, built in 1.98s (100% 通過)**
  - **前端單元與四語完整性測試 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.85s (100% 通過)**
  - **Markdown 文件規範檢查 (markdownlint-cli)**：
    - `npx markdownlint-cli README.md` -> **0 errors, 0 warnings (100% 通過)**

#### 應用程式主畫面 Tailwind v4 樣式重構 (App.vue Tailwind CSS v4 Modernization)

- **執行時間**：2026-10-23
- **架構原則**：針對 Vue 應用程式根元件 [App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue)，全面消除按鈕背景、懸浮狀態、邊框與說明文字的舊式 `[var(...)]` 語法警告。
- **完成項目**：
  1. **類別現代化精簡 (Modernized Classnames)**：
     - [apps/web/src/App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue)：
       - `bg-[var(--color-primary)] hover:bg-[var(--color-primary-hover)]` -> `bg-(--color-primary) hover:bg-primary-hover` (登入提示與按鈕)
       - `border-[var(--color-border-main)]` -> `border-border-main` (健康狀態橫幅與 3 個快速卡片外框)
       - `text-[var(--color-text-muted)]` -> `text-text-muted` (時間戳記與數值副標題)
     - 消除 IDE 回報之 11 項語法警告 (0 Warnings, 0 Errors)。
- **測試命令與實際輸出 (Verified Execution)**：
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 58 modules transformed, built in 1.89s (100% 通過)**
  - **前端單元與四語完整性測試 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.74s (100% 通過)**
  - **Markdown 文件規範檢查 (markdownlint-cli)**：
    - `npx markdownlint-cli README.md` -> **0 errors, 0 warnings (100% 通過)**

#### 表格與過濾列元件 Tailwind v4 樣式重構 (DataTable & FilterBar Tailwind CSS v4 Modernization)

- **執行時間**：2026-10-23
- **架構原則**：遵循 Tailwind CSS v4 設計規範，重構共用數據表格 [DataTable.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/DataTable.vue) 與過濾搜尋列 [FilterBar.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/FilterBar.vue)，消除舊式分割線、邊框、寬度與焦點樣式警告。
- **完成項目**：
  1. **共用數據表格 ([DataTable.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/DataTable.vue))**：
     - 重構外框與分頁底部分隔線為 `border-border-main`。
     - 重構表頭與行間分隔線為 `divide-border-main`。
     - 重構表頭文字色彩為 `text-text-muted`。
     - 消除 5 處 IDE 警告。
  2. **共用過濾搜尋列 ([FilterBar.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/FilterBar.vue))**：
     - 重構容器邊框為 `border-border-main`。
     - 將搜尋框寬度 `min-w-[200px]` 規範化為 Tailwind v4 標準階度 `min-w-50`。
     - 重構搜尋框聚焦邊框為 `focus:border-(--color-primary)`。
     - 重構查詢按鈕為 `bg-(--color-primary) hover:bg-primary-hover`。
     - 消除 5 處 IDE 警告。
- **測試命令與實際輸出 (Verified Execution)**：
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 58 modules transformed, built in 1.78s (100% 通過)**
  - **前端單元與四語完整性測試 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.79s (100% 通過)**
  - **Markdown 文件規範檢查 (markdownlint-cli)**：
    - `npx markdownlint-cli README.md` -> **0 errors, 0 warnings (100% 通過)**

#### 認證彈窗與通用輸入元件樣式重構 (Auth Modals & Common Inputs Tailwind CSS v4 Modernization)

- **執行時間**：2026-10-23
- **架構原則**：遵循 Tailwind CSS v4 語法規範，針對修改密碼彈窗 [ChangePasswordModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/auth/ChangePasswordModal.vue)、首登改密彈窗 [FirstTimePasswordModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/auth/FirstTimePasswordModal.vue)、登入彈窗 [LoginModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/auth/LoginModal.vue)、日期時間輸入框 [DateTimeInput.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/DateTimeInput.vue) 與空狀態展示 [EmptyState.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/EmptyState.vue) 消除全部舊式語法警告。
- **完成項目**：
  1. **修改密碼彈窗 ([ChangePasswordModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/auth/ChangePasswordModal.vue))**：
     - 重構 3 處輸入框之 `focus:ring-(--color-primary)`。
     - 重構確認按鈕為 `bg-(--color-primary) hover:bg-primary-hover`。
     - 消除 5 處 IDE 警告。
  2. **首次強制改密彈窗 ([FirstTimePasswordModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/auth/FirstTimePasswordModal.vue))**：
     - 重構新密碼與確認密碼輸入框之 `focus:ring-(--color-primary)`。
     - 消除 2 處 IDE 警告。
  3. **登入彈窗 ([LoginModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/auth/LoginModal.vue))**：
     - 重構登入按鈕懸浮樣式為 `hover:bg-primary-hover`。
     - 消除 1 處 IDE 警告。
  4. **日期時間輸入元件 ([DateTimeInput.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/DateTimeInput.vue))**：
     - 重構聚焦邊框為 `focus:border-(--color-primary)`。
     - 重構時區標籤文字色彩為 `text-text-muted`。
     - 消除 2 處 IDE 警告。
  5. **空狀態展示元件 ([EmptyState.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/EmptyState.vue))**：
     - 重構說明文字色彩為 `text-text-muted`。
     - 消除 1 處 IDE 警告。
- **測試命令與實際輸出 (Verified Execution)**：
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 58 modules transformed, built in 1.78s (100% 通過)**
  - **前端單元與四語完整性測試 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.87s (100% 通過)**
  - **Markdown 文件規範檢查 (markdownlint-cli)**：
    - `npx markdownlint-cli README.md` -> **0 errors, 0 warnings (100% 通過)**

#### 時區與語言切換下拉選單重構 (Timezone & Language Dropdown Selectors Modernization)

- **執行時間**：2026-10-23
- **架構原則**：針對頂部導航列 [AppShell.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/AppShell.vue)，將原先佔用大量橫向寬度的雙時區按鈕群與四語系按鈕群，全面重構為風格統一、膠囊外觀之下拉選單（Dropdown Selectors），並於 [i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts) 補齊四語系 `header.language` 鍵值。
- **完成項目**：
  1. **國際化字典補齊 ([i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts))**：
     - 同步於 `zh-TW`（語言）、`ja-JP`（表示言語）、`en-US`（Language）與 `zh-CN`（语言）之 `header` 命名空間新增 `language` 翻譯鍵值。
  2. **導航外殼下拉選單重構 ([AppShell.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/AppShell.vue))**：
     - 新增 `handleTimezoneChange` 與 `handleLanguageSelectChange` 變換監聽事件。
     - 時區下拉選單：整合台北 (UTC+8) 與東京 (UTC+9)，並連動既有 `localStorage` 與父層 `change-timezone` 事件。
     - 語言下拉選單：整合繁體中文、日本語、English 與簡體中文，即時觸發 `i18next.changeLanguage`。
     - 視覺風格統一採用 `bg-slate-50 border border-slate-200 rounded-md px-2.5 py-1 text-xs`，與公司切換器保持一致。
- **測試命令與實際輸出 (Verified Execution)**：
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 58 modules transformed, built in 2.66s (100% 通過)**
  - **前端單元與四語完整性測試 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 3.74s (100% 通過)**
  - **Markdown 文件規範檢查 (markdownlint-cli)**：
    - `npx markdownlint-cli README.md` -> **0 errors, 0 warnings (100% 通過)**

#### 部門組織編輯與有效/失效日期擴充 (Department Editing & Validity Dates Management)

- **執行時間**：2026-10-23
- **架構原則**：滿足企業人資組織異動需求，支援部門單位（Organization Unit）之資料編輯、代號與名稱變更、組織層級調整、父子層級關聯調整，並引進業務日期之「有效起始日 (`effective_date`)」與「失效截止日 (`expiry_date`)」維度，配合資料庫無損遷移與嚴格前後端防呆檢核。
- **完成項目**：
  1. **資料模型與無損遷移 (Models & Alembic Migration)**：
     - [apps/api/app/models/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/models/hr.py)：`Organization` 模型擴充 `effective_date` (Date, nullable)、`expiry_date` (Date, nullable) 與 `updated_at` (DateTime, UTC)。
     - 遷移腳本 [7a3c8e1b9d4f_add_org_effective_and_expiry_dates.py](file:///c:/Sources/EtronJF8/apps/api/alembic/versions/7a3c8e1b9d4f_add_org_effective_and_expiry_dates.py)：處理 SQLite 外鍵約束，使用 batch alter table 完成無損結構升級，並執行 `alembic upgrade head` 套用至 SQLite 資料庫。
  2. **後端 API 與領域防呆檢核 (API Endpoints & DAG Validation)**：
     - [apps/api/app/api/v1/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/hr.py)：
       - 新增 Pydantic 模型 `OrgUpdate` 與標準化回傳 `OrgResponse`。
       - 實作 `PUT /api/v1/hr/organizations/{organization_id}` 端點，受 `require_permissions("hr.employee.manage")` 伺服器端授權防護。
       - 自上級防呆：嚴格阻擋將部門自身設為自身上級 (`INVALID_PARENT_ORG`)。
       - DAG 無循環檢核：當調整 `parent_id` 時，嚴格調用 `check_organization_cycle` 阻擋循環相依 (`ORGANIZATION_CYCLE_DETECTED`)。
       - 日期區間檢核：校驗 `effective_date <= expiry_date`，反向區間回傳 `INVALID_DATE_RANGE`；失效日期留空代表永久有效。
       - 代碼唯一性：變更部門代碼時檢驗本公司內代碼唯一性 (`ORG_CODE_EXISTS`)。
       - 部門啟用與停用：支援 `is_active` 軟停用狀態更新。
  3. **國際化多語系字典對齊 ([i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts))**：
     - 同步於 `zh-TW`、`ja-JP`、`en-US` 與 `zh-CN` 四大語系新增完整 `hr.org` 命名空間，涵蓋標題、副標題、按鈕、各欄位標籤、組織層級名稱、有效期間與永久有效標籤。
  4. **前端組織階層元件升級 ([OrgTree.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OrgTree.vue))**：
     - 組織卡片：展示「啟用/停用」徽章、組織層級、部門代號、上級部門，並新增「有效期間標籤 (`effective_date ~ expiry_date`)」與右上角「✏️ 編輯部門」動作按鈕。
     - 編輯彈窗：整合共用日期元件 `DateTimeInput` 供維護有效起始日與失效截止日，支援修改部門代碼、名稱、層級、上級組織（自動過濾自身防循環），並支援啟用狀態切換開關。
     - 安全請求：全面採用 `apiFetch` 進行 CSRF 與 Bearer Token 授權提交。
  5. **自動化測試擴充與完整回歸 (Automated Testing)**：
     - [apps/api/tests/test_hr_full_system.py](file:///c:/Sources/EtronJF8/apps/api/tests/test_hr_full_system.py)：新增 `test_organization_update_and_effective_dates` 整合測試，涵蓋建立、編輯、日期倒置阻擋、自己為父阻擋、代號重複阻擋與停用切換。
- **測試命令與實際輸出 (Verified Execution)**：
  - **後端全套單元測試 (pytest)**：
    - `pytest` -> **68 passed in 20.53s (100% 通過)**
  - **人資全流程系統測試 (pytest)**：
    - `pytest tests/test_hr_full_system.py` -> **9 passed in 4.24s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 58 modules transformed, built in 1.90s (100% 通過)**
  - **前端單元與四語完整性測試 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.69s (100% 通過)**
  - **Markdown 文件規範檢查 (markdownlint-cli)**：
    - `npx markdownlint-cli README.md` -> **0 errors, 0 warnings (100% 通過)**

#### 前端四大業務模組視圖補齊與端到端串接 (Leave, Attendance, Travel & Expense Views Implementation)

- **執行時間**：2026-10-23
- **架構原則**：修復左側選單中「請假管理 (`leave`)」、「出勤管理 (`attendance`)」、「出差與結報 (`travel`)」與「費用報支 (`expense`)」缺乏對應前端視圖組件而降級回退至儀表板假資料之問題。全面建立這四大模組的繁體中文互動視圖，補齊後端查詢端點，並串接正式 RESTful API。
- **完成項目**：
  1. **🌴 請假管理視圖 ([LeaveManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/leave/LeaveManagementView.vue))**：
     - 請假單列表展示：單號、假別代碼、起訖時間、折算天數與分鐘數、事由說明、簽核狀態標籤。
     - 請假單開立彈窗：支援選擇假別、起訖時間、工作代理人與請假事由。
     - 即時工時試算：連動後端 `/api/v1/leave/calculate`，跳過休息時間、例假日與非工作日即時試算請假扣抵天數。
     - 支援送審草稿與單據撤回抽單功能。
     - 後端 API 補齊：於 [apps/api/app/api/v1/leave.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/leave.py) 實作 `GET /api/v1/leave/requests` 清單查詢端點。
  2. **⏱️ 出勤管理視圖 ([AttendanceManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/attendance/AttendanceManagementView.vue))**：
     - 在線打卡卡片：動態顯示台北/東京本地時間時鐘，支援「上班打卡」與「下班打卡」一鍵操作。
     - 出勤事件清單：串接 `/api/v1/attendance/events`，依公司時區展示打卡時間戳、工作日期、打卡來源與異常考勤標記。
     - 批次匯入解析：提供打卡文字/CSV 檔案快速上傳，自動執行預覽與確認入庫。
     - 後端 API 擴充：於 [apps/api/app/api/v1/attendance.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/attendance.py) 新增 `POST /api/v1/attendance/punch` 即時打卡端點。
  3. **✈️ 出差與結報視圖 ([TravelManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/travel/TravelManagementView.vue))**：
     - 頁籤切換：出差申請單 (Travel Requests) 與差旅結報單 (Travel Settlements)。
     - 出差單開立：目的地、出差起訖日、交通方式、出差事由，並支援差旅預支款項申請（TWD/JPY/USD 多幣別）。
     - 差旅結報開立：關聯已核准出差單、輸入費用項目明細、原始幣別、匯率折算與淨應補退款項即時核算。
  4. **📰 費用報支視圖 ([ExpenseManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/expense/ExpenseManagementView.vue))**：
     - 費用報銷單列表：報銷單號、標題、總報支金額 (TWD)、幣別、審核狀態、付款結清狀態。
     - 重複憑證警示：前端即時呈現後端回傳之 `has_duplicate_warning` 警示徽章，輔助會計窗口重點複核。
     - 開立費用報銷單：支援多筆費用明細、發票憑證號碼、未稅金額、營業稅額與成本中心。
  5. **主框架視圖路由掛載 ([App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue))**：
     - 在主範本中加入 `currentModule` 分支切換（`leave`, `attendance`, `travel`, `expense`），並在各視圖標頭對應時區與公司代碼。
- **測試命令與實際輸出 (Verified Execution)**：
  - **後端全套單元測試 (pytest)**：
    - `pytest` -> **68 passed in 16.79s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 66 modules transformed, built in 2.31s (100% 通過)**
  - **前端單元與四語完整性測試 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.68s (100% 通過)**
  - **Markdown 文件規範檢查 (markdownlint-cli)**：
    - `npx markdownlint-cli README.md` -> **0 errors, 0 warnings (100% 通過)**

#### 用印申請、廠商請款與合約管理系統前端建置 (Seal, Vendor Payment & Contract Systems Implementation)

- **執行時間**：2026-10-23
- **架構原則**：全面補齊法務、總務與財會關鍵業務前端視圖，建立「用印申請系統 (`seal`)」、「廠商請款系統 (`payment`)」與「合約管理系統 (`contract`)」，串接已完備之主管鏈、門檻法務與會計核銷審批管線。
- **完成項目**：
  1. **🔏 用印申請系統 ([SealManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/seal/SealManagementView.vue))**：
     - 用印申請單清單：單號、文件名稱、印鑑代碼、申請份數、簽核狀態、實體用印狀態。
     - 印鑑清冊主檔檢視：代碼、名稱、印鑑類型、保管人員與啟用狀態。
     - 開立用印申請：選擇印鑑（串接 `/api/v1/seals`）、填寫文件名稱、版本號、用途事由與用印份數。
     - 保管人實體用印登記：審核完簽後提供保管人記錄實體蓋印份數與完簽掃描件歸檔網址（串接 `/api/v1/seal/requests/{id}/execute`）。
  2. **💵 廠商請款系統 ([PaymentManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/payment/PaymentManagementView.vue))**：
     - 廠商請款單清單：請款單號、主旨標題、受款供應商、請款金額、折合本位幣金額 (TWD)、預計付款日、審核與付款狀態。
     - 供應商名冊清單：供應商代碼、名稱、統一編號/法人番號、往來銀行名稱與自動遮罩銀行帳號。
     - 開立廠商請款單：選擇受款供應商、幣別匯率換算、預計付款日、付款方式（電匯/支票）、發票號碼與說明。
     - 註冊供應商主檔：維護代碼、公司名稱、統編與受款銀行帳戶資訊（串接 `/api/v1/vendors`）。
  3. **📜 合約管理系統 ([ContractManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/contract/ContractManagementView.vue))**：
     - 合約主檔清單：合約編號、合約主旨、簽約相對人、合約類型、合約金額 (TWD)、有效期間、簽核狀態與生命週期狀態。
     - 開立合約審查單：簽約相對人、合約名稱、合約類型（採購/銷售/NDA/勞務委任/租賃）、幣別金額、生效起訖日、自動續約與是否需用印。
     - 支援送審草稿與合約簽署完畢後的歸檔作業（串接 `/api/v1/contracts/{id}/archive`）。
  4. **主框架全模組路由整合 ([App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue))**：
     - 掛載 `seal`、`payment`、`contract` 視圖組件，至此側邊欄業務模組全部 100% 具備對應的前端視圖與後端正式 API 連通。
- **測試命令與實際輸出 (Verified Execution)**：
  - **後端全套單元測試 (pytest)**：
    - `pytest` -> **68 passed in 14.62s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 72 modules transformed, built in 2.12s (100% 通過)**
  - **前端單元與四語完整性測試 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.66s (100% 通過)**
  - **Markdown 文件規範檢查 (markdownlint-cli)**：
    - `npx markdownlint-cli README.md` -> **0 errors, 0 warnings (100% 通過)**

#### 出差申請單開立異常修復與全系統員工指派強化 (Travel Request Creation Fix & Robust Employee Fallback)

- **執行時間**：2026-10-23
- **問題回報與症狀 (Incident & Symptoms)**：
  - 使用者在前端出差管理視圖（`TravelManagementView.vue`）點擊「+ 開立出差申請單」並送出時，彈窗頂部出現紅色警示：「建立出差單失敗」，無法建立出差草稿。
- **根本原因深入分析 (Root Cause Analysis)**：
  1. **員工身分未綁定之預設值問題**：前端在送出開單請求時，將 `employee_id` 設為 `currentUser.value?.employee_id || 'EMP-DEFAULT'`。若當前登入者為管理員（`admin`，本身未連結特定員工資料）或未登入狀態，前端即向後端發送 `'EMP-DEFAULT'`。
  2. **模型欄位屬性錯誤導致內部例外**：後端原本嘗試在找不到指定員工時 fallback 取得該公司第一位有效在職員工，然而在篩選條件中誤用了不存在的 `Employee.employment_status == "ACTIVE"`（正確模型欄位名稱為 `Employee.status`），導致 SQLAlchemy 在評估查詢時引發 `AttributeError` 例外。
  3. **前端例外捕捉未解析後端結構化錯誤**：後端回傳格式為 `{ error: { code: "...", message: "..." } }`，但前端僅讀取 `err.message`，導致在非 2xx 回應時退回顯示預設的「建立出差單失敗」，隱藏了後端具體的錯誤細節。
- **架構設計與修復處置 (Architectural Solutions & Actions)**：
  1. **後端領域服務自動容錯機制 (Domain Services Resilient Fallback)**：
     - [apps/api/app/core/travel_service.py](file:///c:/Sources/EtronJF8/apps/api/app/core/travel_service.py)：修正 `Employee.status == "ACTIVE"` 查詢條件；當傳入之 `employee_id` 為 `'EMP-DEFAULT'`、空字串或資料庫查無此人時，自動安全降級為所屬公司之有效在職員工。
     - [apps/api/app/core/payment_service.py](file:///c:/Sources/EtronJF8/apps/api/app/core/payment_service.py)：同步在費用報銷 (`create_expense_claim`) 與廠商請款 (`create_payment_request`) 補齊相同之員工安全 fallback 與正確欄位。
     - [apps/api/app/core/seal_contract_service.py](file:///c:/Sources/EtronJF8/apps/api/app/core/seal_contract_service.py)：同步在用印申請 (`create_seal_request`) 與合約主檔 (`create_contract`) 補齊在職員工安全 fallback 機制。
     - [apps/api/app/api/v1/attendance.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/attendance.py)：同步修正打卡 API 中的 `Employee.status` 查詢。
  2. **前端開單表單明確選擇員工 (Explicit Employee Selector in Frontend Form)**：
     - [apps/web/src/components/travel/TravelManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/travel/TravelManagementView.vue)：
       - 於載入資料時同步呼叫 `GET /api/v1/hr/employees?company_id={companyId}` 獲取員工清單。
       - 出差開單彈窗新增「申請出差員工 (Applicant)」下拉選單，優先自動綁定當前登入者所屬員工；管理員或代開者亦可明確指定申請人員。
       - 差旅結報開立彈窗同步自動綁定合法員工代碼。
  3. **全面完善前端結構化錯誤解析 (Structured Error Handling)**：
     - 在 `TravelManagementView.vue`、`ExpenseManagementView.vue`、`SealManagementView.vue`、`ContractManagementView.vue`、`PaymentManagementView.vue` 中，統一將錯誤解析升級為：`err.error?.message || err.message || err.detail || '...'`，使後端業務檢核訊息能清晰呈現給使用者。
  4. **自動化測試強化 (Automated Test Coverage)**：
     - [apps/api/tests/test_travel_vertical_slice.py](file:///c:/Sources/EtronJF8/apps/api/tests/test_travel_vertical_slice.py)：新增 `test_travel_request_fallback_employee` 測試案例，正式驗證傳入 `EMP-DEFAULT` 或代開情況下，系統仍可正常建立出差單並處於 `DRAFT` 狀態。
- **測試命令與實際輸出 (Verified Execution)**：
  - **出差單專屬測試 (pytest)**：
    - `pytest apps/api/tests/test_travel_vertical_slice.py` -> **7 passed in 3.13s (100% 通過)**
  - **後端全套單元測試 (pytest)**：
    - `pytest apps/api/tests` -> **69 passed in 15.64s (全模組 69 項測試 100% 通過)**
  - **前端單元與四語完整性測試 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.54s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 72 modules transformed, built in 2.19s (100% 通過)**
  - **Markdown 文件規範檢查 (markdownlint-cli)**：
    - `npx markdownlint-cli README.md` -> **0 errors, 0 warnings (100% 通過)**

#### 側邊欄導航項目補齊 (Sidebar Navigation Items Integration)

- **執行時間**：2026-10-23
- **問題回報與症狀 (Incident & Symptoms)**：
  - 前端已建置完成用印申請 (`SealManagementView`)、供應商請款 (`PaymentManagementView`) 與合約管理 (`ContractManagementView`) 視圖組件，但在系統側邊欄（`AppShell.vue`）中未呈現這三個模組的導航按鈕，導致使用者無法直接由選單切換至對應視圖。
- **根本原因與架構修復 (Root Cause & Solution)**：
  - `AppShell.vue` 導航清單中原先僅配置 `dashboard`、`hr`、`inbox`、`leave`、`attendance`、`travel`、`expense` 7 個項目，缺少 `seal`、`payment`、`contract`。
  - 在 [apps/web/src/components/common/AppShell.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/AppShell.vue) 側邊欄清單中補齊這三個模組按鈕，完整綁定四語 i18n key (`nav.seal`、`nav.payment`、`nav.contract`) 與活動高亮狀態樣式。
- **測試命令與實際輸出 (Verified Execution)**：
  - **前端單元與四語完整性測試 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.64s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 72 modules transformed, built in 2.65s (100% 通過)**
  - **Markdown 文件規範檢查 (markdownlint-cli)**：
    - `npx markdownlint-cli README.md` -> **0 errors, 0 warnings (100% 通過)**

#### 班別編輯與工時調整功能補齊 (Shift Update & Working Hours Adjustment Implementation)

- **執行時間**：2026-10-23
- **問題回報與症狀 (Incident & Symptoms)**：
  - 使用者回報「班別無法調整」；在人資管理系統的「班別與工時 (Shifts)」標籤頁中，僅能檢視班別清單與新增班別，無法對現有班別的工作起訖時間、休息時數或標準工時進行編輯或調整。
- **根本原因深入分析 (Root Cause Analysis)**：
  1. **後端缺乏班別異動端點 (Missing Shift Update Endpoints)**：後端 [apps/api/app/api/v1/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/hr.py) 先前僅提供 `POST /shifts` 與 `GET /shifts`，缺乏 `PUT /shifts/{shift_id}`（修改班別）與 `DELETE /shifts/{shift_id}`（刪除班別）端點。
  2. **前端缺乏編輯操作介面 (Missing Edit Interface in UI)**：前端 [apps/web/src/components/hr/ShiftList.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/ShiftList.vue) 班別卡片上未放置任何編輯按鈕，且彈窗僅支援建立模式，無載入現有班別資料並保存之邏輯。
- **架構設計與修復處置 (Architectural Solutions & Actions)**：
  1. **資料庫遷移與結構擴充 (Alembic Migration & Schema Expansion)**：
     - 生成並執行遷移腳本 [alembic/versions/8b4d9e2c1a5f_add_shift_break_interval_and_flex_minutes.py](file:///c:/Sources/EtronJF8/apps/api/alembic/versions/8b4d9e2c1a5f_add_shift_break_interval_and_flex_minutes.py)。
     - 在 `shifts` 表中擴充：
       - `break_start_time` (String(5))：休息起始時間（例如 "12:00"）。
       - `break_end_time` (String(5))：休息結束時間（例如 "13:00"）。
       - `flex_minutes` (Integer, default 0)：彈性工時分鐘數（例如 30 分鐘）。
       - `updated_at` (DateTime)：最後調整時間戳。
     - 資料轉換：自動為現有班別補齊預設休息時段與彈性時數（常日班預設 12:00~13:00，彈性 30 分鐘）。
  2. **後端 RESTful API 實作**：
     - 於 [apps/api/app/api/v1/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/hr.py) 增加 `ShiftUpdate` Pydantic 驗證模型。
     - 實作 `PUT /api/v1/hr/shifts/{shift_id}` 端點：支援彈性更新班別代號、名稱、上班時間 (`work_start_time`)、下班時間 (`work_end_time`)、休息起始 (`break_start_time`)、休息結束 (`break_end_time`)、中場休息分鐘數 (`break_minutes`)、彈性分鐘數 (`flex_minutes`)、每日標準工時分鐘數 (`daily_standard_minutes`) 與是否跨夜班 (`is_overnight`)。
     - 實作 `DELETE /api/v1/hr/shifts/{shift_id}` 端點：具備安全約束保護，若有在職員工綁定該班別為預設班別（`Employee.default_shift_id == shift_id`），拋出 `SHIFT_IN_USE` (HTTP 400) 阻擋刪除。
  3. **前端介面、工時試算與視覺設計優化 (Rich Aesthetics & Interactive Controls)**：
     - 於 [apps/web/src/components/hr/ShiftList.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/ShiftList.vue) 徹底重構班別卡片：
       - 明顯展示「🕒 工作時間」、「☕ 休息時間（從幾點到幾點）」、「🎯 彈性時間（彈性打卡區間推導）」與「⚖️ 法定標準工時」。
       - 為每一班別卡片配置醒目的「✏️ 調整班別設定」與「🗑️ 刪除」按鈕。
     - 彈窗支援新增與編輯雙模式，在編輯模式下主鍵 ID 鎖定，自動代入原有班別各項數值。
     - 實作智慧工時即時試算功能（`autoCalculateMinutes` & `handleBreakTimeChange`）：調整休息起訖時自動折算休息分鐘數；調整上班起訖時間、午休分鐘數或跨夜選項時，即時自動扣除休息時數試算每日淨標準工時（例如 09:00~18:00 扣除 60 分鐘午休自動折算為 480 分鐘 / 8.00 小時）。
  4. **自動化整合測試**：
     - 在 [apps/api/tests/test_hr_full_system.py](file:///c:/Sources/EtronJF8/apps/api/tests/test_hr_full_system.py) 之 `test_shifts_calendars_and_leave_types_master` 測試中追加 `PUT /api/v1/hr/shifts/{id}` 驗證，確保調整後起訖時間、休息時段與標準工時正確保存並即時反映於查詢結果。
- **測試命令與實際輸出 (Verified Execution)**：
  - **人資系統全流程測試 (pytest)**：
    - `pytest apps/api/tests/test_hr_full_system.py` -> **9 passed in 3.02s (100% 通過)**
  - **後端全套單元測試 (pytest)**：
    - `pytest apps/api/tests` -> **69 passed in 15.22s (全模組 69 項測試 100% 通過)**
  - **前端單元測試與四語完整性 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.95s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 72 modules transformed, built in 2.30s (100% 通過)**
  - **Markdown 文件規範檢查 (markdownlint-cli)**：
    - `npx markdownlint-cli README.md` -> **0 errors, 0 warnings (100% 通過)**

#### 帳號管理及權限設定系統實作 (User IAM & RBAC Permissions Management)

- **執行時間**：2026-10-23
- **架構原則**：
  1. **雙頁籤架構與現代化美學設計 (Tabbed IAM Architecture & Rich Aesthetics)**：
     - **標籤 1：帳號名冊與設定 (`User Accounts`)**：包含頂部統計指標（總帳號數、正常啟用、停用/凍結、待改密碼）、多條件組合篩選（關鍵字、角色、狀態）、完整使用者名冊表格（頭像、帳號、姓名、Email、主屬公司、關聯員工工號、角色標籤、狀態開關）以及管理員操作群組（✏️ 編輯、🛡️ 分配角色、🔑 重設密碼、🚫 停用 / ✅ 啟用 開關）。
     - **標籤 2：角色與 RBAC 權限設定 (`Roles & RBAC Matrix`)**：左側角色清單（顯示系統內建/自訂標籤、授權項目數、成員數）與新增自訂角色；右側為角色專屬之「全模組權限矩陣配置面板」，支援按模組（HR、LEAVE、ATTENDANCE、TRAVEL、EXPENSE、SEAL、CONTRACT、SYSTEM）分組展示、單鍵全選/取消全選以及原子更新權限配置。
  2. **伺服器端權限種子自動補齊與驗證 (Seed Permissions & Built-in Roles Initialization)**：
     - 於後端全面初始化 26 項全模組業務權限（涵蓋人事組織、假單審查、加班補休、考勤匯入、出差結報、費用報銷、供應商請款、用印登記、合約審查與系統管理）。
     - 自動生成與維護 6 大標準內建角色（`ADMIN`, `HR_ADMIN`, `FINANCE_OFFICER`, `LEGAL_OFFICER`, `DEPT_HEAD`, `GENERAL_USER`），嚴格禁止刪除內建系統角色。
  3. **帳號安全性與強制首登改密 (Account Lifecycle & Mandatory First Login Password Change)**：
     - 新增帳號支援設定初始密碼，並預設勾選「強制首次登入變更密碼 (`must_change_password`)」。
     - 帳號停用（`suspend`）時自動撤銷該帳號名下所有進行中的登入 Sessions，立即強制中斷其連線。
     - 管理員重設密碼支援自訂臨時密碼並重設首登改密旗標。
  4. **四國語言 i18n 與全模組導航完整集成 (i18n & AppShell Navigation Integration)**：
     - 在繁中 (`zh-TW`)、日語 (`ja-JP`)、英語 (`en-US`) 與簡中 (`zh-CN`) 完整收錄 `nav.users` 語系字串。
     - 在 `AppShell.vue` 側邊欄與 `App.vue` 儀表板快捷入口全面掛載 `users` 模組導航按鈕，無縫切換。
- **完成項目**：
  1. **後端 RESTful API 與授權驗證 ([users.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/users.py))**：
     - `GET /api/v1/users`：多條件過濾查詢帳號清單與關聯角色/工號。
     - `POST /api/v1/users`：建立新帳號並指派角色與主屬公司。
     - `GET /api/v1/users/{id}`、`PUT /api/v1/users/{id}`：查詢與編輯帳號資料。
     - `POST /api/v1/users/{id}/activate`：啟用帳號。
     - `POST /api/v1/users/{id}/suspend`：停用帳號並撤銷所有 Sessions。
     - `POST /api/v1/users/{id}/reset-password`：管理員重設密碼。
     - `PUT /api/v1/users/{id}/roles`：更新使用者角色分配。
     - `GET /api/v1/users/meta/permissions`：取得依模組分組之全系統權限字典。
     - `GET /api/v1/users/meta/roles`、`POST /api/v1/users/meta/roles`、`PUT /api/v1/users/meta/roles/{id}/permissions`、`DELETE /api/v1/users/meta/roles/{id}`：角色 CRUD 與權限矩陣批次指派。
  2. **前端高質感介面組件 ([UserManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/users/UserManagementView.vue))**：
     - 實作完整的使用者名冊檢視、即時搜尋、建立帳號彈窗、編輯帳號彈窗、指派角色彈窗、重設密碼彈窗、角色清單與模組權限矩陣勾選面板。
  3. **導航與多語整合 ([AppShell.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/AppShell.vue) & [App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue) & [i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts))**：
     - 側邊欄掛載「🛡️ 帳號與權限」選單，儀表板提供快捷進入通道。
- **測試命令與實際輸出 (Verified Execution)**：
  - **RBAC 與認證授權專屬測試 (pytest)**：
    - `pytest apps/api/tests/test_auth_rbac.py` -> **5 passed in 2.12s (100% 通過)**
  - **後端全套單元測試 (pytest)**：
    - `pytest apps/api/tests` -> **69 passed in 15.08s (全模組 69 項測試 100% 通過)**
  - **前端單元測試與四語完整性 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.44s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 74 modules transformed, built in 2.39s (100% 通過)**

#### 彈窗操作按鈕文案體驗優化 (Modal Action Labels UX Optimization)

- **執行時間**：2026-10-23
- **問題回報與症狀 (Incident & Feedback)**：
  - 在「編輯公司基本資料」等維護彈窗介面中，底部取消按鈕原顯示為「撤銷」，儲存提交按鈕原顯示為「送出申請」，文案與一般設定編輯視窗之使用者操作直覺不符。
- **架構設計與修復處置 (Architectural Solutions & Actions)**：
  - 更新多國語言字典 [apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts)：
    - 繁體中文 (`zh-TW`)：`actions.cancel` 由「撤銷」調整為「取消」；`actions.submit` 由「送出申請」調整為「儲存」，並同步補齊 `actions.save: '儲存'`。
    - 日本語 (`ja-JP`)：`actions.submit` 調整為「保存」，補齊 `actions.save: '保存'`。
    - 英語 (`en-US`)：`actions.submit` 調整為「Save」，補齊 `actions.save: 'Save'`。
    - 簡體中文 (`zh-CN`)：`actions.cancel` 調整為「取消」；`actions.submit` 調整為「保存」，補齊 `actions.save: '保存'`。
  - 維持四語系鍵值深度對齊與測試無誤。
- **測試命令與實際輸出 (Verified Execution)**：
  - **前端單元測試與四語完整性 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.76s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 74 modules transformed, built in 3.27s (100% 通過)**

#### 帳號與權限頁籤切換卡死異常修復與資料防禦性強化 (IAM Tab Switching Stalling Fix & Defensive Normalization)

- **執行時間**：2026-10-23
- **問題回報與症狀 (Incident & Symptoms)**：
  - 使用者在「帳號與權限管理」介面中，先切換至「角色與權限矩陣 (Roles & RBAC)」，再切換回「帳號名冊與管理 (Users)」時，系統一直停留在「正在載入使用者帳號資料...」，使用者列表與頂部統計數字顯示為 0，無法正常渲染。
- **根本原因深入分析 (Root Cause Analysis)**：
  1. **角色物件陣列型別不吻合觸發 TypeError**：後端 `/api/v1/users` 回傳之 `roles` 欄位為包含詳細資訊之物件陣列（`[{"role_id": "...", "role_name": "..."}]`），前端 template 在渲染角色徽章時執行 `r.includes('HR')` 與 `r.includes('FINANCE')`，引發 `TypeError: r.includes is not a function`，導致 Vue 元件渲染管線崩潰中斷。
  2. **角色授權端點缺少 GET 方法 (HTTP 405 Method Not Allowed)**：後端路由 `/meta/roles/{role_id}/permissions` 僅定義了 `PUT` 方法供儲存更新，缺少 `GET` 端點，導致切換選取角色讀取授權時拋出 HTTP 405 錯誤。
  3. **權限字典回傳陣列結構對齊問題**：後端 `/meta/permissions` 回傳為陣列型態，前端原嘗試讀取 `.groups` 屬性導致為 `undefined`。
- **架構設計與修復處置 (Architectural Solutions & Actions)**：
  1. **後端端點補齊與相容性欄位擴充 ([users.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/users.py))**：
     - 新增 `GET /api/v1/users/meta/roles/{role_id}/permissions` 端點，回傳指定角色之授權清單。
     - 在 `GET /api/v1/users` 回傳物件中補充 `active_company_id`、`must_change_password`、`employee_no` 與字串代碼清單 `role_names`。
     - 在 `GET /api/v1/users/meta/roles` 中同步提供 `users_count`、`permissions_count`、`is_system` 相容性欄位。
  2. **前端資料防禦性正規化與安全渲染 ([UserManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/users/UserManagementView.vue))**：
     - `fetchUsers` 強化型別過濾：自動解析並扁平化角色代碼字串陣列。
     - `fetchRolesMeta` 與 `fetchPermissionsDictionary` 強化陣列驗證與屬性安全對齊。
     - 封裝 `getRoleBadgeClass(r)` 輔助函式，杜絕直接在 template 執行非字串的 `includes()` 操作。
     - 實作 `switchTab` 頁籤切換器，保證 Tab 狀態平順切換與按需安全載入。
- **測試命令與實際輸出 (Verified Execution)**：
  - **後端全套單元測試 (pytest)**：
    - `pytest apps/api/tests` -> **69 passed in 15.70s (100% 通過)**
  - **前端單元測試與四語完整性 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.51s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 74 modules transformed, built in 2.38s (100% 通過)**

#### 側邊欄導航選單重複項目清理 (Sidebar Navigation Deduplication)

- **執行時間**：2026-10-23
- **問題回報與症狀 (Incident & Feedback)**：
  - 使用者點選側邊欄「簽核待辦 (`inbox`)」時，視圖呈現內容與「營運儀表板 (`dashboard`)」完全相同，造成導覽功能重複與體驗混淆，指示移除側邊欄「簽核待辦」按鈕。
- **架構設計與修復處置 (Architectural Solutions & Actions)**：
  - 更新 [apps/web/src/components/common/AppShell.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/AppShell.vue)：
    - 從側邊欄導航清單中移除 `inbox`（簽核待辦）按鈕，保留清爽明確的業務模組架構（營運儀表板、人事系統、請假管理、出勤管理、出差與結報、費用報支、用印申請、供應商請款、合約管理、帳號與權限）。
- **測試命令與實際輸出 (Verified Execution)**：
  - **後端全套單元測試 (pytest)**：
    - `pytest apps/api/tests` -> **69 passed in 17.36s (100% 通過)**
  - **前端單元測試與四語完整性 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.87s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 74 modules transformed, built in 2.57s (100% 通過)**

#### 營運儀表板範例錯誤面板清理 (Dashboard Error Panel Demo Clean-up)

- **執行時間**：2026-10-23
- **問題回報與症狀 (Incident & Feedback)**：
  - 營運儀表板頂部存在展示用之「關閉錯誤面板 / 展示錯誤面板」切換按鈕，下方常態呈現粉紅色錯誤示範面板 (`ErrorPanel`，`[APPROVAL_CONFLICT] 簽核衝突或資料已被他人變更，請重新整理`)，影響實際營運畫面與視覺體驗。
- **架構設計與修復處置 (Architectural Solutions & Actions)**：
  - 更新 [apps/web/src/App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue)：
    - 移除頂部操作列之錯誤面板開關按鈕。
    - 移除下方展示用之粉紅色 `<ErrorPanel>` 元件區塊。
    - 清理未使用的 `showError` 響應式狀態與 `ErrorPanel` 模組引用，使首頁儀表板回歸乾淨專業之營運指標視圖。
- **測試命令與實際輸出 (Verified Execution)**：
  - **後端全套單元測試 (pytest)**：
    - `pytest apps/api/tests` -> **69 passed in 15.55s (100% 通過)**
  - **前端單元測試與四語完整性 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.68s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 72 modules transformed, built in 2.72s (100% 通過)**

#### 側邊欄左下角核心版本與除錯狀態區塊清理 (Sidebar Footer Info Clean-up)

- **執行時間**：2026-10-23
- **問題回報與症狀 (Incident & Feedback)**：
  - 側邊欄左下角原放置展示系統開發資訊之文字區塊（`ETJ Core v0.1.0`、`SQLite WAL Mode (Full Sync)`、`● 認證階段保護中`），影響系統介面之簡潔度與正式營運視覺觀感。
- **架構設計與修復處置 (Architectural Solutions & Actions)**：
  - 更新 [apps/web/src/components/common/AppShell.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/AppShell.vue)：
    - 移除側邊欄底部之版本號、資料庫引擎日誌模式與登入除錯提示文字區塊，使側欄選單更為簡潔專業。
- **測試命令與實際輸出 (Verified Execution)**：
  - **前端單元測試與四語完整性 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.70s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 72 modules transformed, built in 2.40s (100% 通過)**

#### 營運儀表板後端狀態橫幅清理 (Dashboard Health Banner Clean-up)

- **執行時間**：2026-10-23
- **問題回報與症狀 (Incident & Feedback)**：
  - 營運儀表板頂部常態展示後端健康檢查狀態橫幅（`[healthy] 後端核心狀態: SQLite (SQLite 3.50.4) WAL 模式運作中`、`UTC 基準時間`），使用者指示將此開發測試除錯資訊由一般業務儀表板中正式移除。
- **架構設計與修復處置 (Architectural Solutions & Actions)**：
  - 更新 [apps/web/src/App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue)：
    - 移除首頁儀表板上方之 `<div v-if="health" class="mb-6 ...">` 橫幅區塊。
    - 清理未使用的 `health`、`loadingHealth`、`fetchHealth` 及其 TypeScript 介面定義，使儀表板視覺焦點專注於業務操作。
- **測試命令與實際輸出 (Verified Execution)**：
  - **後端全套單元測試 (pytest)**：
    - `pytest apps/api/tests` -> **69 passed in 16.29s (100% 通過)**
  - **前端單元測試與四語完整性 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.74s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 72 modules transformed, built in 2.19s (100% 通過)**

#### 營運儀表板表單元件示範卡片清理 (Dashboard Form Component Showcase Clean-up)

- **執行時間**：2026-10-23
- **問題回報與症狀 (Incident & Feedback)**：
  - 營運儀表板展示區塊中包含開發初期供視覺檢驗之三張卡片：「金額輸入元件 (MoneyInput - Decimal 無精度遺失)」、「日期輸入元件 (DateTimeInput - Date Only)」以及「狀態標籤展示 (StatusBadge)」，在正式營運環境中屬於冗餘示範內容，使用者指示予以移除。
- **架構設計與修復處置 (Architectural Solutions & Actions)**：
  - 更新 [apps/web/src/App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue)：
    - 移除首頁儀表板上方之 `<div class="grid grid-cols-1 md:grid-cols-3 gap-6">` 內之三張示範卡片。
    - 移除未使用之 `MoneyInput`、`DateTimeInput` 與 `FormField` 元件引入。
    - 清理響應式示範變數 `demoMoney`、`demoCurrency` 與 `demoDate`，使營運儀表板完全專注於業務資料過濾與待辦單據表格。
- **測試命令與實際輸出 (Verified Execution)**：
  - **後端全套單元測試 (pytest)**：
    - `pytest apps/api/tests` -> **69 passed in 23.22s (100% 通過)**
  - **前端單元測試與四語完整性 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.61s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 70 modules transformed, built in 2.79s (100% 通過)**

#### 人事系統頁籤導航順序調整 (HR Module Tab Navigation Order Reorganization)

- **執行時間**：2026-10-23
- **問題回報與症狀 (Incident & Feedback)**：
  - 人事系統內部導航原先首項為「公司基本資料」，使用者指定調整頁籤順序為：
    1. 👥 員工名冊與到職報到 (`employees`)
    2. 🏢 公司基本資料 (`companies`)
    3. 🌳 組織與部門階層 (`organizations`)
    4. ⏱️ 班別與工時 (`shifts`)
    5. 🌴 假額天數與帳本 (`leaveLedger`)
- **架構設計與修復處置 (Architectural Solutions & Actions)**：
  - 更新 [apps/web/src/components/hr/HrManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/HrManagementView.vue)：
    - 將 `activeTab` 預設值切換為 `'employees'`，使進入人事系統時優先呈現在職員工名冊與報到操作。
    - 調整頂部 Tab 導航按鈕渲染順序，由 `employees` 置頂，依序為 `companies`、`organizations`、`shifts`、`leaveLedger`。
    - 同步調整下方內容區塊條件渲染結構，維持邏輯與 UI 頁籤一致性。
- **測試命令與實際輸出 (Verified Execution)**：
  - **前端單元測試與四語完整性 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.83s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 70 modules transformed, built in 3.40s (100% 通過)**

#### 員工基本個資維護與到職報到分離重構 (Person Profile vs Company Employment Decoupling)

- **執行時間**：2026-10-23
- **問題回報與業務需求 (Business Requirements & Feedback)**：
  - 新進員工報到建立作業中，原先將自然人身分個資與公司任職資料混合於單一表單。
  - 依集團多公司營運模式（Multi-Company Conglomerate HR），同一自然人（如吳金樹）可能同時於集團旗下多家公司（如台灣總部與福岡支社）擔任職務或兼任主管。
  - 規格要求將「員工基本資料維護 (Person Profile)」與「公司到職報到 (Employment Assignment)」予以分離，支援同一自然人主體跨公司多重任職。
- **架構設計與修復處置 (Architectural Solutions & Actions)**：
  1. **資料模型解耦 (Database Model Decoupling)**：
     - 新增獨立之 `Person` 模型（`persons` 資料表），專職保管集團自然人法定主體資料（姓名、英文名、身分證/居留證字號 `national_id`、出生日期、性別、國籍、通訊住址與緊急聯絡人）。
     - 更新 `Employee` 模型，新增 `person_id` 外鍵關聯至 `persons.id`；並將工號唯一性改為公司維度複合約束 `UniqueConstraint("company_id", "employee_no")`，實現各公司獨立編制工號。
     - 防重複在職檢驗：同一自然人在同一公司同期間嚴格禁止重複報到在職 (`DUPLICATE_COMPANY_EMPLOYMENT`)。
  2. **資料庫遷移與平滑移轉 (Alembic Migration & Data Transformation)**：
     - 生成並套用遷移腳本 [apps/api/alembic/versions/9c5e0f1a2b3d_create_persons_table_and_link_employees.py](file:///c:/Sources/EtronJF8/apps/api/alembic/versions/9c5e0f1a2b3d_create_persons_table_and_link_employees.py)。
     - 遷移程序自動提取現存所有 `employees` 資料，依身分證號聚合生成對應之 `Person` 實體並回填 `person_id`，達成平滑無痛資料升級。
  3. **後端服務與 API 擴充 (Backend Domain Services & RESTful Endpoints)**：
     - 新增 `GET /api/v1/hr/persons`（支援關鍵字、身分證號即時搜尋集團人員主檔庫）。
     - 新增 `GET /api/v1/hr/persons/{id}` 與 `PUT /api/v1/hr/persons/{id}`（維護自然人個資，同步連動各公司任職顯示）。
     - 擴充 `POST /api/v1/hr/employees`，支援直接以既有 `person_id` 辦理跨公司新任職，亦支援一次性新創人員並報到。
     - 擴充 `GET /api/v1/hr/employees/{id}`，動態載入該自然人之跨公司任職清單 (`other_employments`)。
  4. **前端兩步驟引導介面 (Two-step Guided Onboarding UI/UX)**：
     - 更新 [apps/web/src/components/hr/OnboardModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OnboardModal.vue)：
       - **步驟一：員工基本個資維護 (Person Profile)**：提供搜尋現有人員快捷鍵，輸入身分證/姓名一鍵帶入個資並自動關聯，亦可手動填寫新人員；
       - **步驟二：本公司到職任職設定 (Company Employment)**：設定本公司專屬之工號、公務信箱、部門、職稱、職等、到職日與系統帳號。
     - 更新 [apps/web/src/components/hr/EmployeeDetailModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/EmployeeDetailModal.vue)，在職員工詳情卡片中即時呈現跨公司兼任與任職徽章。
     - 更新 [apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts) 補齊四語系相關字典鍵值。
- **測試命令與實際輸出 (Verified Execution)**：
  - **後端全套單元測試 (pytest)**：
    - `pytest apps/api/tests` -> **70 passed in 15.82s (新增多公司任職測試，100% 通過)**
  - **前端單元測試與四語完整性 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.43s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 70 modules transformed, built in 2.06s (100% 通過)**

#### 頂端所屬公司選單與法人公司基本資料動態綁定 (Top Bar Company Selector Dynamic Binding)

- **執行時間**：2026-10-23
- **問題回報與症狀 (Incident & Feedback)**：
  - 頂端導覽列 Header 中的「🏢 所屬公司」下拉選單原先為硬編碼（Hardcoded）之靜態選項（僅列有 `ETJ-TW`、`ETJ-JP` 兩家），未能動態反映「法人公司基本資料維護」中已註冊之完整公司清單（包含新設立之 `ETRON` 鈺創科技股份有限公司、`ETJ` 鈺創-福岡等），導致無法切換至新公司作業。
- **架構設計與修復處置 (Architectural Solutions & Actions)**：
  1. **建立全域公司資料狀態模組 (Global Company State Management)**：
     - 新增 [apps/web/src/utils/companies.ts](file:///c:/Sources/EtronJF8/apps/web/src/utils/companies.ts)，提供響應式 `availableCompanies`、`activeCompanyId` 與異步載入函式 `fetchAvailableCompanies()`。
  2. **頂端選單動態綁定 (Dynamic Selector in AppShell)**：
     - 更新 [apps/web/src/components/common/AppShell.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/AppShell.vue)：
       - 於 `onMounted` 自後端 `/api/v1/hr/companies` 動態載入所有已啟用之法人公司；
       - 下拉選單改由 `availableCompanies` 以 `v-for` 動態渲染，呈現公司法定名稱與記帳幣別（例如 `鈺創科技股份有限公司 (TWD)`）；
       - 切換公司時同步寫入 `localStorage`，並透過 slot 與事件廣播連動全系統視圖。
  3. **公司維護即時聯動 (Real-time Sync on Company Mutation)**：
     - 更新 [apps/web/src/components/hr/CompanyManagement.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/CompanyManagement.vue)，在「+ 新增註冊公司」或「編輯公司資料」完成後立即觸發 `fetchAvailableCompanies()`，頂端所屬公司下拉選單無須重新整理即可即時同步更新。
- **測試命令與實際輸出 (Verified Execution)**：
  - **後端全套單元測試 (pytest)**：
    - `pytest apps/api/tests` -> **70 passed in 15.18s (100% 通過)**
  - **前端單元測試與四語完整性 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.45s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 71 modules transformed, built in 2.48s (100% 通過)**

#### 員工生命週期作業原則重構：基本資料維護 ➔ 報到 ➔ 異動 ➔ 離職 (Employee Lifecycle Workflow Restructuring)

- **執行時間**：2026-10-23
- **問題回報與業務原則 (Business Lifecycle & Principle)**：
  - 使用者明確指派人事作業直觀原則為四部曲生命週期：
    1. **員工的基本資料維護 (Person Master Profile Maintenance)**
    2. **報到作業 (Company Onboarding & Employment Setup)**：填寫報到時對應之任職資訊
    3. **異動作業 (Transfer & Promotion)**：更換部門、職位、Title、職等 Grade
    4. **離職作業 (Resignation & Offboarding)**：登記離職生效日並停用系統帳號
  - 舊設計將自然人個資建檔與報到作業擠在同一表單，不僅直觀上不易操作，且無法清晰體現多公司任職之主體關係與各階段作業邊界。
- **架構設計與修復處置 (Architectural Solutions & Actions)**：
  1. **第 1 步：獨立「🪪 人員基本檔案庫 (Person Master Profiles)」視圖**：
     - 新增獨立組件 [apps/web/src/components/hr/PersonManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/PersonManagementView.vue) 與 [apps/web/src/components/hr/PersonModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/PersonModal.vue)；
     - 專職維護集團自然人身份主檔（姓名、英文名、身分證號、生日、性別、國籍、電話、現居地、戶籍地、緊急聯絡人），不綁定特定公司工號與部門；
     - 提供即時關鍵字搜尋、多公司兼任在職徽章顯示，並提供「✏️ 維護個資」與「📝 辦理報到」快捷按鈕。
  2. **第 2 步：純粹的「報到作業 (Onboarding Modal)」**：
     - 重構 [apps/web/src/components/hr/OnboardModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OnboardModal.vue)；
     - 專注填寫本公司的任職設定：選擇欲報到之人員（支援即時搜尋或自檔案庫直接帶入）、分配本公司工號、公務電子信箱、分派組織部門、職稱、職等、到職日與一鍵開通帳號；若尚未建檔可隨時切換至檔案庫先建檔。
  3. **第 3 步：完整支援更換部門、職位、Title 的「異動作業 (Transfer Modal)」**：
     - 擴充後端 API `POST /api/v1/hr/employees/{id}/transfer` 及 [apps/api/app/api/v1/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/hr.py) 中的 `TransferEmployeeRequest`，支援 `new_organization_id`、`new_job_title`、`new_job_grade`；
     - 重構 [apps/web/src/components/hr/TransferModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/TransferModal.vue)，在「職務異動」模式下完整提供「新所屬部門」、「新職務職稱 (Title)」、「新職等職級 (Grade)」之並行異動，並留存異動原因、生效日期與完整異動歷程軌跡 (`EmployeeChange`)。
  4. **第 4 步：明確分離的「離職作業 (Resignation Modal)」**：
     - 離職登記模式專注填寫離職生效日與原因備註，完成後標記狀態為 `RESIGNED`，並同步停用登入帳號及撤銷授權。
  5. **頁籤與導航重新梳理 (Tab & Lifecycle Flow Refactoring)**：
     - 更新 [apps/web/src/components/hr/HrManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/HrManagementView.vue)：
       - Tab 0：`🪪 人員基本檔案庫`（自然人基本資料維護）
       - Tab 1：`👥 在職員工與任職管理`（報到、名冊、異動、離職、歷程）
       - Tab 2：`🏢 公司基本資料`
       - Tab 3：`🌳 組織與部門階層`
       - Tab 4：`⏱️ 班別與工時`
       - Tab 5：`🌴 假額天數與帳本`
     - 在「在職員工與任職管理」上方加入清晰的「① 自然人建檔 ➔ ② 報到作業 ➔ ③ 異動作業 ➔ ④ 離職作業」生命週期橫幅，操作按鈕明確標記「🔍 詳情」、「🔄 異動作業」、「🚪 離職作業」、「📜 歷程」。
  6. **四語系與測試校正 (i18n & Test Alignment)**：
     - 更新 [apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts) 與 [apps/web/tests/hr-components.test.ts](file:///c:/Sources/EtronJF8/apps/web/tests/hr-components.test.ts)，四語系字典完整支援 `hr.tabs.persons` 與更新之 `hr.tabs.employees`。
- **測試命令與實際輸出 (Verified Execution)**：
  - **後端全套回歸測試 (pytest)**：
    - `pytest apps/api/tests` -> **70 passed in 15.30s (100% 通過)**
  - **前端單元測試與四語完整性 (vitest)**：
    - `npm run test` -> **5 test files passed, 16 passed in 2.44s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 75 modules transformed, built in 2.72s (100% 通過)**

#### 儀表板與報到表單日語及四語系欄位全面動態化修正 (Japanese & Multi-Language i18n Dynamic Alignment)

- **執行時間**：2026-10-23
- **問題回報與症狀 (Incident & Feedback)**：
  - 使用者在切換系統語系至「日本語 (ja-JP)」時，回報儀表板畫面存在大量寫死中文標題與欄位未切換：
    1. 儀表板副標題（原為 `目前顯示時區：...`）；
    2. 右上角功能按鈕（原為 `🛡️ 帳號與權限管理`、`👥 進入人事系統`）；
    3. 搜尋列 placeholder 與按鈕（原為 `搜尋單號、申請人姓名...`、`查詢`、`重設`）；
    4. 表格標題欄位（原為 `單號`、`單據類型`、`申請人`、`金額`、`簽核狀態`、`送簽時間 (本地時區)`）；
    5. 單據類型欄位資料（原為 `特別休假`、`費用報支`、`出差申請`、`用印申請`）；
    6. 分頁頁尾（原為 `共 X 筆紀錄，第 Y 頁`、`上一頁`、`下一頁`）；
    7. 報到作業彈窗 [apps/web/src/components/hr/OnboardModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OnboardModal.vue) 標題、任職設定與聘僱類型選項。
- **架構設計與修復處置 (Architectural Solutions & Actions)**：
  1. **擴充四語系字典結構 (i18n Resource Expansion)**：
     - 更新 [apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts)：
       - 在 `zh-TW`、`ja-JP`、`en-US`、`zh-CN` 建立全新 `dashboard` 字典節點，收錄時區標示、按鈕文字、搜尋提示、欄位名稱及單據類型對照；
       - 擴充 `hr.onboardModal` 字典，補齊彈窗主標題、副標題、人員挑選、任職配置、部門選擇及完成報到等各層級標籤；
       - 擴充 `hr.employmentTypes` 字典（正社員、試用期中、契約社員、インターン、パート・アルバイト）。
  2. **共用組件全面動態多語系化 (Common Component i18n Refactoring)**：
     - 更新 [apps/web/src/components/common/FilterBar.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/FilterBar.vue)：改用 `t('actions.search')` 與 `t('actions.reset')` 動態渲染按鈕與 placeholder。
     - 更新 [apps/web/src/components/common/DataTable.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/DataTable.vue)：改用 `t('status.loading')`、`t('table.empty')`、`t('table.totalRecords')`、`t('actions.prevPage')`、`t('actions.nextPage')`。
  3. **視圖與彈窗動態欄位改寫 (View & Modal Dynamic Binding)**：
     - 更新 [apps/web/src/App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue)：
       - 將靜態 `columns` 重構成 `computed<TableColumn[]>(() => [...])`，確保切換語言時表格表頭即時響應重繪；
       - 表格列增加 `typeKey` 欄位，在 `<template #type>` 透過 `t('dashboard.types.' + row.typeKey)` 即時動態切換；
       - 儀表板副標題、按鈕及其他模組副標題全面接入 `t('dashboard.companyAndTz', ...)` 與 `t('dashboard.currentTimezone', ...)`。
     - 更新 [apps/web/src/components/hr/OnboardModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OnboardModal.vue)：將所有寫死文字全面改為 `t('hr.onboardModal.*')` 與 `t('hr.employmentTypes.*')`。
- **測試命令與實際輸出 (Verified Execution)**：
  - **前端單元測試與四語完整性 (vitest)**：
    - `npm run test -- --run` -> **5 test files passed, 16 passed in 2.62s (100% 通過)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 75 modules transformed, built in 3.34s (100% 通過)**
  - **真實瀏覽器實測驗證 (Browser Subagent E2E Verification)**：
    - 啟動瀏覽器載入 `http://localhost:5173`，切換語系至「日本語 (ja-JP)」；
    - 實證確認副標題顯示為 `現在の表示タイムゾーン：台北 (Asia/Taipei, UTC+8)`；
    - 右上角操作按鈕顯示為 `アカウント・権限管理` 與 `人事システムへ`；
    - 搜尋列顯示 `申請番号、申請者氏名で検索...`、按鈕為 `検索` 與 `リセット`；
    - 表格欄位顯示為 `申請番号`, `申請種別`, `申請者`, `金額`, `承認ステータス`, `申請日時 (現地時間)`；
    - 單據類型顯示為 `有給休暇`, `経費精算`, `出張申請`, `押印申請`；
    - 分頁頁尾顯示為 `全 4 件中、1 ページ目` 與 `前へ`, `次へ`；
    - 成功儲存真實截圖至工作區。

#### HR 模組全欄位與彈窗多語系動態響應全面修復 (HR All Field Titles & Modals i18n Dynamic Alignment)

- **執行時間**：2026-10-23
- **問題回報與症狀 (Incident & Feedback)**：
  - 使用者在人事系統切換為日本語 (ja-JP) 或英語 (en-US) 時，回報「部分欄位 title 沒有跟著語系變動」，在部分子頁籤與彈窗中仍殘留寫死中文標題與表單標籤：
    1. 人員主檔庫 (Person Master Profiles) 之功能副標題與操作按鈕；
    2. 異動與離職作業彈窗 [TransferModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/TransferModal.vue) 之彈窗標題、員工標籤、現職資訊、新部門、新職位、新職等、生效日、資安防護警告及確認按鈕；
    3. 員工詳細資料彈窗 [EmployeeDetailModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/EmployeeDetailModal.vue) 之版本號、身分證遮罩、性別、生日、國籍、婚姻、直屬主管、集團兼任公司數、通訊與緊急聯絡人欄位；
    4. 異動歷史彈窗 [EmployeeHistoryModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/EmployeeHistoryModal.vue) 之歷程時間軸、到職/調動/離職/晉升標籤與關閉按鈕；
    5. 班別與工時設定 [ShiftList.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/ShiftList.vue) 之主標題、副標題、新增班別按鈕、工時資訊卡片、新增與編輯班別彈窗的所有表單欄位與選項；
    6. 假額天數與帳本 [LeaveLedgerView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/LeaveLedgerView.vue) 之「選擇查核員工」label、基準日、假額彙總卡片、不可變流水帳本表頭、手動發放假額彈窗；
    7. 公司基本資料 [CompanyManagement.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/CompanyManagement.vue) 與組織階層 [OrgTree.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OrgTree.vue) 之標題、副標題、未設定 fallback、輸入框 placeholder 與無資料提示。
- **根本成因 (Root Cause)**：
  - 早期開發時，部分彈窗與子頁籤之表頭或表單 label 採用寫死中文文字；或者呼叫 `t('key', '繁中預設')` 時該鍵值僅存在於 `zh-TW` 或未定義於字典，導致語系切換時 fallback 至寫死中文。
- **架構設計與修復處置 (Architectural Solutions & Actions)**：
  1. **擴充四語系字典結構並嚴格對齊 (i18n Resource Expansion & Quad-Language Alignment)**：
     - 更新 [apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts)，在 `zh-TW`、`ja-JP`、`en-US`、`zh-CN` 建立並 100% 遞迴結構對齊以下鍵值：
       - `hr.transferModal`（異動與離職彈窗完整欄位與資安警示）；
       - `hr.employeeDetailModal`（員工詳情彈窗之各項身分、主管、聯絡人與兼職資訊）；
       - `hr.employeeHistoryModal`（異動歷史彈窗之時間軸與類型標記）；
       - `hr.shifts`（班別工時主標題、列表、卡片、表單欄位與彈性時間設定）；
       - `hr.ledger`（假額天數、不可變流水帳本、查核選單與手動發放彈窗）；
       - `hr.company`（法人公司管理標題、副標題、未設定 fallback 與 placeholder）；
       - `hr.org`（組織階層無資料提示與層級欄位）。
  2. **全面重構 Vue 元件接入多語系 (Vue Components i18n Dynamic Binding)**：
     - 更新 [TransferModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/TransferModal.vue)：所有寫死標題、label、placeholder 與按鈕改接 `t('hr.transferModal.*')`；
     - 更新 [EmployeeDetailModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/EmployeeDetailModal.vue)：身分、主管、兼職跨公司、版本、聯絡人全面改接 `t('hr.employeeDetailModal.*')`；
     - 更新 [EmployeeHistoryModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/EmployeeHistoryModal.vue)：引入 `useTranslation`，時間軸與狀態標籤改接 `t('hr.employeeHistoryModal.*')`；
     - 更新 [ShiftList.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/ShiftList.vue)：引入 `useTranslation`，班別列表、工時卡片、新增與編輯彈窗改接 `t('hr.shifts.*')`；
     - 更新 [LeaveLedgerView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/LeaveLedgerView.vue)：查核員工選單、基準日、假額彙總卡片、不可變流水帳本表頭、發放假額彈窗改接 `t('hr.ledger.*')`；
     - 更新 [CompanyManagement.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/CompanyManagement.vue) 與 [OrgTree.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OrgTree.vue)：副標題、placeholder 與無資料標籤全面接入 `t('hr.company.*')` 與 `t('hr.org.*')`。
- **測試命令與實際輸出 (Verified Execution)**：
  - **前端單元測試與四語完整性 (vitest)**：
    - `npm run test -- --run` -> **5 test files passed, 16 passed in 2.13s (100% 通過，四語鍵值 100% 遞迴無缺漏)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 75 modules transformed, built in 2.13s (100% 通過)**
  - **後端全套測試回歸驗證 (pytest)**：
    - `pytest apps/api/tests` -> **70 passed in 16.69s (100% 通過)**
  - **真實瀏覽器實測驗證 (Browser Subagent E2E Verification)**：
    - 啟動瀏覽器載入 `http://localhost:5173`，切換語系至「日本語 (ja-JP)」與「English (en-US)」；
    - 實證確認「Person Master Profiles」日語顯示為 `グループ人員基本台帳 (Person Master Profiles)`、操作按鈕為 `プロファイル作成`、`詳細編集`、`入社手続き`；
    - 英語切換下正確顯示為 `Person Master Profiles`、操作按鈕為 `Create Profile`、`Edit Profile`、`Onboarding`；
    - 班別工時、假額天數帳本、組織與公司等各子模組表頭與表單 label 均 100% 即時響應切換，無任何殘留中文；
    - 成功儲存真實驗證截圖至工作區。

#### 全系統 7 大業務模組欄位與表頭多語系動態響應全面完成 (Seven Business Modules i18n Alignment)

- **執行時間**：2026-10-23
- **問題回報與症狀 (Incident & Feedback)**：
  - 使用者截圖指出側欄 7 大核心模組（出勤管理、出差與結報、費用報支、用印申請、供應商請款、合約管理、帳號與權限），進入後其標題列、說明副標題、操作按鈕、頁籤導航、數據表格表頭與狀態標籤皆未隨語系動態變動，殘留寫死中文；且明確指示「**不要啟動 browser 測試**」。
- **根本成因 (Root Cause)**：
  - 先前多語系改造主要著重於「儀表板 (Dashboard)」與「人事管理主檔庫 (HR Master)」，其餘 7 個核心業務模組頁面當初實作時採用靜態寫死字串，且未在 [i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts) 建立各模組專屬字典鍵值結構。
- **架構設計與修復處置 (Architectural Solutions & Actions)**：
  1. **四國語系字典 100% 遞迴結構對齊擴充 (Quad-language Alignment)**：
     - 在 `zh-TW`、`ja-JP`、`en-US`、`zh-CN` 建立並遞迴結構對齊以下 7 大模組字典：
       - `attendanceView`（打卡按鈕、即時時鐘時區、流水帳表頭、異常標籤、批次匯入彈窗）；
       - `travelView`（出差與結報標題、申請/結報頁籤、多幣別匯率抵扣表頭、付款狀態）；
       - `expenseView`（費用報銷單號、報支幣別、重複發票即時警示標籤、付款狀態）；
       - `sealView`（用印單號、申請印鑑代號、份數、簽核狀態、用印實體狀態、印鑑清冊在庫狀態）；
       - `paymentView`（廠商請款單號、受款銀行快照、多級金額審批、供應商名冊）；
       - `contractView`（合約編號、相對人、合約類別、折合金額、履約生命週期狀態）；
       - `usersView`（帳號名冊、RBAC 角色、指派角色、安全操作、帳號狀態）。
  2. **全面重構 7 大視圖組件為響應式多語系 (Vue Components i18n Refactoring)**：
     - [AttendanceManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/attendance/AttendanceManagementView.vue)：全面改接 `t('attendanceView.*')`；
     - [TravelManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/travel/TravelManagementView.vue)：全面改接 `t('travelView.*')`；
     - [ExpenseManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/expense/ExpenseManagementView.vue)：全面改接 `t('expenseView.*')`；
     - [SealManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/seal/SealManagementView.vue)：全面改接 `t('sealView.*')`；
     - [PaymentManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/payment/PaymentManagementView.vue)：全面改接 `t('paymentView.*')`；
     - [ContractManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/contract/ContractManagementView.vue)：全面改接 `t('contractView.*')`；
     - [UserManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/users/UserManagementView.vue)：引入 `useTranslation`，頁籤、按鈕與表頭全面改接 `t('usersView.*')`。
  3. **遵循無瀏覽器自動化驗證規範 (Headless Automated CI Verification)**：
     - 恪遵使用者「不要啟動 browser 測試」規約，全程採用無外置瀏覽器之 Vitest 單元測試、TypeScript 靜態編譯檢查與 Pytest 後端回歸測試驗證。
- **測試命令與實際輸出 (Verified Execution)**：
  - **前端單元測試與四語完整性 (vitest)**：
    - `npm run test -- --run` -> **5 test files passed, 16 passed in 3.07s (100% 通過，四語鍵值 100% 遞迴無缺漏)**
  - **前端型別檢查與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 75 modules transformed, built in 3.80s (100% 通過)**
  - **後端全套測試回歸驗證 (pytest)**：
    - `pytest apps/api/tests` -> **70 passed in 24.15s (100% 通過)**

#### 人事系統：假管理（假別主檔設定、年資法定特休自動試算與批次發放、假額不可變帳本流水）(HR Leave Administration & Entitlement)

- **執行時間**：2026-10-23
- **需求與業務場景 (Business Scenario & Requirements)**：
  - 使用者明確要求擴充人事系統中的「假管理 (Leave Management)」，涵蓋：
    1. **假別主檔設定 (Leave Types Management)**：維護法人公司轄下之假別代碼 (`code`)、名稱 (`name`)、計算單位 (`unit`：`DAYS`/`HOURS`/`MINUTES`)、給薪屬性 (`is_paid`：全薪/無薪)、是否強制檢附證明 (`requires_attachment`)，支援新增與編輯。
    2. **年資法定特休自動試算與批次發放 (Annual Leave Entitlement Calculator & Batch Grant)**：依據員工之到職日 (`hire_date`) 與計算基準日 (`as_of_date`)，自動計算精確服務年資（年、月、日）與法定應給特休，並支援一鍵批次發放至不可變假額帳本 (`leave_ledger`)。
    3. **雙軌勞基法規支援**：精準支援台灣勞基法第 38 條週年制階梯與日本勞基法第 39 條年次有給休暇階梯。
    4. **帳本整合**：與現有不可變假額流水帳本 (`leave_ledger`) 無縫串接，保留歷史分錄稽核與可用額度即時折算。
- **架構設計與實作處置 (Architectural Design & Implementation)**：
  1. **年資計算與雙軌法規階梯演算法 (Entitlement Service & Statutory Stepladders)**：
     - 在 [apps/api/app/core/hr_rules.py](file:///c:/Sources/EtronJF8/apps/api/app/core/hr_rules.py) 建立 `LeaveEntitlementService`：
       - `calculate_seniority(hire_date, as_of_date)`：精確計算服務滿幾年幾月幾日。
       - `calculate_entitlement(hire_date, as_of_date, country)`：
         - **台灣週年制 (TW LSA Art. 38)**：
           - 滿 6 個月未滿 1 年：3 天 (1,440 分鐘)；
           - 滿 1 年未滿 2 年：7 天 (3,360 分鐘)；
           - 滿 2 年未滿 3 年：10 天 (4,800 分鐘)；
           - 滿 3 年未滿 5 年：14 天 (6,720 分鐘)；
           - 滿 5 年未滿 10 年：15 天 (7,200 分鐘)；
           - 滿 10 年以上：每滿 1 年加給 1 天，上限 30 天。
         - **日本有給休暇 (JP LSL Art. 39)**：
           - 滿 6 個月：10 天 (4,800 分鐘)；
           - 滿 1.5 年：11 天；滿 2.5 年：12 天；滿 3.5 年：14 天；滿 4.5 年：16 天；滿 5.5 年：18 天；滿 6.5 年以上：20 天 (9,600 分鐘)。
       - `get_company_entitlements_preview(db, company_id, as_of_date)`：查詢公司轄下所有在職員工，依到職日逐筆試算法定天數、換算標準工時分鐘數 (8h = 480m)，並查詢帳本當期是否已發放特休。
  2. **後端 API 契約與端點擴充 (FastAPI RESTful Endpoints)**：
     - 在 [apps/api/app/api/v1/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/hr.py) 擴充：
       - `LeaveTypeResponse` Pydantic 模型 (支援 `ConfigDict(from_attributes=True)`)；
       - `PUT /api/v1/hr/leave-types/{id}`：編輯現有假別名稱、單位、給薪屬性與附檔要求；
       - `GET /api/v1/hr/leave-entitlement/calculate`：回傳全公司在職員工特休年資試算清冊預覽；
       - `POST /api/v1/hr/leave-entitlement/grant-batch`：支援單筆或多筆特休批次發放至 `leave_ledger` (不可變分錄 `GRANT`)，記錄年資備註與有效起訖期間。
  3. **四語系國際化擴充 (i18n Quad-Language Alignment)**：
     - 在 [apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts) 於 `zh-TW`、`ja-JP`、`en-US`、`zh-CN` 建立 `hr.leaveAdmin` 物件，包含 38 個專業鍵值，100% 結構對齊。
  4. **前端視圖整合 (Vue Components)**：
     - 建立 [apps/web/src/components/hr/LeaveAdminView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/LeaveAdminView.vue)：
       - 提供 3 個子頁籤導航：`🏷️ 假別主檔設定`、`📅 法定特休年資試算發放`、`📒 假額帳本流水帳`；
       - 假別主檔設定：即時表格檢視、新增假種 Modal、編輯假種 Modal，具備防重複與錯誤提示；
       - 法定特休試算：自訂基準日、即時重新試算、員工清冊勾選 (Checkbox)、全選/反選、單筆一鍵發放、批次發放；
       - 假額帳本流水帳：無縫嵌入 [LeaveLedgerView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/LeaveLedgerView.vue)，完整保留員工假額額度彙總、分錄流水明細與手動發放。
     - 更新 [apps/web/src/components/hr/HrManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/HrManagementView.vue)：Tab 5 改接 `LeaveAdminView.vue`。
- **測試命令與實際輸出 (Verified Execution)**：
  - **後端單元與整合測試 (pytest)**：
    - `pytest apps/api/tests/test_leave_entitlement.py` -> **2 passed in 0.63s (台日特休年資階梯試算、假別增修、特休計算清冊與批次發放 API 100% 通過)**
    - `pytest apps/api/tests` -> **72 passed in 15.40s (全套 72 項後端測試 100% 通過)**
  - **前端單元測試與四語結構驗證 (vitest)**：
    - `npm test -- --run` -> **5 test files passed, 16 passed in 2.48s (i18n-completeness 100% 通過，四語鍵值零缺失)**
  - **前端靜態編譯與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 77 modules transformed, built in 2.48s (100% 通過)**
  - **無瀏覽器驗證原則**：
    - 恪遵使用者指令「不要啟動 browser 測試」，完全透過自動化測試套件與 TypeScript 編譯進行無頭檢驗。

#### 系統登入與重設密碼多重身分識別驗證優化 (Multi-Identifier Login & Password Reset Compatibility)

- **執行時間**：2026-10-23
- **問題回報與症狀 (Incident & Feedback)**：
  - 使用者在系統為員工重設密碼為 `Etron123` 後，於系統登入畫面輸入使用者帳號 `cswu` 與密碼 `Etron123`，系統出現紅色警告「⚠️ 帳號或密碼錯誤」，無法正常登入。
- **根本成因分析 (Root Cause Analysis)**：
  1. **身分代號 (Identifier) 不一致**：
     - 人事系統在員工報到開通帳號時，預設以**工號**做為 `User.username`（如工號 `207`）；而員工之公務信箱為 `cswu@etron.com.tw`。
     - 管理員在帳號管理中為該帳號重設密碼時，密碼雜湊已成功更新為 `Etron123`（Argon2id 驗證為真）。
     - 但在系統登入畫面中，使用者依照直覺輸入公務信箱前綴 `cswu`，而後端 `POST /api/v1/auth/login` 原先僅執行 `where(User.username == req.username)` 單一欄位等值查詢，無法以 Email 或 Email 前綴比對到該帳號，因而拋出 `401: 帳號或密碼錯誤`。
- **架構設計與修復處置 (Architectural Solutions & Actions)**：
  1. **後端多識別碼相容登入 (Multi-Identifier Login Query)**：
     - 修改 [apps/api/app/api/v1/auth.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/auth.py) 之 `login` 端點，透過 SQLAlchemy `or_` 同時比對：
       - 系統帳號 / 工號：`User.username == login_id`（如 `207`）
       - 完整公務信箱：`User.email == login_id`（如 `cswu@etron.com.tw`）
       - 公務信箱前綴：`User.email.ilike(f"{login_id}@%")`（如 `cswu`）
  2. **前端登入提示與多語系對齊 (Frontend Login UX & i18n Alignment)**：
     - 更新 [apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts) 在四國語系增加 `auth.usernamePlaceholder`；
     - 更新 [apps/web/src/components/auth/LoginModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/auth/LoginModal.vue)，輸入框 placeholder 動態提示：「帳號、工號或 Email (例如 cswu 或 207)」。
  3. **自動化測試擴充與回歸 (Automated Testing Expansion)**：
     - 在 [apps/api/tests/test_auth_rbac.py](file:///c:/Sources/EtronJF8/apps/api/tests/test_auth_rbac.py) 增加 `test_multi_identifier_login` 單元測試，全面驗證工號、完整信箱及信箱前綴登入。
- **實際測試驗證與命令輸出 (Verified Execution)**：
  - **後端專屬與全套回歸測試 (pytest)**：
    - `pytest apps/api/tests/test_auth_rbac.py` -> **6 passed in 2.38s (100% 通過)**
    - `pytest apps/api/tests` -> **73 passed in 16.65s (100% 通過)**
  - **實際帳號登入端點驗證 (Scratch Verification)**：
    - `POST /api/v1/auth/login` 輸入 `username: "cswu"`, `password: "Etron123"` -> **200 OK (登入成功)**
    - `POST /api/v1/auth/login` 輸入 `username: "cswu@etron.com.tw"`, `password: "Etron123"` -> **200 OK (登入成功)**
    - `POST /api/v1/auth/login` 輸入 `username: "207"`, `password: "Etron123"` -> **200 OK (登入成功)**
  - **前端單元測試與生產建置 (vitest & build)**：
    - `npm test -- --run` -> **5 test files passed, 16 passed in 2.65s (四語系鍵值 100% 對齊)**
    - `npm run build` -> **0 errors, 77 modules transformed, built in 2.52s**

#### 新進員工基本資料擴充 (Person Master Profile Enhancement)

- **執行時間**：2026-10-23
- **需求來源與目標 (Requirements & Objective)**：
  - 依據標準「新進員工基本資料」人事表單（包含身分識別、出生日期、性別、血型、婚姻、役別、持有駕照、交通工具、身高公分、體重公斤、市內聯絡電話、行動電話、電子郵件、聯絡地址、戶籍地址、緊急聯絡人姓名/關係/市話/行動電話，以及學歷背景清單與工作經歷清單）。
  - 將集團自然人個資主檔（`Person` Master Profile）與公司任職個資（`Employee`）進行深層解耦與資料結構擴充，使員工在跨公司任職或轉調時，個人生理、學歷與工作經歷生命資產得以完整保存與共用。
- **架構設計與實作處置 (Architectural Solutions & Actions)**：
  1. **資料模型與資料庫遷移 (Data Model & Alembic Migration)**：
     - 在 [apps/api/app/models/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/models/hr.py) 的 `Person` 模型擴充下列欄位：
       - 生理與生活資訊：`blood_type` (VARCHAR 8)、`military_service_status` (VARCHAR 32)、`driving_licenses` (VARCHAR 128)、`transportation_modes` (VARCHAR 128)、`height_cm` (NUMERIC 5,1)、`weight_kg` (NUMERIC 5,1)；
       - 通訊與緊急聯絡人：`contact_phone` (VARCHAR 32)、`emergency_contact_mobile` (VARCHAR 32)；
       - 動態歷程子表 (JSON Arrays)：`education_history`（學校名稱、科系、起訖年份、畢肄業狀態）、`work_experience`（服務單位、職稱、工作說明、年資）。
     - 產出結構化遷移腳本 [apps/api/alembic/versions/ad12e45f6a7b_expand_person_profile_fields.py](file:///c:/Sources/EtronJF8/apps/api/alembic/versions/ad12e45f6a7b_expand_person_profile_fields.py)，支援升級與復原機制，並成功執行 `alembic upgrade head`。
  2. **API 契約與端點整合 (API Contracts & Endpoints)**：
     - 更新 [apps/api/app/api/v1/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/hr.py)：
       - 擴充 `PersonResponse`、`PersonCreate`、`PersonUpdate` Pydantic Schemas，完整支援學經歷 JSON 清單驗證與序列化；
       - 完善 `build_person_response` 工具函式；
       - 強化 `GET /employees/{employee_id}` 端點，自動串聯自然人主檔之生理/交通/兵役資訊與學經歷記錄。
  3. **前端介面重構與全功能支援 (Frontend UI & UX)**：
     - 全面重構 [apps/web/src/components/hr/PersonModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/PersonModal.vue)：
       - 分割為「基本身分與生理資訊」、「通訊與地址」（提供一鍵「同聯絡地址」複製按鈕）、「緊急聯絡人」、「學歷背景」（可動態新增/刪除行）與「工作經歷」（可動態新增/刪除行）五大區塊；
     - 升級 [apps/web/src/components/hr/EmployeeDetailModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/EmployeeDetailModal.vue)：
       - 檢視員工個人詳情時，同步卡片化展示血型、役別、身高體重、駕照通勤、市內電話、緊急手機，並結構化條列學歷與工作經歷清單。
  4. **四國語系一致性對齊 (Multi-Language i18n Alignment)**：
     - 在 [apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts) 於 `zh-TW`、`ja-JP`、`en-US`、`zh-CN` 四語系完整補齊所有新增欄位標籤與按鈕翻譯，結構 100% 嚴格對稱。
- **測試命令與實際輸出 (Verified Execution)**：
  - **資料庫遷移**：`alembic upgrade head` -> **已遷移至 ad12e45f6a7b**
  - **後端單元與整合測試 (pytest)**：
    - `pytest apps/api/tests/test_hr_master.py` -> **5 passed in 1.47s (100% 通過)**
    - `pytest apps/api/tests` -> **73 passed in 17.12s (全套 73 項後端測試 100% 通過)**
  - **前端單元測試與四語結構驗證 (vitest)**：
    - `npm test -- --run` -> **5 test files passed, 16 passed in 2.92s (i18n-completeness 100% 通過)**
  - **前端靜態編譯與生產打包 (vue-tsc & vite build)**：
    - `npm run build` -> **0 errors, 77 modules transformed, built in 2.86s (100% 通過)**
  - **無瀏覽器驗證原則**：
    - 恪遵使用者指令「不要啟動 browser 測試」，完全透過自動化測試套件與 TypeScript 編譯進行無頭檢驗。

#### 組織部門層級多階層擴充 (Organization Level Expansion: 組、課、部、處、中心、總經理、執行長、董事長)

- **執行時間**：2026-10-24
- **需求來源與目標 (Requirements & Objective)**：
  - 配合企業多元組織階層管理需求，編輯組織部門（Organization Unit）時，組織層級（Organization Level）需涵蓋自基層至最高決策層之完整階層：組 (Team)、課 (Section)、部 (Department)、處 (Division)、中心 (Center)、總經理 (General Manager)、執行長 (Chief Executive Officer, CEO)、董事長 (Chairman)。
- **架構設計與實作處置 (Architectural Solutions & Actions)**：
  1. **資料模型與長度規範 (Data Model Specification)**：
     - [apps/api/app/models/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/models/hr.py) 之 `Organization.level` 定義為 `Column(String(20), nullable=False, default="DEPARTMENT")`，更新型別備註以涵蓋 `CHAIRMAN`、`CEO`、`GM`、`CENTER`、`DIVISION`、`DEPARTMENT`、`SECTION`、`TEAM` 八大組織層級。字元長度完全在 VARCHAR(20) 安全容量內，無需變更實體 Schema，維持無損相容性。
  2. **國際化多語系字典擴充 ([i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts))**：
     - 在 `zh-TW`、`ja-JP`、`en-US`、`zh-CN` 四大語系同步擴充 `hr.org.levels` 命名空間：
       - `team`：組 (Team) / 係・チーム (Team) / Team / 组 (Team)
       - `section`：課 (Section) / 課 (Section) / Section / 课 (Section)
       - `department`：部 (Department) / 部 (Department) / Department / 部 (Department)
       - `division`：處 (Division) / 統括部・本部 (Division) / Division / 处 (Division)
       - `center`：中心 (Center) / センター (Center) / Center / 中心 (Center)
       - `gm`：總經理 (General Manager) / 社長・総支配人 (General Manager) / General Manager / 总经理 (General Manager)
       - `ceo`：執行長 (CEO) / 最高経営責任者 (CEO) / Chief Executive Officer (CEO) / 首席执行官 (CEO)
       - `chairman`：董事長 (Chairman) / 取締役会長 (Chairman) / Chairman / 董事长 (Chairman)
     - 通過 `tests/i18n-completeness.test.ts` 深度自動化鍵值結構比對，四語 100% 嚴格一致。
  3. **前端組織階層視圖元件重構 ([OrgTree.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OrgTree.vue))**：
     - 下拉選單整合：於「新增/編輯組織部門」Modal 依序提供：組 (Team)、課 (Section)、部 (Department)、處 (Division)、中心 (Center)、總經理 (General Manager)、執行長 (CEO)、董事長 (Chairman)。
     - 卡片徽章多語格式化：新增 `formatLevel(level: string)` 輔助函式，卡片標籤由顯示原始常數值升級為精緻的多語層級文字，並相容歷史或別名（如 `GENERAL_MANAGER`）。
  4. **自動化測試擴充與回歸 (Automated Testing)**：
     - 後端測試 [apps/api/tests/test_hr_full_system.py](file:///c:/Sources/EtronJF8/apps/api/tests/test_hr_full_system.py)：新增更新層級至 `CENTER` 與最高層階層 `CHAIRMAN` 之驗證，9 項全系統人資測試全數通過。
     - 前端單元測試與構建：Vitest 16 項測試全部通過，Vue-tsc 及 Vite 生產打包 77 個模組編譯 0 警告錯誤。

#### 緊急聯絡人設定標籤重疊與字典鍵值異常修復 (Emergency Contact Form Labels & i18n Alignment Fix)

- **執行時間**：2026-10-24
- **問題根因分析 (Root Cause Analysis)**：
  - 在「建立/維護人員基本檔案」彈窗（[PersonModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/PersonModal.vue)）之「🚨 緊急聯絡人設定」區塊中，表單標籤誤用不存在之多語鍵名：`hr.employee.emergencyContactName`、`hr.employee.emergencyContactRelationship`、`hr.employee.emergencyContactPhone`。
  - 因鍵名缺失，前端多語引擎直接輸出原始字串（長度達 30~42 字元）；加上原四欄網格排版在寬度受限下未設置換行截斷，導致四個長英文字串橫向溢出並在畫面上重疊為 `hr.employee.emergencyContactNamehr.employee.emergencyContactRelationshiphr.employee.emergencyContactPhone緊急聯絡人行動電話`。
- **修復處置 (Solutions & Actions)**：
  1. **多語字典對齊與別名相容 ([i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts))**：
     - 在 `zh-TW`、`ja-JP`、`en-US`、`zh-CN` 四大語系同步補齊 `emergencyContactName`、`emergencyContactRelationship`、`emergencyContactPhone` 鍵值，與原既有 `emergencyContact`、`emergencyRelationship`、`emergencyPhone` 完美對齊。
  2. **視圖元件與防呆機制 ([PersonModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/PersonModal.vue))**：
     - 統一改用標準多語路徑，並全面加入預設繁中 Fallback 參數：
       - `t('hr.employee.emergencyContact', '緊急聯絡人姓名')`
       - `t('hr.employee.emergencyRelationship', '與聯絡人關係')`
       - `t('hr.employee.emergencyPhone', '聯絡電話 (市話)')`
       - `t('hr.persons.modal.emergencyMobile', '緊急聯絡人行動電話')`
     - 網格配置優化為響應式 `grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3`，徹底杜絕窄螢幕擠壓。
  3. **共用欄位元件強化 ([FormField.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/FormField.vue))**：
     - 在 `<label>` 類別中新增 `break-words`，防止任何長文字造成意外溢出。
  4. **驗證與回歸 (Verification)**：
     - `npm test`：16 passed（包含 `i18n-completeness.test.ts` 四語對稱檢查 100% 通過）。
     - `npm run build`：0 errors，77 modules transformed 構建成功。

#### 部門與所屬公司綁定完整整合 (Organization Unit & Company Binding Integration)

- **執行時間**：2026-10-24
- **需求來源與目標 (Requirements & Objective)**：
  - 解決組織部門（Organization Unit）於建立或編輯時未能在介面上明確指定、綁定與辨識「所屬公司 (Company)」之缺失。
  - 嚴格落實多法人跨國企業之資料隔離與組織上下級防呆規範，確保新增部門時可自由指定綁定公司，編輯時清楚標註不可跨公司移轉，上級組織選單依所選公司動態聯動過濾，且卡片與清單視圖完整顯示公司標籤。
- **架構設計與實作處置 (Architectural Solutions & Actions)**：
  1. **後端組織清單 API 彈性強化 ([hr.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/hr.py))**：
     - 將 `GET /api/v1/hr/organizations` 的 `company_id` 查詢參數調整為可選 `Optional[str] = Query(None)`。
     - 傳入特定公司時回傳該公司部門；留空時回傳集團全部組織架構，兼具多公司快速篩選與跨公司上下級動態檢核能力。
  2. **多語系國際化字典對齊 ([i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts))**：
     - 於 `zh-TW`、`ja-JP`、`en-US`、`zh-CN` 四大語系同步擴充 `hr.org` 命名空間：
       - `company`：所屬公司 (Company) / 所属法人・会社 (Company) / Company / 所属公司 (Company)
       - `selectCompany`：選擇所屬公司 / 所属会社を選択 / Select Company / 选择所属公司
       - `companyImmutable`：所屬公司（建立後不可任意跨公司異動） / 所属会社（作成後の変更は不可） / Belonging Company (Cannot be changed once created) / 所属公司（创建后不可任意跨公司变更）
       - `allCompanies`：全部公司部門 / すべての会社組織 / All Companies / 全部公司部门
     - 自動化鍵值結構比對 100% 通過。
  3. **組織架構視圖深層重構 ([OrgTree.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OrgTree.vue))**：
     - **彈窗建立綁定**：在「+ 新增組織部門」Modal 頂端新增「所屬公司 (Company) *」下拉選單（預設帶入當前檢視公司），使用者可直接切換指派至「台灣總部 (ETJ-TW)」或「福岡支社 (ETJ-JP)」。
     - **動態上級組織過濾 (Dynamic Parent Filtering)**：上級組織（Parent Org）候選清單改依據當前 Modal 所選的 `formCompanyId` 動態過濾，切換公司時自動重設上級部門，從前端杜絕跨公司閉環與資料錯位。
     - **編輯防呆標記**：在「編輯組織部門」Modal 中，所屬公司以唯讀鎖定徽章呈現，明確提示不可任意跨公司遷移。
     - **組織卡片公司標籤**：於每張部門卡片頂部清楚標示 `🏢 台灣總部 (ETJ-TW)` 或 `🏢 福岡支社 (ETJ-JP)`，並標記啟用狀態。
     - **視圖頂部公司快速切換器**：在組織階層標題區新增公司篩選選單，支援切換檢視特定公司或全部公司部門。
  4. **全套測試驗證 (Verification)**：
     - `pytest tests/test_hr_full_system.py`：9 passed in 4.98s。
     - `npm test`：5 test files, 16 passed in 3.05s。
     - `npm run build`：0 errors，77 modules transformed 構建成功。

#### 請假申請表單標準表格重構與登入者身分／部門／主管自動帶出 (Leave Application Form Redesign & Auto-Population)

- **執行時間**：2026-10-24
- **需求來源與目標 (Requirements & Objective)**：
  - 依照標準紙本與企業人資表性格局全面重構「請假申請表單 (Leave Application Form)」。
  - 解決填寫請假申請時繁瑣挑選申請人、缺乏部門與主管資訊之痛點；實作**申請人**、**申請部門**、**直屬主管**均依當前登入者帳號（`currentUser`）自動關聯帶出。
  - 將請假類型全面對齊標準假別選項陣列（特休假、補休假、公假、事假、病假、喪假、婚假、產假、陪產假、生理假、其他），整合即時工作時數試算、代理人選取、申請單號預覽與申請日期展示。
- **架構設計與實作處置 (Architectural Solutions & Actions)**：
  1. **認證身分中繼與組織關聯擴充 ([auth.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/auth.py) & [auth.ts](file:///c:/Sources/EtronJF8/apps/web/src/utils/auth.ts))**：
     - 後端 `/api/v1/auth/me` 端點於 `UserProfileResponse` 擴充 `employee_no`、`department_id`、`department_name`、`manager_id`、`manager_name`、`manager_no` 欄位。
     - 使用者登入後，系統自動透過關聯之員工檔案解析當前所屬部門名稱，並精確檢索目前有效之 `DIRECT`（直屬主管）主管關係鏈。
     - 前端 `UserProfile` 介面同步擴充對應屬性，作為全系統表單自動填寫之單一事實來源。
  2. **員工詳情端點強化 ([hr.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/hr.py))**：
     - 於 `GET /api/v1/hr/employees/{employee_id}` 回傳結構中補齊 `organization_name` 與 `department_name`，支援切換代理代填假單時即時動態查詢。
  3. **假別高可用性智能補齊 ([leave_service.py](file:///c:/Sources/EtronJF8/apps/api/app/core/leave_service.py))**：
     - 建立假別自動尋找容錯與動態補齊機制：若資料庫缺乏某個標準假別主檔（如生理假、陪產假），服務層自動以標準法規屬性（是否需證明、是否支薪）為該公司建立對應之 `LeaveType`，確保不阻斷任何請假申請流程。
  4. **請假表單視圖標準格式實作 ([LeaveManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/leave/LeaveManagementView.vue))**：
     - **表頭資訊**：右上角展示動態「申請單號 (`LV-YYYYMMDD-XXXX`)」與當日「申請日期 (`YYYY/MM/DD`)」。
     - **經典表格網格佈局 (Table Grid Border Layout)**：
       - `[申請人]`：依登入者自動帶出姓名與工號，標記「🔒 帳號自動帶出」。
       - `[申請部門]`：依登入者自動帶出所屬部門名稱，標記「🔒 自動帶出」。
       - `[代理人*]`：下拉選單選取工作代理人（自動過濾申請人自己）。
       - `[主管]`：依主管關係鏈自動關聯帶出直屬主管姓名與工號，標記「🔒 自動關聯」。
       - `[請假事由*]`：文字輸入框。
       - `[請假類型*]`：以單選方塊展示 11 大標準假別（特休、補休、公、事、病、喪、婚、產、陪產、生理、其他），選「其他」時展開專屬具體假別輸入框。
       - `[開始日期* / 結束日期*]`：本地日期時間選擇器。
       - `[請假時數*]`：即時串接工時試算引擎，精準扣除班別午休與國定非工作日，展示「X.X 小時 (折算 X 天 / X 分鐘)」。
       - `[備註]`：輸入額外交接或檢附證明說明。
  5. **全流程驗證與構建 (Verification)**：
     - `pytest tests/test_leave_vertical_slice.py`：5 passed in 1.32s。
     - `pytest tests/test_hr_full_system.py tests/test_leave_entitlement.py`：11 passed in 4.94s。
     - `npm test`：5 test files, 16 passed in 2.90s。
     - `npm run build`：0 errors，77 modules transformed 構建成功。

#### 假種設定最小計假單位與給薪方式選項重構 (Leave Type Minimum Unit & Salary Payment Mode Refinement)

- **執行時間**：2026-10-24
- **需求來源與目標 (Requirements & Objective)**：
  - 人事假別管理 (LeaveAdminView) 中「新增/編輯假種設定」Modal：
    1. 將原「計假單位 (Unit)」欄位改為「**最小計假單位 (Minimum Leave Unit)**」，下拉選單選項調整為：`0.5小時 (HALF_HOUR)`、`1小時 (ONE_HOUR)`、`1天 (ONE_DAY)`。
    2. 將原單一勾選方塊「全薪 (有給)」重構為單選選項組：`全薪 (FULL)`、`半薪 (HALF)`、`不給薪 (UNPAID)` 供人事管理員單選勾選。
- **架構設計與實作處置 (Architectural Solutions & Actions)**：
  1. **資料庫模型與平滑遷移 (Database Model & Alembic Migration)**：
     - 在 apps/api/app/models/hr.py 的 LeaveType 模型擴充 `paid_type = Column(String(10), default="FULL", nullable=False)`，支援 'FULL' (全薪)、'HALF' (半薪)、'UNPAID' (不給薪)。
     - 建立 Alembic 遷移腳本 b1e2d3c4a5f6_add_paid_type_to_leave_types.py，將既有資料庫平滑升級，並依據既有 is_paid 狀態自動轉換 paid_type（is_paid=False 轉為 'UNPAID'，其餘轉為 'FULL'）。
     - 執行 alembic upgrade head，成功套用遷移。
  2. **API 契約雙向相容設計 (hr.py)**：
     - LeaveTypeResponse：補齊 `paid_type: str = "FULL"`。
     - LeaveTypeCreate 與 LeaveTypeUpdate：新增 `paid_type: Optional[str]`。
     - 實作雙向連動：建立或更新假別時，若給定 paid_type，系統自動維持 `is_paid = (paid_type != "UNPAID")`，確保系統既有讀取 is_paid 布林值之業務邏輯 100% 向前向後相容。
  3. **四語字典 100% 對齊 (i18n.ts)**：
     - 於四大語系 (zh-TW, ja-JP, en-US, zh-CN) 完整同步新增 8 組鍵值：minUnit, unitHalfHour, unitOneHour, unitOneDay, salaryPayment, paidFull, paidHalf, paidNone。
     - 通過 `tests/i18n-completeness.test.ts` 自動化缺鍵檢查測試。
  4. **前端假別管理視圖改版 (LeaveAdminView.vue)**：
     - Modal 表單：
       - 計假單位改為「最小計假單位」，下拉選單選項為 `0.5小時`、`1小時`、`1天`（預設為 `0.5小時`）。
       - 給薪屬性改為視覺化選項組，提供「全薪」、「半薪」、「不給薪」供單選勾選。
       - 保留「強制檢附」核取方塊。
     - 假別清單表格：
       - 表頭調整為「最小計假單位」與「給薪方式」。
       - 最小計假單位支援 `HALF_HOUR`、`ONE_HOUR`、`ONE_DAY` 友善顯示，並相容舊有單位。
       - 給薪方式提供三態彩色徽章：全薪（翡翠綠）、半薪（天藍色）、不給薪（灰色）。
  5. **全流程自動化驗證成果 (Verification Summary)**：
     - 後端測試：`pytest tests/test_hr_master.py` 6/6 通過（含新增的 `test_leave_type_min_unit_and_paid_type`）。
     - 前端測試：`vitest run` 5 個測試檔、16 個測試 100% 通過（含 i18n 完整度測試）。
     - 前端構建：`npm run build` (vue-tsc + vite build) 0 錯誤構建成功。

#### 出差申請單標準表格重構與登入者／部門／主管自動帶出 (Business Travel Application Form Redesign & Auto-Population)

- **執行時間**：2026-10-24
- **需求來源與目標 (Requirements & Objective)**：
  - 依照標準紙本表格格局全面重構「出差申請單 (Business Travel Application Form)」。
  - 實作**申請人**、**員工編號**、**部門**、**主管**依當前登入者帳號（`currentUser`）自動關聯帶出，減少重複填寫負擔。
  - 完整支援截圖規格之 14 大核心業務欄位：出差事由、國內/國外地點、出差起訖時間與「共 X 天 Y 夜」即時試算、複選交通工具（公司車、高鐵/台鐵、客運、自駕、飛機、其他）、住宿需求與預計住宿、同行人員、拜訪對象/單位、預定工作內容、預期成果、工作代理人、預估費用（交通/住宿/膳雜/其他及即時合計）與備註。
- **架構設計與實作處置 (Architectural Solutions & Actions)**：
  1. **資料庫模型與 Alembic 遷移 (Database Model & Alembic Migration)**：
     - 在 [apps/api/app/models/travel.py](file:///c:/Sources/EtronJF8/apps/api/app/models/travel.py) 的 `TravelRequest` 模型擴充欄位：`region_type` (國內外)、`start_time` / `end_time` (起訖時分)、`estimated_nights` (夜數)、`transport_modes` (JSON 複選)、`transport_other`、`needs_accommodation`、`accommodation_plan`、`companions`、`visiting_target`、`planned_agenda`、`expected_results`、各項預估費用 (`estimated_transport_cost`, `estimated_accommodation_cost`, `estimated_daily_cost`, `estimated_other_cost`, `estimated_total_cost`) 與 `notes`。
     - 建立 Alembic 遷移腳本 [c2f3d4e5a6b7_expand_travel_request_fields.py](file:///c:/Sources/EtronJF8/apps/api/alembic/versions/c2f3d4e5a6b7_expand_travel_request_fields.py)，執行 `alembic upgrade head` 平滑擴充現有資料表。
  2. **後端服務層與 API 契約 ([travel_service.py](file:///c:/Sources/EtronJF8/apps/api/app/core/travel_service.py) & [travel.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/travel.py))**：
     - `create_travel_request` 與 `TravelRequestCreate` 支援接收全部標準出差欄位，相容保留既有差旅預支款申請與抵扣流程。
     - `get_travel_request_detail` 補齊詳情回傳欄位。
  3. **四語字典 100% 對齊 ([i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts))**：
     - 於四大語系 (`zh-TW`, `ja-JP`, `en-US`, `zh-CN`) 的 `travelView.form` 同步新增 40+ 組出差表單多語系鍵值。
     - 通過 `tests/i18n-completeness.test.ts` 自動化缺鍵檢查測試。
  4. **前端出差申請單經典格狀視圖實作 ([TravelManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/travel/TravelManagementView.vue))**：
     - **表頭資訊**：右上角展示動態「申請單號 (`TR-YYYYMMDD-XXXX`)」與「申請日期 (`YYYY/MM/DD`)」。
     - **標準格狀外框結構 (Table Grid Border Layout)**：
       - `[申請人]` / `[部門]`：依登入者帳號自動帶出姓名與部門名稱，標記「🔒 帳號自動帶出」。
       - `[員工編號]` / `[主管]`：依登入者與組織主管鏈自動帶出工號與主管姓名，標記「🔒 主管自動關聯」。
       - `[出差事由*]`：文字輸入框。
       - `[出差地點*]`：國內／國外單選，並填寫詳細地址。
       - `[出差期間*]`：本地日期時間選擇器，即時自動換算「共 X 天 Y 夜」。
       - `[交通方式*]`：複選核取方塊（公司車、高鐵/台鐵、客運、自駕、飛機、其他）。
       - `[住宿需求]`：需要／不需要單選，並可填寫預計住宿飯店說明。
       - `[同行人員]` / `[拜訪對象／單位]`：文字輸入。
       - `[預定工作內容]` / `[預期成果]`：多行規劃與成效輸入。
       - `[工作代理人*]`：下拉選單選取同公司員工（排除申請人自己）。
       - `[預估費用]`：交通費、住宿費、膳雜費、其他輸入框，前端即時自動加總合計金額。
       - `[備註]`：多行額外補充說明。
     - 支援「儲存草稿 (Save Draft)」與「確認送審 (Submit Application)」，銜接既有工作流程引擎。
  5. **全流程自動化驗證成果 (Verification Summary)**：
     - 後端測試：`pytest tests/test_travel_vertical_slice.py` 7/7 通過。
     - 前端測試：`vitest run` 5 個測試檔、16 個測試 100% 通過（含 i18n 完整度測試）。
     - 前端構建：`npm run build` (vue-tsc + vite build) 0 錯誤構建成功。

#### 營運儀表板多餘登入按鈕清理與全域導覽列單一入口整合 (Dashboard Redundant Login Button Removal & Shell Navigation Unification)

- **執行時間**：2026-10-24
- **問題回報與分析 (Problem & Root Cause)**：
  - 使用者回報營運儀表板 (Dashboard) 標題列 (PageHeader) 右側多出重複的「🔑 登入」按鈕，造成視覺紊亂。
  - 經查 [apps/web/src/App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue) 在 `PageHeader` 的 `#actions` slot 中配置了條件渲染 `v-if="!currentUser"` 之登入按鈕。但整個系統在頂層外框 [AppShell.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/AppShell.vue) 的右上角已有統一的身分驗證／登入／使用者個人資訊選單，內頁重複放置登入按鈕違反單一事實原則。
- **實作處置與架構調整 (Actions & Architectural Unification)**：
  1. 移除 [apps/web/src/App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue) 中 `PageHeader` 內的重複登入按鈕，保留儀表板專屬捷徑按鈕「🛡️ 帳號與權限」與「👥 進入人事系統」。
  2. 登入、登出與身分驗證對話框統一由全域導覽列 (`AppShell.vue`) 單一元件負責管理。
- **全流程驗證成果 (Verification Summary)**：
  - 前端單元測試：`npm test` (Vitest) 5 個測試檔、16 個測試 100% 通過。
  - 前端打包編譯：`npm run build` (`vue-tsc -b && vite build`) 0 錯誤構建通過。

#### 人員基本檔案庫彈窗多語系切換不完全修復與全面國際化 (Person Profile Modal i18n Completeness & Hardcoded Strings Elimination)

- **執行時間**：2026-10-24
- **問題回報與分析 (Problem & Root Cause)**：
  - 使用者回報於切換語系（如英文 en-US）時，「建立人員基本檔案 (Create Person Profile)」彈窗中，底部「取消」按鈕仍出現寫死之中文「取消」。
  - 經查 [apps/web/src/components/hr/PersonModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/PersonModal.vue)：
    1. 底部取消按鈕硬編碼為字串 `取消`，未透過 i18next 取得對應語系翻譯。
    2. 儲存中狀態硬編碼為 `儲存中...`。
    3. 血型選單硬編碼為 `A 型`、`B 型`、`O 型`、`AB 型`、`其他 / 未提供`。
    4. 各欄位輸入範例（placeholder，如 `例如 Lily Chen`、`例如 A123456789`、戶籍地址備註等）與刪除按鈕提示（`title="刪除此筆"`）均寫死中文。
- **實作處置與國際化重構 (Actions & Full i18n Refactoring)**：
  1. **四語字典擴充 (i18n.ts - zh-TW, ja-JP, en-US, zh-CN)**：
     - 在 `hr.persons.modal` 下同步擴充 32 組多語系鍵值，涵蓋 `cancel`、`saving`、血型選項（`bloodTypeA` ~ `bloodTypeOther`）、所有欄位範例 placeholder（`fullNamePlaceholder`、`nationalIdPlaceholder`、`permanentAddressPlaceholder` 等）與按鈕提示。
     - 四大語系鍵值 100% 結構對齊，全數通過 `tests/i18n-completeness.test.ts` 缺 Key 深度自動化審查。
  2. **視圖元件重構 ([PersonModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/PersonModal.vue) & [ShiftList.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/ShiftList.vue))**：
     - 將底部取消按鈕重構為 `{{ t('hr.persons.modal.cancel') }}`。
     - 儲存狀態重構為 `{{ isSaving ? t('hr.persons.modal.saving') : t('hr.persons.modal.save') }}`。
     - 血型與所有 placeholder 全面動態綁定 `:placeholder="t(...)"`。
     - 同步檢查班別設定彈窗 [ShiftList.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/ShiftList.vue)，將硬編碼取消按鈕替換為 `{{ t('hr.shifts.cancel') }}`。
- **全流程驗證成果 (Verification Summary)**：
  - 前端單元測試：`npm test` (Vitest) 5 個測試檔、16 個測試 100% 通過（含 i18n 完整度測試）。
  - 前端打包編譯：`npm run build` (`vue-tsc -b && vite build`) 0 錯誤構建通過。

#### 班別設定時區選擇支援與取消按鈕異常修復 (Shift Timezone Selection Support & Cancel Button Glitch Resolution)

- **執行時間**：2026-10-25
- **問題回報與分析 (Problem & Root Cause)**：
  1. **取消按鈕顯示異常 (Cancel Button Display Glitch)**：使用者回報在「新增／編輯班別設定 (Shift Configuration Modal)」對話框底部，取消按鈕文字顯示為 raw i18n key `hr.shifts.cancel`。經查多國語言定義檔 [apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts)，在 `hr.shifts` 命名空間下未配置 `cancel` 字典鍵值，導致 i18next 回退渲染鍵名。
  2. **要可以選擇時區 (Timezone Selection Support)**：依 [PROJECT-PLAN.md](file:///c:/Sources/EtronJF8/docs/PROJECT-PLAN.md) 規格，系統支援台北（`Asia/Taipei`, UTC+8）與東京（`Asia/Tokyo`, UTC+9）雙營運時區。班別工時（Shifts）應具備指派其所屬時區之能力，使跨國駐點、工廠或子公司班別能精確對齊當地工作時區。先前資料庫 `shifts` 資料表及前後端模型均未納入 `timezone` 欄位。
- **實作處置與架構調整 (Actions & Architectural Implementation)**：
  1. **資料庫遷移 (Database Migration - Alembic Revision `d3e4f5a6b7c8`)**：
     - 建立 [apps/api/alembic/versions/d3e4f5a6b7c8_add_timezone_to_shifts.py](file:///c:/Sources/EtronJF8/apps/api/alembic/versions/d3e4f5a6b7c8_add_timezone_to_shifts.py)。
     - 透過 `op.batch_alter_table` 為 `shifts` 資料表新增 `timezone VARCHAR(50)` 欄位（預設為 `'Asia/Taipei'`，`nullable=False`），提供完整的資料相容轉換（Data Migration）與回滾復原方案（`downgrade`）。
     - 執行 `python -m alembic upgrade head` 成功套用。
  2. **後端資料模型與 API 契約 (ORM Model & API Endpoints)**：
     - 在 [apps/api/app/models/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/models/hr.py) 的 `Shift` 模型加入 `timezone = Column(String(50), default="Asia/Taipei", nullable=False)`。
     - 在 [apps/api/app/api/v1/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/hr.py) 中更新 Pydantic Schemas：`ShiftCreate`（加入 `timezone: str = "Asia/Taipei"`）與 `ShiftUpdate`（加入 `timezone: Optional[str] = None`）。
     - 更新 `create_shift` 端點，加入 `db.refresh(shift)` 確保提交後物件屬性即時重新整理回傳；更新 `update_shift` 端點支援更新時區。
     - 在 [apps/api/tests/test_hr_full_system.py](file:///c:/Sources/EtronJF8/apps/api/tests/test_hr_full_system.py) 中擴充時區指派與異動之單元測試驗證。
  3. **四語字典擴充 (i18n.ts - zh-TW, ja-JP, en-US, zh-CN)**：
     - 於 [apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts) 之四大語系 `hr.shifts` 節點同步擴充 `cancel`、`timezone`、`tzTaipei` 與 `tzTokyo` 四組鍵值，嚴格達成結構 100% 對齊。
  4. **前端視圖與元件互動整合 (Frontend Vue Components)**：
     - [apps/web/src/components/hr/ShiftList.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/ShiftList.vue)：
       - `ShiftItem` 型別擴充 `timezone?: string`。
       - `props` 接收上層傳入之 `timezone?: string`。
       - 建立與編輯班別彈窗內加入「適用時區 (Timezone)」下拉選單，預設綁定當前畫面／公司時區。
       - 彈窗底部取消按鈕修正為通用動作鍵 `{{ t('actions.cancel') }}`。
       - 班別清單卡片右上角新增時區徽章（例如：`🌐 台北 (Asia/Taipei, UTC+8)` / `🌐 東京 (Asia/Tokyo, UTC+9)`）。
     - [apps/web/src/components/hr/HrManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/HrManagementView.vue)：將所屬時區傳入 `<ShiftList :companyId="props.companyId" :timezone="props.timezone" />`。
- **全流程驗證成果 (Verification Summary)**：
  - 後端測試：`pytest tests` 15 個測試檔、74 個測試 100% 通過（含時區設定整合測試）。
  - 前端單元測試：`npm test` 5 個測試檔、16 個測試 100% 通過（`i18n-completeness.test.ts` 零缺失）。
  - 前端靜態類型與構建：`npm run build` (`vue-tsc -b && vite build`) 0 錯誤構建成功。

#### 員工到職報到與異動作業班別選擇支援 (Employee Onboard & Transfer Shift Assignment Support)

- **執行時間**：2026-10-25
- **需求來源與目標 (Requirements & Objective)**：
  - 使用者需求：「辦理員工到職報到作業, 異動作業 都要可以選擇班別」。
  - 確保新進同仁於報到手續中可直接指派所屬工作班別（Default Shift），調動／異動作業時亦可變更所屬班別並完整留存異動歷程（Audit Trail）。
  - 在職員工清單與員工詳情中清晰展現所屬班別，前後端介面四語完整對齊。
- **架構分析與實作處置 (Architectural Analysis & Actions)**：
  1. **資料模型與核心能力盤點 (Data Model & Schema Verification)**：
     - 經檢驗 [apps/api/app/models/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/models/hr.py)，資料庫 `employees` 資料表早前已由遷移 `4a2e1d7f8c9b` 具備 `default_shift_id` 外鍵欄位（關聯至 `shifts.id`），且核心層之 `EmployeeOnboard` 與 `onboard_employee` 領域函式已支援 `default_shift_id` 寫入。因此本功能無需進行破壞性資料表結構異動，符合「規格優先、避免過度遷移」之準則。
  2. **後端 API 契約與異動歷程擴充 ([apps/api/app/api/v1/hr.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/hr.py))**：
     - 在 `TransferEmployeeRequest` Pydantic 請求模型中新增 `new_default_shift_id: Optional[str] = None`。
     - 在 `transfer_employee` API 端點中加入班別異動邏輯：
       - 校驗指定的 `new_default_shift_id` 是否存在且同屬該公司，確保資料完整性。
       - 若指定新班別且與現行班別不同，更新 `emp.default_shift_id = req.new_default_shift_id`。
       - 於調動歷程模型 `EmployeeChange.notes` 中保留班別異動備註（如 `變更班別: 舊班別 -> 新班別`），確保審計軌跡完整。
     - 在 [apps/api/tests/test_hr_full_system.py](file:///c:/Sources/EtronJF8/apps/api/tests/test_hr_full_system.py) 中擴充 `test_employee_transfer_and_version_increment` 整合測試，斷言到職報到時指派班別及調動異動時變更班別成功。
  3. **四語字典結構 100% 遞迴對齊 ([apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts))**：
     - 在 `zh-TW`、`ja-JP`、`en-US`、`zh-CN` 四大語系同步新增 6 組字典鍵值：
       - `hr.employee.defaultShift`（預設班別 / 既定シフト / Default Shift / 默认班次）
       - `hr.onboardModal.defaultShift`（預設工作班別）
       - `hr.onboardModal.noDefaultShift`（暫不指定班別）
       - `hr.transferModal.newShift`（調動工作班別）
       - `hr.transferModal.keepCurrentShift`（維持原工作班別）
       - `hr.transferModal.currentShift`（現職班別）
     - 執行 `npm test` 自動化審查，通過 `tests/i18n-completeness.test.ts` 零缺失檢驗。
  4. **前端視圖與對話框元件整合 (Vue 3.5 Components Integration)**：
     - **到職報到對話框 ([OnboardModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OnboardModal.vue))**：
       - 接收 `props.shifts` 班別清單。
       - 在職稱與職級下方新增「預設工作班別」下拉選單，預設綁定公司首個可用班別。
       - 提交報到時將 `default_shift_id: form.defaultShiftId || undefined` 隨 API 請求送出。
     - **調職／異動對話框 ([TransferModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/TransferModal.vue))**：
       - 接收 `props.shifts` 班別清單。
       - 在現行職務資訊卡片中加入「現職班別」提示標籤。
       - 在新部門與新職稱下方新增「調動工作班別」下拉選單，提供「維持原工作班別」選項與全部可用班別。
       - 提交異動時將 `new_default_shift_id: form.newShiftId || undefined` 隨調動請求送出。
     - **人事管理主視圖 ([HrManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/HrManagementView.vue))**：
       - 加入 `fetchShifts()` 於載入公司資料時同步取得該公司所有班別。
       - 將 `shifts` 傳遞至 `<OnboardModal :shifts="shifts" />` 與 `<TransferModal :shifts="shifts" />`。
       - 在在職員工資料表格中，於「部門與職務」欄位下增加「所屬班別」徽章（若未指定則顯示「未排班」）。
     - **員工詳情對話框 ([EmployeeDetailModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/EmployeeDetailModal.vue))**：
       - 在身分資訊卡片直屬主管右側加入「預設班別」展示區塊。
- **全流程驗證成果 (Verification Summary)**：
  - 後端測試：`pytest tests` 15 個測試檔、74 個測試 100% 通過。
  - 前端單元測試：`npm test` 5 個測試檔、16 個測試 100% 通過（含 i18n 完整度測試）。
  - 前端靜態類型與構建：`npm run build` (`vue-tsc -b && vite build`) 0 錯誤構建成功。

#### 班別清單操作按鈕國際化顯示異常修復 (Shift Card Action Buttons i18n Glitch Resolution)

- **執行時間**：2026-10-25
- **問題回報與根本原因分析 (Problem & Root Cause Analysis)**：
  1. **按鈕未翻譯顯示 Raw Key**：使用者回報班別管理卡片底部之「編輯」與「刪除」按鈕顯示異常，直接顯示原始鍵值 `actions.edit` 與 `actions.delete`。
  2. **根本原因**：
     - 在 [apps/web/src/locales/i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts) 之全域 `actions` 字典中，僅定義了 `search`, `reset`, `submit`, `save`, `approve`, `reject`, `return`, `cancel`, `saveDraft`, `export`, `retry`, `prevPage`, `nextPage`，遺漏了通用操作鍵 `edit`、`delete` 與 `close`。
     - 當前端元件調用 `t('actions.edit')` 與 `t('actions.delete')` 時，因四大語系均無此鍵，i18next 自動 Fallback 渲染出原始 Key 字串。
     - 同時檢查發現 [ShiftList.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/ShiftList.vue) 中存在部分寫死之繁體中文字串（如 `固定上班 (無彈性)`、`分鐘`、刪除確認提示 `確定要刪除班別 [${s.name}] 嗎？`），在切換日本語或英語時顯示不協調。
- **實作處置與多語系對齊 (Actions & Full i18n Realignment)**：
  1. **四語字典同步擴充 ([i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts))**：
     - 在 `zh-TW`、`ja-JP`、`en-US`、`zh-CN` 四大語系的 `actions` 物件同步補齊：
       - `edit`（編輯 / 編集 / Edit / 编辑）
       - `delete`（刪除 / 削除 / Delete / 删除）
       - `close`（關閉 / 閉じる / Close / 关闭）
     - 在四大語系的 `hr.shifts` 節點同步擴充 `minutesUnit`（分鐘 / 分 / mins / 分钟）。
     - 四語結構 100% 遞迴吻合，自動化測試 `i18n-completeness.test.ts` 零缺失通過。
  2. **視圖元件重構 ([ShiftList.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/ShiftList.vue))**：
     - `getFlexRange()` 函式改採 `t('hr.shifts.fixedSchedule')` 與 `t('hr.shifts.flexMinutes', { minutes: flex })`。
     - 標準工時展示之分鐘單位改為動態 `t('hr.shifts.minutesUnit')`。
     - 刪除確認對話框改採 `t('hr.shifts.deleteConfirm', { name: s.name })`。
     - 編輯與刪除按鈕對齊 `t('actions.edit')` 與 `t('actions.delete')`，在日語環境下精確呈現 `✏️ 編集` 與 `🗑️ 削除`，在繁中環境下精確呈現 `✏️ 編輯` 與 `🗑️ 刪除`。
- **全流程驗證成果 (Verification Summary)**：
  - 前端單元測試：`npm test` 5 個測試檔、16 個測試 100% 通過（`i18n-completeness.test.ts` 零缺失）。
  - 前端靜態類型與構建：`npm run build` (`vue-tsc -b && vite build`) 0 錯誤構建成功。
  - 後端測試回歸：`pytest tests` 74/74 通過。

#### 員工報到與調動對話框所屬部門下拉選單自主載入與容錯強化 (Onboard & Transfer Department Autonomous Loading & Resilience)

- **執行時間**：2026-10-25
- **問題回報與根本原因分析 (Problem & Root Cause Analysis)**：
  1. **選不到部門**：使用者回報在「辦理員工到職報到作業 (OnboardModal)」對話框中，「所屬部門」下拉選單點開僅顯示「請選擇派駐部門」，無任何組織部門選項可供選取。
  2. **根本原因**：
     - 在 [OnboardModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OnboardModal.vue) 與 [TransferModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/TransferModal.vue) 中，部門選項完全被動依賴父組件 [HrManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/HrManagementView.vue) 透過 props 傳入之 `organizations`。
     - 當使用者在「人員基本檔案庫 (PersonManagementView)」點擊「辦理報到」時，若父組件在載入時因非同步時序、快取或網路回傳延遲導致 `organizations` 為空，彈窗內部無任何自主請求或重新抓取機制，造成下拉選單陷入空狀態。
     - 此外，選單缺乏「載入中」狀態與「無部門提示」，使用者無法得知當前狀態是尚在請求或本公司尚未建檔。
- **實作處置與容錯強化 (Actions & Architectural Implementation)**：
  1. **對話框自主加載與父層 Fallback 機制 ([OnboardModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/OnboardModal.vue) & [TransferModal.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/TransferModal.vue))**：
     - 在 `OnboardModal` 內部增加 `localOrganizations` 與 `localShifts` 本地響應式狀態，以及計算屬性 `effectiveOrganizations` 與 `effectiveShifts`（若本地有抓取資料則優先採用，否則以 props 為 fallback）。
     - 新增 `loadOrganizations(companyId)` 與 `loadShifts(companyId)`，於彈窗開啟（`watch props.isOpen`）與公司切換（`watch props.companyId`）時，主動發送 `/api/v1/hr/organizations?company_id=${companyId}` 與 `/api/v1/hr/shifts?company_id=${companyId}` 請求該公司最新資料。
     - 若 `effectiveOrganizations` 載入成功且使用者尚未手動選擇，自動預選第一筆部門，提升使用者填寫體驗。
     - 在 `TransferModal` 同樣加入 `effectiveOrganizations` 與 `effectiveShifts`，在彈窗開啟時依員工所屬公司自主刷新部門與班別清單。
  2. **介面互動與友善提示改善**：
     - 部門下拉選單於請求期間展示「載入部門清單中...」並暫時禁用，避免空選單誤點。
     - 若該公司確實未建立部門，展示明確警語「⚠️ 本公司 ({{companyId}}) 尚無建立部門」，並提示「此公司尚未建立組織部門，請先至『組織與部門階層』建立部門」。
  3. **父元件生命週期強化 ([HrManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/HrManagementView.vue))**：
     - 在 `handleStartOnboard`、`openOnboardDirectly`、`openTransfer` 等開啟彈窗動作時，同步觸發 `refreshAll()`，主動預熱部門與班別資料。
     - 監聽 `props.companyId` 加上 `{ immediate: true }`，確保初次渲染即載入該公司組織。
  4. **四語字典結構對齊 ([i18n.ts](file:///c:/Sources/EtronJF8/apps/web/src/locales/i18n.ts))**：
     - 在 `zh-TW`、`ja-JP`、`en-US`、`zh-CN` 同步新增 `loadingDepts`、`noDeptsInCompany` 與 `noDeptsHint`，通過 `tests/i18n-completeness.test.ts` 自動化檢驗。
- **全流程驗證成果 (Verification Summary)**：
  - 前端單元測試：`npm test` 5 個測試檔、16 個測試 100% 通過。
  - 前端靜態類型與構建：`npm run build` (`vue-tsc -b && vite build`) 0 錯誤構建成功。
  - 後端測試：`pytest tests` 74/74 通過。





#### 營運儀表板關鍵字搜尋無效問題修復 (Dashboard Filter & Search Fix)

- **執行時間**：2026-10-25
- **問題回報與根本原因分析 (Problem & Root Cause Analysis)**：
  1. **查詢無效**：使用者回報在營運儀表板 (Dashboard) 頂端的搜尋框輸入關鍵字（例如「王大明」）並點擊「查詢」按鈕後，下方待辦/單據表格未進行任何過濾，依然顯示全部 4 筆紀錄。
  2. **根本原因**：
     - 在 [apps/web/src/App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue) 中，`<FilterBar :keywordPlaceholder="t('dashboard.searchPlaceholder')" />` 未監聽其拋出的 `@search` 與 `@reset` 自訂事件 (Custom Events)。
     - 元件層級缺少儲存查詢字串的響應式狀態 (Reactive State) `searchKeyword`，且 `<DataTable>` 的資料列綁定屬性 `:rows="sampleRows"` 直接綁定未經篩選的原始陣列。
     - 分頁組件屬性 `:currentPage="1"`、`:totalCount="sampleRows.length"` 亦為靜態綁定，未與即時過濾結果形成聯動。
- **實作處置與架構補強 (Actions & Architectural Implementation)**：
  1. **響應式搜尋與分頁狀態實作 ([App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue))**：
     - 新增 `searchKeyword` (搜尋關鍵字)、`currentPage` (當前頁碼)、`pageSize` (每頁筆數)。
     - 實作 `handleSearch(kw: string)` 與 `handleReset()` 處理函式；每次觸發查詢或重設時，重置頁碼至第 1 頁。
     - 建立計算屬性 `filteredRows`：
       - 若搜尋字串為空，回傳全部紀錄。
       - 比對範圍涵蓋單號 (`docNo`)、申請人 (`applicant`)、金額 (`amount`)、多語系單據類型標籤 (`dashboard.types.${row.typeKey}`) 與簽核狀態標籤 (`status.${row.status}`)，支援不分大小寫模糊搜尋。
     - 建立計算屬性 `paginatedRows`，依據目前頁碼與頁面大小進行切片 (`slice`)。
  2. **模板事件綁定與表格聯動 ([App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue))**：
     - `<FilterBar>` 完整綁定 `@search="handleSearch"` 與 `@reset="handleReset"`。
     - `<DataTable>` 綁定 `:rows="paginatedRows"`、`:totalCount="filteredRows.length"`、`:currentPage="currentPage"`、`:pageSize="pageSize"`，並監聽 `@page-change="(p) => currentPage = p"` 實現翻頁狀態響應。
  3. **自動化測試擴充 ([apps/web/tests/dashboard-filter.test.ts](file:///c:/Sources/EtronJF8/apps/web/tests/dashboard-filter.test.ts))**：
     - 新增 5 項單元測試，涵蓋 `FilterBar` 輸入觸發 `search` 與 `reset` 事件驗證、輸入姓名「王大明」精確過濾 1 筆、輸入工號「TW0102」過濾、輸入單號「LV」與「EX」過濾，以及空關鍵字/重設恢復全部 4 筆之完整測試案例。
- **全流程驗證成果 (Verification Summary)**：
  - 前端單元測試：`npm run test` 6 個測試檔、21 個測試 100% 通過（包含新增之 `dashboard-filter.test.ts`）。
  - 前端靜態類型檢查：`npm run typecheck` (`vue-tsc --noEmit`) 0 錯誤通過。

#### 帳號與權限分配角色權限設定失敗問題修復 (Assign User Roles & Company Scope Fix)

- **執行時間**：2026-10-25
- **問題回報與根本原因分析 (Problem & Root Cause Analysis)**：
  1. **指派角色設定失敗**：使用者回報在「帳號與權限」模組中，於帳號操作列點擊「分配角色權限 (🛡️ 按鈕)」開啟彈窗並勾選角色後，點擊「確定指派」操作失敗。
  2. **根本原因**：
     - **API 契約欄位不符 (API Contract Mismatch)**：
       - 前端 [UserManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/users/UserManagementView.vue) 在 `handleSaveUserRoles` 中發送的 Payload 為 `{ role_names: selectedUserRoles.value }`。
       - 但後端 [users.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/users.py) 的 `AssignRolesRequest` 將 `company_id` 與 `role_ids` 宣告為必填欄位 (Required Fields)，且未定義 `role_names`。
       - 當前端呼叫 `PUT /api/v1/users/{user_id}/roles` 時，FastAPI 的 Pydantic 驗證直接拋出 `422 Unprocessable Entity` 阻絕請求。
     - **UI 選取值與系統角色識別碼脫節 (Key Value Discrepancy)**：
       - 前端彈窗核取方塊的 `:value="r.name"` 綁定的是中文名稱（例如 `系統最高管理員`），而非角色代號（例如 `ADMIN`），造成勾選狀態比對與後端查詢無法對齊。
     - **缺少公司範圍切換 (Missing Company Scope Selection)**：
       - 角色指派未提供指派目標公司 (Company Scope) 選擇，導致無法為多公司架構下的帳號靈活指定生效組織。
- **實作處置與前後端架構強固 (Actions & Architectural Implementation)**：
  1. **後端 API 彈性相容與容錯解析 ([apps/api/app/api/v1/users.py](file:///c:/Sources/EtronJF8/apps/api/app/api/v1/users.py))**：
     - `AssignRolesRequest` 改造為相容模式：`company_id`、`role_ids` 與 `role_names` 均支援可選 (`Optional`)。
     - 在 `assign_user_roles` 處理常式中：
       - 自動推導生效公司：優先採用請求帶入之 `company_id`，未提供時自動 Fallback 至使用者主屬公司 `u.primary_company_id or "ETJ-TW"`。
       - 角色識別容錯：候選清單相容 `role_ids` 與 `role_names`，查詢角色時優先依 `Role.id` 檢索，未命中則依 `Role.name` 查詢，確保自訂與內建角色均能正確關聯。
       - 同步健全 `CreateUserRequest` 與 `UpdateUserRequest`，雙向相容 `primary_company_id` 與 `active_company_id`。
  2. **前端指派彈窗與狀態優化 ([apps/web/src/components/users/UserManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/users/UserManagementView.vue))**：
     - 新增 `roleAssignCompany` 響應式狀態，彈窗開啟時預設為該帳號主屬公司。
     - 於指派角色彈窗中增加「角色生效公司範圍 (Company Scope)」下拉選單，支援跨公司角色權限設定。
     - Checkbox 綁定改為 `:value="r.id"`，標籤展示為標準代號 `r.id` 與中文名稱 `(r.name)` 及內建標記。
     - 發送 Payload 同時提供 `company_id`、`role_ids` 與 `role_names`，確保跨版本相容。
  3. **自動化測試擴充與全量回歸**：
     - 後端測試 [apps/api/tests/test_auth_rbac.py](file:///c:/Sources/EtronJF8/apps/api/tests/test_auth_rbac.py)：新增 `test_assign_user_roles_payload_compatibility`，覆蓋標準模式與省略 company_id/傳入 role_names 等容錯模式。
- **全流程驗證成果 (Verification Summary)**：
  - 後端全量測試：`pytest tests` 75/75 100% 通過（含新增之角色指派相容性測試）。
  - 前端單元測試：`npm run test` 6 個測試檔、21 個測試 100% 通過。
  - 前端靜態類型檢查：`npm run typecheck` (`vue-tsc --noEmit`) 0 錯誤通過。

#### 角色無權限時關聯功能表動態隱藏機制實作 (RBAC Permissions & Dynamic Menu Visibility)

- **執行時間**：2026-10-25
- **問題回報與需求分析 (Problem & Requirement Analysis)**：
  1. **無權限功能表隱藏**：使用者反映在系統設定了角色與權限之後，當使用者帳號未具備某些模組或功能權限時，相關的功能表（包含外層側邊欄功能選單與內層模組 Tab 頁籤）不應該顯示在畫面上。
  2. **架構檢視**：
     - 在 [AppShell.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/AppShell.vue) 中，側邊欄導航按鈕原本全數靜態寫死無條件渲染，未登入或未獲授權的使用者依然看得到所有業務模組按鈕。
     - 在 [HrManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/HrManagementView.vue) 中，頂端 6 個 Tab（人員、員工、公司、組織、班別、假額帳本）亦無條件全開，未依據 `hr.employee.manage`、`hr.org.manage`、`hr.shift.manage`、`hr.ledger.manage` 進行條件渲染。
     - 在 [UserManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/users/UserManagementView.vue) 中，帳號管理與角色授權 Tab 亦缺乏個別權限過濾。
- **實作處置與多層級功能表權限聯動 (Actions & Hierarchical Implementation)**：
  1. **前端權限工具健全 ([apps/web/src/utils/auth.ts](file:///c:/Sources/EtronJF8/apps/web/src/utils/auth.ts))**：
     - 封裝並匯出 `hasPermission(code)`、`hasAnyPermission(codes)`、`hasAllPermissions(codes)` 與 `hasRole(role)`。
     - 最高管理員 `ADMIN` 角色自動具備全量授權；未登入狀態嚴格回傳 `false`；一般在職同仁精確比對當前有效之 `currentUser.permissions` 集合。
  2. **側邊欄導覽功能表動態過濾 ([AppShell.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/AppShell.vue))**：
     - 定義 `navItems` 映射清單，為各業務模組綁定對應之權限識別碼清單（例如 HR 模組綁定 4 項 `hr.*` 權限；請假綁定 `leave.*` 等）。
     - 建立計算屬性 `visibleNavItems`，若未登入僅開放首頁 Public 項目；登入後僅過濾並渲染使用者擁有任一權限之模組功能表。
  3. **人事模組子功能表頁籤過濾 ([HrManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/hr/HrManagementView.vue))**：
     - 依據 4 項標準人事權限進行精細 Tab 顯示控制：
       - `hr.employee.manage`：人員基本檔案庫 (`persons`)、在職員工與任職管理 (`employees`)。
       - `hr.org.manage`：組織與部門階層 (`organizations`)、公司基本資料 (`companies`)。
       - `hr.shift.manage`：班別工時與排班管理 (`shifts`)。
       - `hr.ledger.manage`：假額天數與帳本維護 (`leaveLedger`)。
     - 動態計算可用清單 `availableTabs`，若當前 `activeTab` 遭停用或未獲權限，自動修正跳轉至第一個可見 Tab；若完全無人事權限則顯示友善安全提示面板。
  4. **帳號與權限視圖子功能表過濾 ([UserManagementView.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/users/UserManagementView.vue))**：
     - 帳號名冊 Tab 需具備 `system.user.manage`；角色與授權矩陣 Tab 需具備 `system.role.manage`。
  5. **儀表板快捷捷徑按鈕過濾 ([App.vue](file:///c:/Sources/EtronJF8/apps/web/src/App.vue))**：
     - 儀表板頂端之快捷操作按鈕同步加上 `hasAnyPermission`，確保全站無授權功能一律不洩漏入口。
- **全流程驗證成果 (Verification Summary)**：
  - 前端單元測試 [apps/web/tests/nav-permissions.test.ts](file:///c:/Sources/EtronJF8/apps/web/tests/nav-permissions.test.ts)：
    - 驗證未登入時受保護功能表完全不顯示。
    - 驗證 `ADMIN` 角色具備無條件全功能存取權限。
    - 驗證僅獲指派部分人事權限時，未授權 Tab 完整隱藏。
    - 驗證完全無人事權限時側邊欄與子功能表全部隱藏。
  - 前端全量測試：`npm run test` 7 個測試檔、25 個測試 100% 通過。
  - 前端靜態類型檢查：`npm run typecheck` (`vue-tsc --noEmit`) 0 錯誤通過。
  - 後端全量測試：`pytest tests` 75/75 100% 通過。

#### 使用者角色指派 API 調用指南 (User Role Assignment API Usage Guide)

- **執行時間**：2026-10-25
- **端點規格 (Endpoint Specification)**：
  - **方法與路徑 (Method & URL)**：`PUT /api/v1/users/{user_id}/roles`
  - **安全性與身分驗證 (Security & Auth)**：
    - 採同源 Session Cookie 機制，需附帶登入取得之 Cookie (`session_token`)。
    - 需在 HTTP Header 攜帶 CSRF 驗證權杖：`X-CSRF-Token: <csrf_token>`。
    - 必須具備 `system.role.manage` 或 `ADMIN` 最高權限。
  - **請求本文 (Request Body - JSON)**：
    ```json
    {
      "company_id": "ETJ-TW",
      "role_ids": ["HR_ADMIN", "ADMIN"]
    }
    ```
  - **更新機制說明 (Replacement Semantic)**：
    - 此端點採公司範圍內的角色全量更新（Full Replacement）。若要在原有角色上疊加 `ADMIN`，清單需同時包含原角色（如 `HR_ADMIN`）與新增角色（`ADMIN`）。
    - 系統具備相容容錯機制：若未傳 `company_id`，自動 Fallback 為該使用者之 `primary_company_id`；欄位名稱同時支援 `role_ids` 與 `role_names`。

#### 使用者 test_admin 角色權限變更記錄 (User test_admin Role Privilege Assignment Log)

- **執行時間**：2026-10-25
- **目標帳號 (Target User)**：
  - **使用者帳號 (Username)**：`test_admin`
  - **使用者唯一識別碼 (User ID)**：`7aa9910c-f939-47cd-8f9c-ae2ff67da8a8`
  - **所屬公司 (Primary Company)**：`ETJ-TW` (台灣總部)
- **變更項目 (Change Details)**：
  - 為 `test_admin` 疊加最高管理員角色 (`ADMIN`)，同時保留其原有之人事管理員角色 (`HR_ADMIN`)。
  - 更新後角色清單：`['ADMIN', 'HR_ADMIN']`。
- **授權生效機制 (Privilege Enforcement Architecture)**：
  1. **資料庫關聯表 (Database Mapping)**：在 UserRole 資料表中建立 (user_id='7aa9910c-f939-47cd-8f9c-ae2ff67da8a8', role_id='ADMIN', company_id='ETJ-TW') 實體映射，並受 UserScope 公司存取範圍安全保護。
  2. **前端動態功能表解鎖 (Frontend Dynamic Navigation Unlock)**：在 [apps/web/src/stores/auth.ts](file:///c:/Sources/EtronJF8/apps/web/src/stores/auth.ts) 的 hasPermission 機制下，ADMIN 角色會自動放行所有權限校驗。側邊欄導覽列 [AppShell.vue](file:///c:/Sources/EtronJF8/apps/web/src/components/common/AppShell.vue) 與模組內部功能頁籤（如人事管理、帳號角色管理、各類簽核單據）將全面解鎖並完整顯示。
  3. **後端 API 伺服器端授權 (Backend Server-side Authorization)**：後端依據 RBAC 機制確認其具備 ADMIN 身分，全量開放全公司範圍之業務查詢、表單提交、核准駁回及系統參數設定端點。
- **驗證方式 (Verification)**：
  - 經由 ORM 檢索驗證 UserRole 表，確認角色陣列已正確寫入 ['ADMIN', 'HR_ADMIN']。
# EtronJF
