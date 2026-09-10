@echo off
setlocal
title AutoApplyJobs — All Services Launcher

echo ==========================================================
echo       AutoApplyJobs — Launching Full-Stack Services
echo ==========================================================

:: 1. Check AI service (Ollama or Cloud Gemini)
where ollama >nul 2>nul
if "%ERRORLEVEL%"=="0" (
    tasklist /fi "imagename eq ollama.exe" 2>NUL | find /i "ollama.exe" >NUL
    if "%ERRORLEVEL%"=="0" (
        echo [AI] Ollama service is running.
    ) else (
        echo [AI] Starting local Ollama service in background...
        start "Ollama Service" /min cmd /c "ollama serve"
    )
) else (
    echo [AI] Using Cloud Gemini API / Profile Question Answering.
)

:: 2. Python environment detection
set "PYTHON_EXE=python"
if exist "%~dp0backend\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0backend\venv\Scripts\python.exe"
)

echo.
echo [BACKEND] Starting FastAPI on http://localhost:8000 ...
start "AutoApplyJobs Backend" cmd /k "cd /d "%~dp0backend" && "%PYTHON_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo.
echo [FRONTEND] Starting React Dashboard on http://localhost:5173 ...
start "AutoApplyJobs Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ==========================================================
echo   All services launched in dedicated terminal windows!
echo   - Dashboard: http://localhost:5173
echo   - API Docs:  http://localhost:8000/docs
echo ==========================================================
echo.
pause
