# ETJ 鈺創-福岡資訊管理系統｜專案計畫書

## 1. 專案定位
- 專案根目錄：C:\sources\EtronJF8。
- 系統代號：EtronJF8；顯示名稱：ETJ 鈺創-福岡資訊管理系統。
- 採模組化單體、前後端分離、共用簽核引擎、規格驅動開發。
- 本文件是設計基線，不代表應用程式已建立、依賴版本已驗證或任何測試已通過。
- 首期涵蓋帳號、人事、請假、出差暨請款、費用報支、供應商請款、用印、合約、加班、出勤十項功能。
- 不包含薪資計算、總帳入帳、自動銀行匯款、法定申報或電子簽章法律效力認證；日後另案擴充。

## 2. 技術基線與版本閘門
|項目|使用者指定目標|實施要求|
|---|---|---|
|Python|3.14.8|以官方發行與本機環境驗證，不擅自降版|
|FastAPI|0.156.8|查套件來源、Requires-Python 與相依相容性|
|SQLite runtime|3.54.x|查 Python sqlite3.sqlite_version，不能只查 sqlite3 CLI|
|Tailwind CSS|4.3.x|先核定精確 patch 與建置整合版本|
|Vue|3.5.44|查 npm 套件版本與同儕依賴|
|i18n|26.5.3|待核定是否指 i18next；不是直接假設為 vue-i18n|

其餘 SQLAlchemy、Alembic、Pydantic、Node.js、Vite、TypeScript、Pinia、Vue Router、i18next-vue、pytest、Vitest、Playwright 由 T00 驗證後鎖定。前端只選一套主要翻譯引擎；若核定 i18next 26.5.3，另驗證 Vue adapter 版本。套件未存在或不相容時提交決策，不可宣稱安裝成功。正式使用 lockfile 及固定環境重建。

## 3. 架構與部署
瀏覽器 → 同源 HTTPS 反向代理 → Vue 靜態資產與 /api/v1 FastAPI → Service → Repository → SQLite。
各功能模組放在 apps/api/app/modules 與 apps/web/src/modules，不建立沒有需求的微服務。共用核心包括認證、授權、流程、編號、附件、稽核、通知、匯入、多語系及時間服務。
API 使用 Router → Service → Repository，交易邊界由 service 控制；資料模型不得直接當公開 response。使用 SQLAlchemy 與 Alembic；SQLite schema 調整先測試 migration、備份及還原。
正式部署以單台應用主機及本機磁碟資料庫起步，不把 DB 放 SMB/NAS。WAL 允許讀寫併行但仍只有單一寫入者；需短交易、寫入排隊策略、busy timeout、寫入競爭壓測。每連線啟用 foreign_keys；採財務資料耐久性優先的 synchronous=FULL 基線，再實測調整。初期 API 單 worker，不把同步 SQLite 呼叫直接阻塞 async event loop。通知與匯入採持久化工作紀錄及單一工作消費者，不以單純 in-process BackgroundTasks 承諾可靠交付。
使用 SQLite online backup API 或受控停機備份，不能只複製使用中的主 DB 而忽略 WAL。附件及加密金鑰另行備份與權限隔離。建議 RPO 24 小時、RTO 4 小時，須由業務核定與演練。若跨主機多寫入、實測競爭無法滿足需求，再評估 PostgreSQL 遷移，不默默替換本期資料庫。

## 4. UI/UX
- 天藍主色 #0284C7、hover #0369A1、淡背景 #F0F9FF、卡片 #FFFFFF、正文 #0F172A、邊框 #E2E8F0。
- #87CEEB 僅作淡色裝飾，不預設用白字搭配；所有文字／狀態／焦點色需驗證對比。
- 桌面：左側模組導覽、頂端公司/語言/時區、待辦入口；內容提供標題、篩選、表格與分頁。
- 手機：收合選單、單欄表單、簽核按鈕固定可見；桌面長表格可水平捲動。
- 共用元件：AppShell、PageHeader、DataTable、FilterBar、FormField、MoneyInput、DateTimeInput、AttachmentUploader、ApprovalTimeline、StatusBadge、PermissionButton、EmptyState、ErrorPanel。
- 每個畫面需處理 loading、empty、error、forbidden、validation、unsaved-changes，不能只有成功示意。
- 元件狀態、間距、圓角、字級以 design tokens 集中管理；不得各模組另造視覺風格。

