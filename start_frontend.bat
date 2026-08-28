@echo off
echo ==========================================
echo Starting AutoApplyJobs React Dashboard...
echo ==========================================
cd frontend
if not exist "node_modules" (
    echo Installing npm dependencies...
    npm install
)
echo Starting Vite Dev Server on http://localhost:5173 ...
npm run dev
pause
