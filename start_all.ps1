# AutoApplyJobs — Single Command Launcher (PowerShell)
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "      AutoApplyJobs — Launching Full-Stack Services" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. AI Service Detection (Ollama or Cloud Gemini)
$ollamaProc = Get-Process -Name "ollama" -ErrorAction SilentlyContinue
if ($ollamaProc) {
    Write-Host "[AI] Local Ollama service is running." -ForegroundColor Green
} elseif (Get-Command ollama -ErrorAction SilentlyContinue) {
    Write-Host "[AI] Starting local Ollama service in background..." -ForegroundColor Yellow
    Start-Process powershell -WindowStyle Minimized -ArgumentList "-Command", "ollama serve"
} else {
    Write-Host "[AI] Using Cloud Gemini API / Zero-Fabrication Answers from .env." -ForegroundColor Gray
}

# 2. Python Environment Detection
$pythonExe = "python"
$venvPy = Join-Path $PSScriptRoot "backend\venv\Scripts\python.exe"
if (Test-Path $venvPy) {
    $pythonExe = $venvPy
}

# 3. Launch Backend
Write-Host "`n[BACKEND] Starting FastAPI on http://localhost:8000..." -ForegroundColor Cyan
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot/backend'; & '$pythonExe' -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

# 4. Launch Frontend
Write-Host "[FRONTEND] Starting React Dashboard on http://localhost:5173..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$PSScriptRoot/frontend'; npm run dev"

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "  All services launched in dedicated PowerShell windows!" -ForegroundColor Green
Write-Host "  - React Dashboard: http://localhost:5173" -ForegroundColor Yellow
Write-Host "  - Backend API:     http://localhost:8000" -ForegroundColor Yellow
Write-Host "  - Interactive Docs: http://localhost:8000/docs" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