## 5. 多語系與時間
- 語系：zh-TW、ja-JP、en-US、zh-CN。預設 zh-TW；回退策略明定，CI 檢查四語 key 完整。
- key 例 leave.form.startAt、workflow.status.approved、errors.approvalConflict。後端回傳穩定 error code，前端翻譯；不得把使用者輸入的姓名、地址、合約原文自動翻譯。
- 公司與組織名稱可用 translations JSON 或獨立翻譯表，保留法定原文及可選顯示翻譯。
- 時區使用 Asia/Tokyo 與 Asia/Taipei，與語言獨立設定。個人設定優先於公司預設。
- 事件時間以 UTC ISO-8601 儲存；輸入端帶 offset/IANA zone，回傳 UTC，顯示時再轉換。
- 工作日曆、到職日、假別年度為 date-only；排班為公司時區的 local date/time 與 zone，不把純日期強制轉 UTC。
- 出勤保留來源原文、來源時區、UTC instant、公司工作日期；無來源時區時由匯入設定提供，不能由瀏覽器時區猜測。
- 簽核門檻使用公司業務規則，不因使用者切換顯示時區而改變。

## 6. 功能範圍
### 6.1 帳號權限
登入、登出、首次設定密碼、修改／重設密碼、新增／停用帳號、角色與權限設定、工作階段查詢及撤銷。帳號與員工分離，允許員工尚未開通帳號。停用保留歷史紀錄，立即撤銷 session，處理待辦轉派，停用者不可再簽核。
權限採 RBAC + 公司／組織／本人資料範圍 + 物件層級授權。權限碼例 leave.create、leave.read.own、leave.approve.assigned、hr.employee.manage、payment.bank_account.view、attendance.import。平台管理員不當然可讀銀行與人事敏感資料。
### 6.2 人事
公司（時區、幣別、窗口）、組織階層、主管關係、員工編號與基本資料、到職報到、調職／升遷／離職、班別、工作日曆、假別、年度給假、結轉、失效、調整。
組織與任職關係有生效起訖；禁止階層循環。假額採 ledger，含給予、預占、核准扣抵、釋放、沖銷，不僅存可修改餘額。報到可連動帳號建立但須有授權。敏感欄位讀取留痕。
### 6.3 請假
假別、起訖、工作日曆、排班分鐘數、附件、代理人、餘額與重疊檢查。先計算實際請假工作分鐘，再依核定的每工作日分鐘換算簽核天數；不能預設全公司一律 8 小時。已核准撤銷需專用流程及 ledger 沖銷。
### 6.4 出差暨請款
出差計畫、目的地、跨日區間、預估費用、預支申請。出差申請及出差結報為兩種單據，以 travel_request_id 關聯，結報記錄實際費用、預支抵扣、應補／應退，避免重複報支。同筆預支有狀態與沖銷 ledger。實際付款由會計處理紀錄，非簽核自動匯款。
### 6.5 費用報支
員工一般費用、品項、日期、幣別、稅額、發票／收據、成本中心與附件；與出差結報及供應商請款區別。建立可能重複憑證警示，不能單用發票號碼做全公司絕對唯一。
### 6.6 請款申請
供應商代碼、名稱、國別、地址、付款條件、聯絡資料、啟停用、銀行國別／銀行／分行／戶名／帳號／幣別／SWIFT 等條件式欄位。銀行資訊限權、遮罩、加密與異動雙人覆核。單據保存送簽時供應商及銀行快照，主檔更新不得偷偷改變已核准付款資料。
### 6.7 用印
印鑑清冊：名稱、類型、所屬公司、保管人、生效／失效、交接紀錄；新增、失效、更換保管人均留痕。申請保存文件版本、用途、份數、附件。簽核核准不等於已用印，保管人執行後記錄日期、份數、實際執行者與完成文件。
### 6.8 合約
對象、標題、類型、金額／幣別、期限、責任部門、法務意見、附件版本及是否需要用印。法務後進保管人節點（有用印時），用印執行作業可關聯 seal_request，避免重新走一條重複核准流程。最終簽署文件、到期提醒及續約關聯獨立保存。
### 6.9 加班
工作日期、起訖、休息時間、理由、預估分鐘、加班費／補休意向。不得把申請時數直接當出勤時數或薪資結果；可與出勤比對。法規與公司政策由 HR／法務另核定。
### 6.10 出勤
支援 xlsx、CSV、文字分隔檔；舊式 xls 若需要須另核定解析套件。流程為上傳→解析→欄位映射→來源時區與格式設定→預覽→驗證→確認入庫→錯誤報告。文字支援明確指定 UTF-8／UTF-8 BOM／CP950／Shift_JIS，不靜默用猜測結果入庫。
支援多次打卡，不只兩欄上下班；原始事件不可覆寫，修正有獨立紀錄。查詢公司、員工、日期範圍、部門、來源與異常。批次有 hash、狀態、成功／失敗數、逐列錯誤及可重跑識別；事件去重優先設備事件 ID，否則使用經核定自然鍵與 row hash。跨夜班的工作日期依排班歸屬，而不是直接取 UTC 日期。

