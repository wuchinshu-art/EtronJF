
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

