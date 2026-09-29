#!/usr/bin/env python3
"""
AutoApplyJobs — Unified Services Launcher
Starts Backend (FastAPI), Frontend (Vite/React), and AI service (Ollama or Cloud Gemini).
Handles graceful shutdown on Ctrl+C.
Usage:
    python start_all.py
"""

import os
import sys
import time
import shutil
import signal
import subprocess
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = ROOT_DIR / "backend"
FRONTEND_DIR = ROOT_DIR / "frontend"

def get_python_exe():
    """Locate Python in virtual environment, or fallback to sys.executable."""
    if os.name == "nt":
        venv_py = BACKEND_DIR / "venv" / "Scripts" / "python.exe"
        if venv_py.exists():
            return str(venv_py)
    else:
        venv_py = BACKEND_DIR / "venv" / "bin" / "python"
        if venv_py.exists():
            return str(venv_py)
    return sys.executable

def check_ai_service():
    """Check AI status (Ollama or Cloud Gemini)."""
    ollama_exe = shutil.which("ollama")
    env_file = ROOT_DIR / ".env"
    has_gemini = False
    if env_file.exists():
        text = env_file.read_text(encoding="utf-8", errors="ignore")
        if "GEMINI_API_KEY" in text and "your_gemini_api_key_here" not in text:
            has_gemini = True

    if has_gemini:
        print("\033[92m[AI]\033[0m Cloud Gemini API key detected in .env.")
        ai_model = "qwen2.5-coder:7b"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8", errors="ignore").splitlines():
                if line.startswith("OLLAMA_MODEL="):
                    ai_model = line.split("=", 1)[1].strip()

        print("\033[93m[AI]\033[0m Ollama executable found. Checking if Ollama serve is active...")
        try:
            import urllib.request
            urllib.request.urlopen("http://localhost:11434/api/tags", timeout=2)
            print("\033[92m[AI]\033[0m Local Ollama service is active on http://localhost:11434.")
        except Exception:
            print("\033[93m[AI]\033[0m Starting local Ollama server in background...")
            try:
                subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                time.sleep(2)
                print("\033[92m[AI]\033[0m Ollama service started.")
            except Exception as e:
                print(f"\033[91m[AI]\033[0m Could not start Ollama: {e}")

        # Automatically load and warm up AI model
        try:
            print(f"\033[94m[AI]\033[0m Pre-warming AI Model ({ai_model}) into memory...")
            subprocess.Popen(["ollama", "run", ai_model, ""], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"\033[92m[AI]\033[0m AI Model ({ai_model}) is resident in memory and ready.")
        except Exception as e:
            print(f"\033[93m[AI]\033[0m Could not preload model {ai_model}: {e}")
    else:
        print("\033[93m[AI]\033[0m Note: Configure GEMINI_API_KEY in .env or install Ollama for questionnaire solving.")

def main():
    print("=" * 60)
    print("\033[96m  AutoApplyJobs — Launching Full-Stack Services\033[0m")
    print("=" * 60)

    # 1. AI Service Check
    check_ai_service()

    # 2. Prepare Python Environment
    python_exe = get_python_exe()
    print(f"\033[94m[BACKEND]\033[0m Using Python: {python_exe}")

    # 3. Launch Backend Process
    print("\033[94m[BACKEND]\033[0m Starting FastAPI backend on http://localhost:8000 ...")
    backend_cmd = [
        python_exe,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--reload"
    ]
    backend_proc = subprocess.Popen(
        backend_cmd,
        cwd=str(BACKEND_DIR)
    )

    # 4. Launch Frontend Process
    npm_exe = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not npm_exe:
        npm_exe = "npm"
    print("\033[92m[FRONTEND]\033[0m Starting React Vite dashboard on http://localhost:5173 ...")
    frontend_proc = subprocess.Popen(
        [npm_exe, "run", "dev"],
        cwd=str(FRONTEND_DIR),
        shell=(os.name == "nt")
    )

    print("\n" + "=" * 60)
    print("\033[92m  All services are running!\033[0m")
    print("  - Dashboard UI:  \033[96mhttp://localhost:5173\033[0m")
    print("  - Backend API:   \033[96mhttp://localhost:8000\033[0m")
    print("  - Swagger Docs:  \033[96mhttp://localhost:8000/docs\033[0m")
    print("  Press \033[91mCtrl+C\033[0m to terminate all services cleanly.")
    print("=" * 60 + "\n")

    def signal_handler(sig, frame):
        print("\n\033[93mShutting down all services...\033[0m")
        try:
            frontend_proc.terminate()
        except Exception:
            pass
        try:
            backend_proc.terminate()
        except Exception:
            pass
        time.sleep(1)
        try:
            frontend_proc.kill()
        except Exception:
            pass
        try:
            backend_proc.kill()
        except Exception:
            pass
        print("\033[92mAll services stopped.\033[0m")
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, signal_handler)

    try:
        while True:
            time.sleep(1)
            # If backend or frontend unexpectedly died, monitor
            if backend_proc.poll() is not None:
                print("\033[91mBackend process exited unexpectedly.\033[0m")
                break
            if frontend_proc.poll() is not None:
                print("\033[91mFrontend process exited unexpectedly.\033[0m")
                break
    except KeyboardInterrupt:
        signal_handler(None, None)

if __name__ == "__main__":
    main()