## 7. 簽核規則
申請者送出是動作，不是待簽節點。以下保留使用者原始需求，門檻未明定者見 DECISIONS。
|流程|送出後路徑|
|---|---|
|請假|代理人→直屬主管→第二層主管（3天以上）→第三層主管（10天以上）→人事窗口|
|出差|代理人→直屬主管→會計窗口（有預支）→人事窗口|
|出差請款／結報|直屬主管→會計窗口|
|費用報支|直屬主管→第二層主管（5000以上）→第三層主管（100000）→會計窗口|
|請款申請|直屬主管→部級主管（5000以上）→處級主管（100000）→總經理（500000）→會計窗口|
|用印|直屬主管→印鑑保管人|
|合約|直屬主管→第二層主管（5000以上）→第三層主管（100000）→法務窗口→印鑑保管人（需要用印）|
|加班|直屬主管→人事窗口|

- 送出時產生規則版本、組織、主管鏈、金額／匯率及節點快照；異動主檔不重寫既有流程。
- 第二／第三層主管是主管鏈；部級／處級主管是依組織層級解析的角色，兩者不可混為一談。
- 假單上的代理人與簽核者的職務代理分開建模，不得自動互代。
- 未找到主管、窗口、保管人或有效代理時阻止送出並顯示可修正訊息；不得自動放行。
- 自簽、同人多節點、主管缺席、窗口多人由核定政策處理；預設不自簽、不去重、不自動跳關。
- 系統管理員可依限權人工轉派，但須原因、原受派人、前後值與稽核；不回寫原始快照。
- 狀態：draft→submitted→in_review→approved/rejected/returned/cancelled；returned 編輯後重新送出建立新 revision，舊歷程保留。
- 簽核完成、核銷完成、付款完成、用印完成為不同狀態，不以一個 approved 全部代表。
- 每次簽核原子執行：檢查操作者／assignment／版本→寫決策→推進節點→寫稽核及 outbox→commit。
- 使用 revision/version 與唯一性約束防重複提交、重複核決與餘額超用；交易失敗不留下半完成通知。

## 8. 資料模型基線
核心：users, sessions, roles, permissions, user_roles, role_permissions, user_scopes, password_reset_tokens。
人事：companies, organizations, employees, employment_assignments, manager_relations, employee_changes, shifts, shift_assignments, calendar_days, leave_types, leave_policies, leave_ledger。
簽核：workflow_definitions, workflow_versions, workflow_instances, workflow_nodes, approval_assignments, approval_actions, delegations, document_revisions。
申請：leave_requests, leave_segments, travel_requests, travel_settlements, travel_advances, expense_reports, expense_lines, payment_requests, payment_lines, overtime_requests。
主檔：suppliers, supplier_bank_accounts, supplier_bank_reviews, seals, seal_custody_history, seal_requests, contracts, contract_versions。
平台：attachments, document_attachments, audit_logs, outbox_events, notifications, number_sequences。
出勤：import_profiles, import_batches, import_rows, attendance_events, attendance_corrections, attendance_daily_summaries。
所有業務表有 company_id、建立／更新者與時間；需並行更新者有 version；索引依查詢與唯一規則設計。日期、時間、金額採明確型別及一致序列化。金額 API 用 decimal 字串，後端 Decimal；DB 採幣別最小單位整數，不用 float／SQLite REAL 存財務額。金額與 currency、scale、原幣、換算幣、匯率、匯率日期一併記錄。合約金額未定不可當成 0 跳過門檻。

