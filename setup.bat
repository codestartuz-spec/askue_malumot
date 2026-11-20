@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ===== ASKUE malumot: birinchi ornatish =====
rem Ofis tarmogi proksi orqali bolsa, quyidagi qatordagi "rem" ni olib tashlang:
rem set ASKUE_PROXY=http://192.168.0.1:3128
if defined ASKUE_PROXY (set HTTP_PROXY=%ASKUE_PROXY%& set HTTPS_PROXY=%ASKUE_PROXY%)

where python >nul 2>nul || (echo Python topilmadi. Python 3.10+ ornating. & pause & exit /b 1)
cd backend
if not exist .venv\Scripts\python.exe (
  echo [1/3] Virtual muhit yaratilmoqda...
  python -m venv .venv || (pause & exit /b 1)
)
echo [2/3] Python kutubxonalari ornatilmoqda...
.venv\Scripts\python.exe -m pip install --upgrade pip >nul
.venv\Scripts\python.exe -m pip install -r requirements.txt || (pause & exit /b 1)
.venv\Scripts\python.exe make_env.py
cd ..

where npm >nul 2>nul
if errorlevel 1 (
  echo [3/3] Node.js topilmadi - tayyor frontend (frontend\dist) ishlatiladi.
) else (
  echo [3/3] Frontend yigilmoqda...
  cd frontend
  call npm install --no-audit --no-fund && call npm run build
  cd ..
)
echo.
echo TAYYOR. Endi backend\.env faylidagi DATABASE_URL (MySQL paroli) ni tekshiring va start.bat ni ishga tushiring.
pause
