@echo off
setlocal enabledelayedexpansion
title AutoApplyJobs — 9-to-5 Background Runner

:: Ensure logs directory exists
if not exist "%~dp0logs" mkdir "%~dp0logs"

:: 1. Detect Python executable (prefer backend\venv where packages are installed)
set "PYTHON_EXE=python"
if exist "%~dp0backend\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0backend\venv\Scripts\python.exe"
) else if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
)

:: 2. Handle Silent Mode parameter (from run_9to5_silent.vbs)
if "%1"=="--silent" goto run_silent

:: -------------------------------------------------------------
:: Interactive Menu & Diagnostic Control Center
:: -------------------------------------------------------------
:menu
cls
echo ================================================================
echo        AutoApplyJobs v3.3 - 9-to-5 Workday Autonomous Runner
echo ================================================================
echo   Enforces business-hour job applications (09:00 - 17:00),
echo   inbound email & calendar sync, and mobile Telegram commands.
echo ================================================================
echo.
echo   [1] Start Silent 9-to-5 Runner (Completely Hidden, 0 Clutter)
echo   [2] Start Foreground Runner (Live Console Logs)
echo   [3] View Watchdog Status & Recent Logs
echo   [4] Stop Running Watchdog & Backend Instances
echo   [5] Exit
echo.
set /p "CHOICE=Select an option [1-5]: "

if "%CHOICE%"=="1" goto launch_vbs
if "%CHOICE%"=="2" goto run_foreground
if "%CHOICE%"=="3" goto view_logs
if "%CHOICE%"=="4" goto stop_instances
if "%CHOICE%"=="5" exit /b 0
goto menu

:launch_vbs
echo.
echo [*] Launching silent background watchdog via Windows Script Host...
cscript //nologo "%~dp0run_9to5_silent.vbs"
timeout /t 2 >nul
echo [OK] Background watchdog is active and logging to logs\9to5_daemon.log!
echo      You can safely close this window now.
pause
exit /b 0

:run_foreground
echo.
echo [*] Starting AutoApplyJobs in foreground (Press Ctrl+C to stop)...
cd /d "%~dp0backend"
set "HEADLESS=true"
set "SCHEDULER_ENABLED=true"
set "SCHEDULER_ENFORCE_BUSINESS_HOURS=true"
"%PYTHON_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
goto menu

:run_silent
:: Executed in hidden background by run_9to5_silent.vbs
cd /d "%~dp0backend"
set "HEADLESS=true"
set "SCHEDULER_ENABLED=true"
set "SCHEDULER_ENFORCE_BUSINESS_HOURS=true"
"%PYTHON_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 >> "%~dp0logs\9to5_daemon.log" 2>&1
exit /b 0

:view_logs
cls
echo ================================================================
echo               Recent 9-to-5 Watchdog Logs
echo ================================================================
if exist "%~dp0logs\9to5_daemon.log" (
    powershell -NoProfile -Command "Get-Content -Path '%~dp0logs\9to5_daemon.log' -Tail 30"
) else (
    echo No logs recorded yet. Start the watchdog first.
)
echo ================================================================
echo.
pause
goto menu

:stop_instances
echo.
echo [*] Terminating all running background uvicorn/python workers...
powershell -NoProfile -Command "Get-Process -Name python,uvicorn -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -like '*app.main:app*' } | Stop-Process -Force"
echo [OK] Stopped background instances.
pause
goto menu
