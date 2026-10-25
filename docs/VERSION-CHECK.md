# T00 版本驗證操作（須在目標機實際執行）
以下命令僅供檢查，不代表已執行。python 應指向核定的專案解譯器。
```powershell
Set-Location C:\sources\EtronJF8
python --version
python -c "import sys,sqlite3; print(sys.executable); print(sqlite3.sqlite_version)"
python -m pip index versions fastapi
node --version
npm --version
npm view vue@3.5.44 version engines peerDependencies --json
npm view tailwindcss@4.3 version engines --json
npm view i18next@26.5.3 version engines --json
npm view i18next-vue version peerDependencies --json
```
Python 版本須另對照官方 release 與可用安裝包；FastAPI 需確認 0.156.8 實際存在及套件 Metadata。SQLAlchemy/Alembic/Pydantic 等需一起建立隔離環境 smoke test。不使用未知網站上的同名安裝包，不為滿足數字替換不明 sqlite DLL。
