@echo off
setlocal enabledelayedexpansion
title AutoApplyJobs — All Services Launcher

echo ==========================================================
echo       AutoApplyJobs — Launching Full-Stack Services
echo ==========================================================

:: 1. Detect AI model from backend\.env, root .env, or fallback to qwen2.5-coder:7b
set "AI_MODEL=qwen2.5-coder:7b"
if exist "%~dp0backend\.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0backend\.env") do (
        if "%%A"=="OLLAMA_MODEL" (
            set "AI_MODEL=%%B"
        )
    )
) else if exist "%~dp0.env" (
    for /f "usebackq tokens=1,* delims==" %%A in ("%~dp0.env") do (
        if "%%A"=="OLLAMA_MODEL" (
            set "AI_MODEL=%%B"
        )
    )
)
:: Trim possible quotes or leading/trailing whitespace
for /f "tokens=*" %%T in ("!AI_MODEL!") do set "AI_MODEL=%%T"

:: 2. Check and automatically start AI service (Ollama)
where ollama >nul 2>nul
if "%ERRORLEVEL%"=="0" (
    tasklist /fi "imagename eq ollama.exe" 2>NUL | find /i "ollama.exe" >NUL
    if "%ERRORLEVEL%"=="0" (
        echo [AI] Ollama background daemon is active.
    ) else (
        echo [AI] Starting local Ollama service in background...
        start "Ollama Service" /min cmd /c "ollama serve"
        timeout /t 2 /nobreak >nul
    )

    echo [AI] Automatically loading and pre-warming AI Model: !AI_MODEL! ...
    start "AI Model Runner" /min cmd /c "ollama run !AI_MODEL! "" && exit"
    echo [AI] AI Model !AI_MODEL! is loaded in memory for zero-latency answering.
) else (
    echo [AI] Ollama not found on PATH. Falling back to Cloud Gemini / rule engine.
)

:: 3. Python environment detection
set "PYTHON_EXE=python"
if exist "%~dp0venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0venv\Scripts\python.exe"
) else if exist "%~dp0backend\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0backend\venv\Scripts\python.exe"
)

echo.
echo [BACKEND] Starting FastAPI on http://localhost:8000 ...
start "AutoApplyJobs Backend" cmd /k "cd /d "%~dp0backend" && "%PYTHON_EXE%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

echo [BACKEND] Waiting for API initialization...
powershell -NoProfile -Command "Start-Sleep -Seconds 3" >nul 2>&1

echo.
echo [FRONTEND] Starting React Dashboard on http://localhost:5173 ...
start "AutoApplyJobs Frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

echo.
echo ==========================================================
echo   All services launched in dedicated terminal windows!
echo   - Local AI Model: !AI_MODEL!
echo   - Dashboard:      http://localhost:5173
echo   - API Swagger:    http://localhost:8000/docs
echo ==========================================================
echo.
pause
