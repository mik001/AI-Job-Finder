@echo off
title Importa Cookie Indeed - AI Job Finder
echo ===================================================
echo     Importa Cookie da Browser - AI Job Finder
echo ===================================================
echo.

cd /d "%~dp0\.."

REM Attiva il virtualenv se presente
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

python scripts/import_cookies.py

echo.
pause
