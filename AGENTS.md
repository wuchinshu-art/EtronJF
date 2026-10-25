# EtronJF8 Agent 開發規約
1. 專案根目錄 C:\sources\EtronJF8。先讀 docs/PROJECT-PLAN.md、docs/DECISIONS.md、docs/TASKS.md，再讀本任務 skill。不可一次載入全部 references。
2. 規格優先，未核定門檻／幣別／法規／版本不可自行決定。只能實作顯式標記的候選規則，正式啟用須核准。
3. 使用者指定 Python 3.14.8、FastAPI 0.156.8、SQLite 3.54.x、Tailwind 4.3.x、Vue 3.5.44、i18n 26.5.3；先驗證，不靜默替代。
4. 共用核心及 design tokens 是單一事實來源。模組不得重造登入、簽核、銀行加密或附件授權。
5. API 必須有伺服器端權限與 company scope。UI 隱藏不等於授權。
6. 金額不用浮點；事件 UTC，業務日期保留公司時區；四語 key 必須完整。
7. 每輪只執行一個 task；先提檔案異動計畫，不讀正式密鑰，不連正式 DB，不提交個資。
8. Schema 異動先寫 migration、資料轉換及復原方案；破壞性操作要人工核准。
9. 不宣稱未執行的指令／測試通過。不用 mock 取代正式授權驗收，不關閉測試以通過 CI。
10. 結案回報變更檔案、規格對應、migration、實際測試命令與輸出摘要、未完成項與風險。
11. 不同 Agent 不同時修改共享 schema、workflow core、API contract、locale index、lockfile；由整合負責人序列合併。
12. README/AGENTS 與技能中的示例不是已存在的程式，不得引用不存在的模組稱功能已完成。
