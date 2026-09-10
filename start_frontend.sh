#!/usr/bin/env bash
echo "=========================================="
echo "Starting AutoApplyJobs React Dashboard..."
echo "=========================================="
cd frontend || exit 1

if [ ! -d "node_modules" ]; then
    echo "Installing npm dependencies..."
    npm install
fi

echo "Starting Vite Dev Server on http://localhost:5173 ..."
npm run dev
