---
name: ui-i18n-time
description: 建立天藍 UI、四語及東京台北時區；修改介面、翻譯或日期元件時使用。
---

# 建立天藍 UI、四語及東京台北時區

## 輸入與範圍
先讀 AGENTS.md、docs/TASKS.md 中本任務及相關規格；只讀相關 references，不一次載入全部專案。跨模組需求先由 architecture-spec 更新契約。

## 執行流程
1. 列出規格與未核定決策、允許修改的檔案、相依 task。
2. 讀 docs/UI-I18N-TIME.md；共用 tokens；四語 namespace key；語言與時區獨立；驗證 UTC instant 及 date-only。
3. 先寫測試與失敗案例，再完成實作；共用能力不得複製。
4. 執行本任務測試、migration 驗證及四語／權限檢查。
5. 交由 test-review 或 security-audit 獨立審查。

## 必交付
四語截圖或驗收步驟、缺 key 檢查、日期轉換與可及性測試。

## 禁止事項
不連正式資料庫、不自行改版本或法規、不跳過權限、不抹除歷史、不將 mock 當成完成、不宣稱未執行的測試通過。新增依賴與破壞性 migration 先提出核准。

## 結案格式
規格對應；檔案清單；API／schema 改動；測試命令與實際結果；未完成事項；風險及下一任務。