## 9. API 基線
/api/v1/auth/login, logout, me, change-password, password-reset/*
/api/v1/users, roles, permissions, companies, organizations, employees
/api/v1/hr/shifts, calendars, leave-types, leave-ledger
/api/v1/leave-requests, travel-requests, travel-settlements, expense-reports
/api/v1/suppliers, payment-requests, seals, seal-requests, contracts, overtime-requests
/api/v1/workflows/inbox, instances/{id}, assignments/{id}/actions
/api/v1/attendance/imports, imports/{id}/preview, imports/{id}/commit, events
/api/v1/attachments, notifications, audit-logs
寫入接口遵循 CSRF、認證、物件層授權、version/Idempotency-Key 契約；列表有分頁、排序白名單、公司範圍及上限；匯出也須同樣授權。response 統一 error.code、field_errors、request_id，禁止洩漏 traceback／密碼／銀行原文。

## 10. 安全與個資
預設同源部署，使用高熵 opaque server-side session 與 HttpOnly/Secure/SameSite cookie；登入旋轉 session，閒置／絕對到期、登出及停用可撤銷。CSRF token 及 Origin 檢查保護寫操作，登入限速，密碼使用經維護的 Argon2id 實作，重設 token hash 儲存、限時一次性。不得把密碼或 bearer token 放 localStorage。
附件在 web root 外，以隨機 storage key 儲存、大小／類型／檔頭驗證、隔離掃描、下載重新驗權；未授權不得用猜 ID 下載。銀行欄位以可信加密庫加密，密鑰不進 Git 或 DB，採權限隔離、輪替與備援。
稽核記錄 actor、有效代理人、company、action、object、before/after（遮罩）、reason、request_id、UTC。應用只追加，另輸出至隔離儲存以降低主機管理者篡改風險；不得宣稱本地 SQLite 可絕對不可竄改。保存期限、跨境個資與台日勞動規則需由公司核定。

## 11. 測試與驗收
- pytest：簽核解析、授權、狀態機、交易、假額、匯率與日期計算；Vitest：共用元件與 i18n；Playwright：關鍵端對端。
- 所有條件驗證門檻下、等於、上；金額至少 4999/5000/5001、99999/100000/100001、499999/500000/500001，使用相同核定幣別及最小單位。
- 請假測 3天及10天的前一工作分鐘／等值／後一工作分鐘、不同班別、假日、跨年、半天與跨午夜。
- 權限測跨公司 IDOR、非本人／非受派人簽核、停用 session、轉派、重複點擊與同時簽核。
- 出勤測同檔重匯、不同檔重複事件、錯誤編碼、缺欄、重複列、未知員工、跨夜、多次打卡、部分失敗及回復。
- 四語缺 key CI 檢查；兩時區同 instant 不同顯示；姓名和地址原文不被翻譯。
- 會計／HR UAT：原始憑證、流程快照、核准後主檔異動、金額與假額一致性。
- 效能數字先核定資料量、並行人數與硬體，再形成門檻；不可無壓測宣稱支援上千人。
- 正式上線需版本核定、資安審查、備份還原演練、全流程 UAT、操作手冊、回復方案及責任人簽認。

## 12. 專案工作與交付
T00 版本／規則／部署容量核定 → T01 骨架與 CI → T02 UI 四語雙時區 → T03 帳號權限 → T04 人事 → T05 簽核核心 → T06 請假垂直切片 → T07 加班 → T08 出差結報 → T09 費用／供應商請款 → T10 用印／合約 → T11 出勤 → T12 硬化、UAT、部署。
初估 2 位全端工程師、兼任 QA／DevOps，加 HR／財會／法務窗口協作為 12–18 週，僅供排程起點，T00 後重估，不是交付承諾。
每一任務有輸入規格、允許修改範圍、migration、API契約、測試、四語 keys、操作說明與完成證據。先完成一條請假流程，再平行複用。

## 13. 公開參考資料
- SQLite WAL：https://www.sqlite.org/wal.html
- Claude Code Skills：https://code.claude.com/docs/zh-TW/skills
- i18next 套件識別：https://www.npmjs.com/package/i18next
套件是否可安裝及版本互相相容仍以 T00 的實際結果為準。
