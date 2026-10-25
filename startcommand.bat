@echo off
REM ============================================================
REM ETJ EtronJF8 啟動指令腳本 (Startup Script)
REM ============================================================

echo [ETJ EtronJF8] 服務啟動說明：
echo.
echo 1. 啟動後端 API 伺服器 (FastAPI 0.156.8):
echo    cd C:\sources\EtronJF8\apps\api ^&^& python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
echo.
echo 2. 啟動前端開發伺服器 (Vue 3.5.44 + Tailwind 4):
echo    cd C:\sources\EtronJF8\apps\web ^&^& npm run dev
echo.
pause