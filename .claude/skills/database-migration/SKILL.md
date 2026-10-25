---
name: database-migration
description: 管理 SQLite schema 與資料遷移；新增／修改資料表或索引時使用。
---

# 管理 SQLite schema 與資料遷移

## 輸入與範圍
先讀 AGENTS.md、docs/TASKS.md 中本任務及相關規格；只讀相關 references，不一次載入全部專案。跨模組需求先由 architecture-spec 更新契約。

## 執行流程
1. 列出規格與未核定決策、允許修改的檔案、相依 task。
2. SQLAlchemy/Alembic；每連線 foreign_keys；外鍵／唯一／索引；SQLite batch migration 先演練；先備份再變更，禁止直接改正式庫。
3. 先寫測試與失敗案例，再完成實作；共用能力不得複製。
4. 執行本任務測試、migration 驗證及四語／權限檢查。
5. 交由 test-review 或 security-audit 獨立審查。

## 必交付
migration、資料轉換驗證、備份／復原演練、金額型別與查詢計畫。

## 禁止事項
不連正式資料庫、不自行改版本或法規、不跳過權限、不抹除歷史、不將 mock 當成完成、不宣稱未執行的測試通過。新增依賴與破壞性 migration 先提出核准。

## 結案格式
規格對應；檔案清單；API／schema 改動；測試命令與實際結果；未完成事項；風險及下一任務。
