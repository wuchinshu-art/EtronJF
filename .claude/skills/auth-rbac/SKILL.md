---
name: auth-rbac
description: 實作帳號、工作階段與物件層權限；修改登入、停用、角色、公司範圍時使用。
---

# 實作帳號、工作階段與物件層權限

## 輸入與範圍
先讀 AGENTS.md、docs/TASKS.md 中本任務及相關規格；只讀相關 references，不一次載入全部專案。跨模組需求先由 architecture-spec 更新契約。

## 執行流程
1. 列出規格與未核定決策、允許修改的檔案、相依 task。
2. 依 server-side session、CSRF、Argon2id 規格；停用撤銷 session；API 檢查 role + scope + object。
3. 先寫測試與失敗案例，再完成實作；共用能力不得複製。
4. 執行本任務測試、migration 驗證及四語／權限檢查。
5. 交由 test-review 或 security-audit 獨立審查。

## 必交付
登入登出及停用測試、跨公司 IDOR 測試、敏感欄位權限測試。

## 禁止事項
不連正式資料庫、不自行改版本或法規、不跳過權限、不抹除歷史、不將 mock 當成完成、不宣稱未執行的測試通過。新增依賴與破壞性 migration 先提出核准。

## 結案格式
規格對應；檔案清單；API／schema 改動；測試命令與實際結果；未完成事項；風險及下一任務。
