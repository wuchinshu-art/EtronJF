# 開始使用
將本包解壓至 C:\sources\EtronJF8，使 AGENTS.md、docs 與 .claude 直接位於根目錄，不要多套一層目錄。
本包只包含計畫與技能，不包含應用程式或已執行的測試。
Claude Code 使用 .claude/skills/<name>/SKILL.md；其他 IDE 需確認技能載入方式，可手動指定讀取同一份規格，不能假設所有 IDE 都自動讀 .claude。

## 第一輪 Agent 提示
以 C:\sources\EtronJF8 為根目錄。先讀 AGENTS.md、docs/PROJECT-PLAN.md、docs/DECISIONS.md、docs/TASKS.md。
本輪只做 T00，使用 project-bootstrap skill 及 docs/VERSION-CHECK.md。
驗證指定技術版本與 i18n 套件身分，列出相容性證據、安裝來源及待核定決策。不得自動替換版本，不產生整套應用程式，不連正式 DB。
回報實際命令及結果、未驗證項目、建議鎖定清單與阻擋事項。取得版本與業務規則核准後才開始 T01。

## 後續單任務提示範本
本輪執行 [TASK-ID]，使用 [SKILL]；先列規格、相依、預計變更檔案與驗收。只完成本任務，不重構無關模組。新增 schema 先提 migration，完成後列真實測試結果與風險。
