#!/usr/bin/env bash
# AutoApplyJobs — Single Command Bash Launcher
# Starts Backend (FastAPI), Frontend (React/Vite), and AI Services

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR" || exit 1

# Detect Python executable (prefer backend virtual environment)
if [ -f "$DIR/backend/venv/Scripts/python" ]; then
    PYTHON_EXE="$DIR/backend/venv/Scripts/python"
elif [ -f "$DIR/backend/venv/bin/python" ]; then
    PYTHON_EXE="$DIR/backend/venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    PYTHON_EXE="python3"
else
    PYTHON_EXE="python"
fi

# Run unified launcher
exec "$PYTHON_EXE" "$DIR/start_all.py" "$@"
