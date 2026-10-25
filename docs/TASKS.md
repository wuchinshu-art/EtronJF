# 工作分解與依賴

|Task|內容|主要 skill|依賴|狀態|
|---|---|---|---|---|
|T00|版本與決策核定|project-bootstrap|無|已完成|
|T01|骨架、CI、DB連線|project-bootstrap|T00|已完成|
|T02|UI、四語、雙時區|ui-i18n-time|T01|已完成|
|T03|帳號及權限|auth-rbac|T01|已完成|
|T04|人事主檔及日曆|hr-master|T03|已完成|
|T05|簽核引擎|workflow-engine|T03,T04|已完成|
|T06|請假垂直切片|leave-overtime|T02,T04,T05|已完成|
|T07|加班|leave-overtime|T06|已完成|
|T08|出差及結報|travel-settlement|T06|已完成|
|T09|費用、供應商及請款|expense-payment|T06|已完成|
|T10|用印及合約|seal-contract|T06|已完成|
|T11|出勤匯入與查詢|attendance-import|T02,T04|已完成|
|T12|安全、UAT與發布|release-operations|T07,T08,T09,T10,T11|已完成|

每一個 task 再拆成 schema/API/UI/tests/review 子任務，各自可單輪完成。完成定義：規格核定、契約更新、migration 可重建、權限負向測試、四語 key、測試真實執行、文件更新、審查通過。T00 可產出核定阻擋項，但未核定不得聲稱整個 T00 已完成。

分工：架構負責人管理契約與 schema；後端負責 service/repository；前端負責共用元件與模組頁面；QA 負責邊界與E2E；DevOps負責部署／備份；HR、財會、法務分別核定業務規則。分支可平行，schema、lockfile、locale index 與 core 修改必須序列整合。
