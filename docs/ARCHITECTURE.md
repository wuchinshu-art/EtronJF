
瀏覽器 → 同源 HTTPS 反向代理 → Vue 靜態資產與 /api/v1 FastAPI → Service → Repository → SQLite。
各功能模組放在 apps/api/app/modules 與 apps/web/src/modules，不建立沒有需求的微服務。共用核心包括認證、授權、流程、編號、附件、稽核、通知、匯入、多語系及時間服務。
API 使用 Router → Service → Repository，交易邊界由 service 控制；資料模型不得直接當公開 response。使用 SQLAlchemy 與 Alembic；SQLite schema 調整先測試 migration、備份及還原。
正式部署以單台應用主機及本機磁碟資料庫起步，不把 DB 放 SMB/NAS。WAL 允許讀寫併行但仍只有單一寫入者；需短交易、寫入排隊策略、busy timeout、寫入競爭壓測。每連線啟用 foreign_keys；採財務資料耐久性優先的 synchronous=FULL 基線，再實測調整。初期 API 單 worker，不把同步 SQLite 呼叫直接阻塞 async event loop。通知與匯入採持久化工作紀錄及單一工作消費者，不以單純 in-process BackgroundTasks 承諾可靠交付。
使用 SQLite online backup API 或受控停機備份，不能只複製使用中的主 DB 而忽略 WAL。附件及加密金鑰另行備份與權限隔離。建議 RPO 24 小時、RTO 4 小時，須由業務核定與演練。若跨主機多寫入、實測競爭無法滿足需求，再評估 PostgreSQL 遷移，不默默替換本期資料庫。




核心：users, sessions, roles, permissions, user_roles, role_permissions, user_scopes, password_reset_tokens。
人事：companies, organizations, employees, employment_assignments, manager_relations, employee_changes, shifts, shift_assignments, calendar_days, leave_types, leave_policies, leave_ledger。
簽核：workflow_definitions, workflow_versions, workflow_instances, workflow_nodes, approval_assignments, approval_actions, delegations, document_revisions。
申請：leave_requests, leave_segments, travel_requests, travel_settlements, travel_advances, expense_reports, expense_lines, payment_requests, payment_lines, overtime_requests。
主檔：suppliers, supplier_bank_accounts, supplier_bank_reviews, seals, seal_custody_history, seal_requests, contracts, contract_versions。
平台：attachments, document_attachments, audit_logs, outbox_events, notifications, number_sequences。
出勤：import_profiles, import_batches, import_rows, attendance_events, attendance_corrections, attendance_daily_summaries。
所有業務表有 company_id、建立／更新者與時間；需並行更新者有 version；索引依查詢與唯一規則設計。日期、時間、金額採明確型別及一致序列化。金額 API 用 decimal 字串，後端 Decimal；DB 採幣別最小單位整數，不用 float／SQLite REAL 存財務額。金額與 currency、scale、原幣、換算幣、匯率、匯率日期一併記錄。合約金額未定不可當成 0 跳過門檻。

