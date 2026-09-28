@echo off
REM =========================================================================
REM AI JOB FINDER - Automated Daily Run Script
REM =========================================================================

cd /d "%~dp0\.."

set PYTHONPATH=.
set PYTHONIOENCODING=utf-8
set PYTHONUNBUFFERED=1

echo [*] Avvio esecuzione programmata AI Job Finder: %date% %time% >> data\scheduler.log

.\venv\Scripts\python.exe -u src\main.py >> data\scheduler.log 2>&1

echo [+] Esecuzione completata: %date% %time% >> data\scheduler.log
REM =========================================================================
