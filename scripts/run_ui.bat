@echo off
title AI Job Finder - Web Dashboard
echo ===================================================
echo     Avvio Dashboard Streamlit - AI Job Finder
echo ===================================================

cd /d "%~dp0\.."

REM Attiva il virtualenv se presente
if exist "venv\Scripts\activate.bat" (
    call "venv\Scripts\activate.bat"
)

echo Apertura della dashboard nel browser...
streamlit run src/ui/app.py

pause
