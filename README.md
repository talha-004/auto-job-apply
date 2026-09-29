# 🤖 AutoApplyJobs — Autonomous AI Job Application System 🚀

> **An automated assistant that finds and applies to jobs for you on LinkedIn, Naukri, and Indeed — powered by local AI running right on your laptop.**
> 
> 100% Free & Private • Runs on your machine • No expensive monthly subscriptions.

---

## 💡 What is AutoApplyJobs in Simple Words?

Think of **AutoApplyJobs** as your personal job-search assistant:
1. It opens job websites (LinkedIn, Naukri, Indeed) just like a human does.
2. It searches for positions matching your job title and preferred location.
3. It reads each job posting, checks your resume, and fills in questions (like years of experience, notice period, and skills).
4. It submits the application and tracks everything automatically in a neat Excel spreadsheet and web dashboard.

---

## 💻 Your PC Hardware & Recommended AI Model

We analyzed your laptop hardware specifications:
- **Processor (CPU)**: 13th Gen Intel Core i7-13620H (10 Cores, 16 Threads)
- **RAM**: 16 GB DDR5/DDR4
- **Graphics Card (GPU)**: NVIDIA GeForce RTX 4050 Laptop GPU (**6 GB GDDR6 VRAM**)
- **Operating System**: Windows 11

### 🏆 Which Model is Best for Your PC?

| Model | Size | VRAM Usage | Speed on RTX 4050 | Why it is the best match |
|---|---|---|---|---|
| **`qwen2.5-coder:7b`** *(Recommended)* | **4.7 GB** | **~5.1 GB** | **35–50 tokens/sec** | **Fits 100% inside your 6 GB RTX 4050 VRAM.** Best accuracy for filling forms, parsing resumes, and outputting clean answers. *(Already installed on your machine!)* |
| **`qwen2.5-coder:3b`** *(Ultra-Light)* | 1.9 GB | ~2.3 GB | 70–90 tokens/sec | Uses minimal memory. Ideal if you are playing games or doing heavy video editing at the same time. |
| **Cloud Gemini 1.5 Flash** *(Zero-VRAM)* | Cloud API | 0 MB | Instant | Uses Google's free API key. Zero battery or memory usage on your laptop. |

---

## ⚡ How to Run Everything (Simple 3-Step Guide)

### Step 1: Start Your AI Model
Open a terminal (PowerShell or Command Prompt) and run:
```bash
ollama run qwen2.5-coder:7b
```
> Keep this window open. This provides the local AI brain on `http://localhost:11434`.

---

### Step 2: Start the System (One Single Command)

In your project folder (`AutoApplyJobs`), run:

#### Option A: One-Click File (Easiest for Windows)
Simply double-click:
```cmd
start_all.bat
```

#### Option B: From Terminal
```bash
python start_all.py
```

This single command will:
- Check that your AI model is ready.
- Start the Backend server on `http://localhost:8000`.
- Start the Web Dashboard on `http://localhost:5173`.

---

### Step 3: Open the Dashboard in Your Browser

Open your browser and navigate to:
👉 **[http://localhost:5173](http://localhost:5173)**

---

## 🖥️ How to Use the Dashboard (Beginner-Friendly)

1. **Upload Your Resume**:
   - Go to the **Candidate Resume** tab.
   - Drag and drop your `.pdf` or `.docx` resume.
   - The local AI will automatically extract your contact details, skills, and work history.
2. **Configure Your Application Settings**:
   - **Job Title / Keywords**: e.g., `Full Stack Developer`, `Python Developer`, `Data Analyst`.
   - **Location**: e.g., `Remote`, `Bangalore`, `New York`, `London`.
   - **Platforms**: Check the boxes for **LinkedIn**, **Naukri**, or **Indeed**.
3. **Fill the Q&A Vault (Optional but Recommended)**:
   - Add default answers for frequent questions (e.g., Notice Period = `30 days`, Expected Salary = `$90,000`, Authorized to work = `Yes`).
4. **Click "Start Auto-Apply Bot"**:
   - The browser will open and begin searching and applying.
   - Watch the live log screen on the dashboard to see progress in real time.
   - Your applied jobs are automatically saved to `job_applications.xlsx`.

---

## 🛡️ Anti-Ban & Safe Usage Tips

- **First Run (Keep Headless Disabled)**: On your first run, leave "Headless Mode" unchecked. If LinkedIn or Naukri asks you to log in with an OTP or solve a CAPTCHA, simply do it in the open browser. The bot will save your login cookies so you won't need to log in again.
- **Natural Human Delays**: The bot automatically pauses between actions and uses randomized human typing speeds to prevent bot detection.
- **Recommended Daily Limit**: Start with **20 to 30 applications per day** to keep your accounts healthy and trusted.

---

## 🚀 Advanced Features Included (V2)

- **🎯 ATS Keyword Gap Scorecard**: Scores your resume against every job posting and shows matching vs. missing keywords.
- **📄 Multi-Template Resumes**: Generates clean, tailored PDF resumes matching specific job descriptions.
- **🤝 Recruiter Lead Discovery & Follow-Up**: Finds the hiring manager or recruiter name and drafts polite follow-up messages.
- **📱 Mobile Companion (Telegram Bot)**: Get instant phone notifications when an application succeeds or when a CAPTCHA needs your attention.
- **📊 Conversion Funnel Analytics**: Visualizes how many jobs were found, applied to, screened, and interviewed.

---

## ❓ Frequently Asked Questions & Troubleshooting

#### 1. What if it says "Ollama not running"?
Make sure you ran `ollama run qwen2.5-coder:7b` in a terminal window first, or start the Ollama desktop app.

#### 2. Can I use this while working on my PC?
Yes! The `qwen2.5-coder:7b` model takes about ~5 GB of your 6 GB RTX 4050 GPU, leaving your 10-core CPU and 16 GB of system RAM completely smooth and responsive.

#### 3. How do I stop the automation?
Click the **"Stop Bot"** button on the dashboard at `http://localhost:5173`, or press `Ctrl + C` in the terminal running `start_all.py`.

#### 4. Where are my applied jobs saved?
All successful applications are exported directly to `backend/data/job_applications.xlsx` and can be downloaded anytime via the "Export Excel" button on the dashboard.

---

## 🛠️ Developer Manual Setup (Optional)

If you prefer starting backend and frontend separately:

### Backend
```bash
cd backend
.\venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## 📄 License
MIT License • Free and Open Source.
