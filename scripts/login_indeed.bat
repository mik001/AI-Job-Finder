@echo off
title Accesso Indeed - AI Job Finder
echo ===================================================
echo     Accesso Interattivo Indeed - AI Job Finder
echo ===================================================
echo.

cd /d "%~dp0\.."

REM Attiva il virtualenv se presente
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

python scripts/login_indeed_user.py

echo.
pause
