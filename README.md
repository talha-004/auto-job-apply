# 🤖 AutoApplyJobs — Autonomous AI Job Application System 🚀

> **Production-ready, autonomous job application bot powered by local LLMs (Ollama + `qwen2.5-coder`), Playwright stealth browser automation, FastAPI, and a real-time React dashboard.**
>
> 100% Free & Open Source • Runs locally on your machine • No expensive third-party API keys required.

---

## 🌟 Key Features

- **🧠 100% Local & Free AI Intelligence**: Uses [Ollama](https://ollama.com/) with `qwen2.5-coder:7b-instruct-q4_K_M` to parse resumes, map arbitrary form fields, and intelligently answer portal screening questions.
- **💼 Multi-Platform Automation**:
  - **Naukri**: Quick Apply automation, chatbot questionnaire handler, and session persistence.
  - **LinkedIn**: Easy Apply automation with multi-step wizard traversal and screening responses.
  - **Indeed**: Indeed Apply automation and modal handling.
  - **Dindin & Direct Portals**: Universal form auto-fill for custom job boards.
- **🛡️ Stealth & Anti-Detection**:
  - Randomized typing jitter (`30-80ms`) and human-like scrolling.
  - Randomized viewports, realistic User-Agents (`Chrome 123`, `Firefox 124`), and evasion scripts removing `navigator.webdriver`.
  - Session cookie caching to avoid frequent re-logins.
- **🔐 Human-in-the-Loop (HITL)**:
  - Detects OTP challenges, CAPTCHAs (Cloudflare / reCAPTCHA / Arkose), and 2FA prompts.
  - Automatically pauses execution and alerts the dashboard via real-time WebSockets so you can solve the challenge and click **Resume**.
- **📊 Excel Application Tracker (`job_applications.xlsx`)**:
  - Automatically records timestamp, platform, job title, company, URL, status, and notes.
  - Built-in deduplication ensures you never apply to the same job URL twice.
- **⚡ Real-Time React Dashboard**:
  - Live terminal logs via WebSocket (`/ws/logs`).
  - Drag-and-drop resume upload (`.pdf` / `.docx`) with instant JSON profile inspection and editing.
  - Bot control panel: Start, Pause, Resume, Stop.
  - Headless mode toggle & Dry-run mode for safe testing.
  - Searchable application history with one-click Excel download.

---

## 🛠️ Architecture & Project Structure

```
AutoApplyJobs/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── endpoints/
│   │   │   │   ├── bot.py           # Bot start, stop, pause, resume, status
│   │   │   │   ├── jobs.py          # Job history, stats, export Excel
│   │   │   │   ├── resume.py        # PDF/DOCX upload, LLM parsing, profile edit
│   │   │   │   └── settings.py      # Health checks & platform credential status
│   │   │   └── api.py               # Combined API router
│   │   ├── core/
│   │   │   ├── config.py            # Pydantic settings & .env loader
│   │   │   ├── llm.py               # Ollama client & prompt templates
│   │   │   └── logger.py            # Thread-safe WebSocket broadcaster
│   │   ├── models/
│   │   │   ├── db_models.py         # SQLAlchemy models (SQLite/PostgreSQL)
│   │   │   └── job.py               # Pydantic schemas (Resume, JobRecord, etc.)
│   │   ├── platforms/
│   │   │   ├── base.py              # BasePlatform (Playwright, stealth, form scanning)
│   │   │   ├── linkedin.py          # LinkedIn Easy Apply bot
│   │   │   ├── naukri.py            # Naukri Quick Apply bot
│   │   │   ├── indeed.py            # Indeed Apply bot
│   │   │   └── dindin.py            # Custom platform bot
│   │   ├── services/
│   │   │   ├── bot_manager.py       # Thread-isolated async state machine
│   │   │   ├── excel_tracker.py     # openpyxl tracker & deduplication
│   │   │   └── resume_parser.py     # pypdf/docx extraction + LLM parser
│   │   └── main.py                  # FastAPI server & WebSocket endpoint
│   ├── data/                        # Excel sheet, cookies, candidate profiles
│   ├── requirements.txt             # Python dependencies
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── BotControlPanel.jsx      # Configuration, platforms & start/stop
│   │   │   ├── JobApplicationsTable.jsx # Applications table & Excel export
│   │   │   ├── LiveLogFeed.jsx          # Real-time WebSocket terminal
│   │   │   ├── Navbar.jsx               # Header, Ollama indicator, status badge
│   │   │   ├── ResumeUploader.jsx       # Resume upload & structured editor
│   │   │   └── StatusIndicator.jsx      # Progress counters & CAPTCHA alert
│   │   ├── context/
│   │   │   └── BotContext.jsx           # Central state & WebSocket sync
│   │   ├── services/
│   │   │   └── api.js                   # Axios client & WebSocket helpers
│   │   ├── App.jsx
│   │   ├── index.css
│   │   └── main.jsx
│   ├── package.json
│   ├── vite.config.js
│   └── Dockerfile
├── docker-compose.yml
├── .env.example
├── start_backend.bat
├── start_frontend.bat
└── README.md
```

---

## ⚡ Quick Start Guide

### 1. Prerequisites

Before getting started, make sure you have installed:
- **Python 3.10+** (with `pip`)
- **Node.js 18+ & npm**
- **[Ollama](https://ollama.com/)** (for local LLM capabilities)

---

### 2. Set Up the Local LLM (Ollama)

1. Download and install Ollama from [ollama.com](https://ollama.com).
2. Pull and start the recommended model:
   ```bash
   ollama run qwen2.5-coder:7b-instruct-q4_K_M
   ```
   *(Or the standard 7b model: `ollama run qwen2.5-coder:7b`)*
3. Keep Ollama running in the background. It will serve on `http://localhost:11434`.

---

### 3. Configure Environment Variables

1. Copy `.env.example` to create `.env` in the project root:
   ```bash
   cp .env.example .env
   ```
2. Open `.env` and fill in your platform credentials:
   ```env
   # Ollama LLM Settings
   OLLAMA_BASE_URL=http://localhost:11434
   OLLAMA_MODEL=qwen2.5-coder:7b-instruct-q4_K_M

   # Platform Credentials
   LINKEDIN_EMAIL=your_linkedin_email@example.com
   LINKEDIN_PASSWORD=your_linkedin_password

   NAUKRI_EMAIL=your_naukri_email@example.com
   NAUKRI_PASSWORD=your_naukri_password

   INDEED_EMAIL=your_indeed_email@example.com
   INDEED_PASSWORD=your_indeed_password

   # Safety & Speed Settings
   DEFAULT_MAX_APPLICATIONS=25
   MIN_DELAY_SECONDS=2.0
   MAX_DELAY_SECONDS=5.0
   COOLDOWN_BETWEEN_JOBS_SECONDS=15.0
   HEADLESS=False
   DRY_RUN=False
   ```

---

### 4. Backend Setup & Run

#### In Windows Terminal / Git Bash:
```bash
# 1. Navigate to the backend directory
cd backend

# 2. Create and activate a Python virtual environment
python -m venv venv

# On Windows (Git Bash):
source venv/Scripts/activate
# On Windows (CMD / PowerShell):
.\venv\Scripts\activate
# On Linux / macOS:
source venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt

# 4. Install Playwright Chromium browser binary
playwright install chromium

# 5. Start the FastAPI Uvicorn server
uvicorn app.main:app --reload --port 8000
```
Backend API will be live at `http://localhost:8000` (Interactive Swagger docs: `http://localhost:8000/docs`).

---

### 5. Frontend Setup & Run

Open a new terminal:
```bash
# 1. Navigate to frontend directory
cd frontend

# 2. Install Node.js packages
npm install

# 3. Start Vite development server
npm run dev
```
Frontend Dashboard will be live at `http://localhost:5173`.

---

## 🚀 One-Click Windows Launchers

On Windows, you can also launch both services with the provided batch scripts:
- Double-click **`start_backend.bat`**
- Double-click **`start_frontend.bat`**

---

## 🎯 How to Use the System

1. Open **`http://localhost:5173`** in your browser.
2. **Upload Your Resume**:
   - Go to the **Candidate Resume** section.
   - Upload your `.pdf` or `.docx` resume.
   - The local Ollama LLM will automatically parse your contact info, experience timeline, skills, and screening answers into structured JSON.
   - You can review and edit any parsed field directly in the dashboard.
3. **Configure the Bot**:
   - **Target Platforms**: Check the platforms you want to apply on (e.g., Naukri, LinkedIn, Indeed).
   - **Keywords**: e.g., `Full Stack Developer`, `React Developer`, `Python Engineer`.
   - **Location**: e.g., `Remote`, `Bangalore`, `Hyderabad`, `Pune`, `New York`.
   - **Headless Mode**: Leave **unchecked** for your first run so you can observe the browser and enter any OTP/SMS codes if prompted.
   - **Dry Run Mode**: (Optional) Enable this to test form scanning and traversal without clicking the final submit button.
4. **Click "Start Auto-Apply Bot"**:
   - Watch the visible browser open, search, and apply to matching roles.
   - Monitor the **Live Activity Feed** on the dashboard for real-time progress and logs.
   - Download `job_applications.xlsx` anytime to review your application records.

---

## 🛡️ Anti-Detection & Safety Best Practices

1. **First-Run Interactive Login**: Keep **Headless Mode disabled** on your first run. If a platform asks for an OTP or security check, enter it in the open browser. The bot will save the session cookies in `backend/data/cookies/` and reuse them on future runs.
2. **Cooldowns & Pacing**: Keep the cooldown between applications set to at least **15-30 seconds** to mimic human behavior.
3. **Daily Application Limits**: Target **25-40 applications per day** to stay well within platform rate limits and prevent account restrictions.
4. **Dry-Run Testing**: Always test a new keyword search with **Dry Run Mode** enabled first to ensure the bot targets the right listings.

---

## 🐳 Docker Deployment (Optional)

To spin up the entire stack using Docker Compose:

```bash
docker-compose up --build
```
- Frontend Dashboard: `http://localhost:3000`
- Backend API: `http://localhost:8000`

---

## 📄 License

MIT License • Free and Open Source. Created for educational and personal career automation purposes.
