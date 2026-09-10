#!/usr/bin/env bash
echo "=========================================="
echo "Starting AutoApplyJobs FastAPI Backend..."
echo "=========================================="
cd backend || exit 1

if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python -m venv venv
fi

# Activate virtual environment on Windows Git Bash
if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

echo "Ensuring Playwright chromium is installed..."
python -m playwright install chromium

echo "Launching Uvicorn server on http://localhost:8000 ..."
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
