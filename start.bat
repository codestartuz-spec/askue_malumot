@echo off
chcp 65001 >nul
cd /d "%~dp0backend"
if not exist .venv\Scripts\python.exe (
  echo Avval setup.bat ni ishga tushiring.
  pause & exit /b 1
)
start "ASKUE - Worker (yuklash navbati)" cmd /k ".venv\Scripts\python.exe -m app.worker"
start "ASKUE - Server" cmd /k ".venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2"
timeout /t 5 >nul
start http://localhost:8000
