@echo off
echo ==========================================
echo Starting AutoApplyJobs FastAPI Backend...
echo ==========================================
cd backend
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate
echo Installing dependencies...
pip install -r requirements.txt
echo Ensuring Playwright chromium is installed...
playwright install chromium
echo Launching Uvicorn server on http://localhost:8000 ...
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
