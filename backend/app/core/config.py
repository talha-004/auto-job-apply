import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True, parents=True)

class Settings(BaseSettings):
    PROJECT_NAME: str = "AutoApplyJobs"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # Ollama Configuration
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5-coder:7b-instruct-q4_K_M"
    OLLAMA_TIMEOUT_SECONDS: int = 120
    
    # Storage Paths
    DATA_PATH: Path = DATA_DIR
    EXCEL_FILE_PATH: Path = DATA_DIR / "job_applications.xlsx"
    PROFILE_FILE_PATH: Path = DATA_DIR / "candidate_profile.json"
    RESUME_FILE_PATH: Path = DATA_DIR / "current_resume.pdf"
    RESUMES_DIR: Path = DATA_DIR / "resumes"
    COOKIES_DIR: Path = DATA_DIR / "cookies"
    BROWSER_USER_DATA_DIR: Path = DATA_DIR / "browser_profiles"
    USE_PERSISTENT_CONTEXT: bool = True
    LOGS_DIR: Path = DATA_DIR / "logs"
    LOG_FILE_PATH: Path = DATA_DIR / "logs" / "app.log"
    
    # Platform Credentials (loaded from .env)
    LINKEDIN_EMAIL: Optional[str] = None
    LINKEDIN_PASSWORD: Optional[str] = None
    LINKEDIN_USERNAME: Optional[str] = None
    
    NAUKRI_EMAIL: Optional[str] = None
    NAUKRI_PASSWORD: Optional[str] = None
    NAUKRI_USERNAME: Optional[str] = None
    
    INDEED_EMAIL: Optional[str] = None
    INDEED_PASSWORD: Optional[str] = None
    
    DINDIN_EMAIL: Optional[str] = None
    DINDIN_PASSWORD: Optional[str] = None

    # Optional Gemini LLM configuration
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: Optional[str] = "gemini-1.5-flash"

    # Optional DeepSeek & Groq LLM configuration
    DEEPSEEK_API_KEY: Optional[str] = None
    DEEPSEEK_MODEL: str = "deepseek-chat"
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    PRIMARY_LLM_PROVIDER: str = "ollama"

    # Application Defaults & Safety Limits
    DEFAULT_MAX_APPLICATIONS: int = 25
    MIN_DELAY_SECONDS: float = 2.0
    MAX_DELAY_SECONDS: float = 5.0
    COOLDOWN_BETWEEN_JOBS_SECONDS: float = 15.0
    MAX_RETRIES_PER_JOB: int = 2
    CAPTCHA_TIMEOUT_SECONDS: int = 300
    HEADLESS: bool = True
    DRY_RUN: bool = False

    # Outreach & SMTP Configuration
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USER: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_USE_TLS: bool = True
    SMTP_USE_SSL: bool = False
    SENDER_EMAIL: Optional[str] = None
    SENDER_NAME: Optional[str] = None
    OUTREACH_REQUIRE_APPROVAL: bool = True
    OUTREACH_DIR: Path = DATA_DIR / "outreach"

    # Background Scheduler Configuration
    SCHEDULER_ENABLED: bool = False
    SCHEDULER_MORNING_HOUR: int = 9
    SCHEDULER_MORNING_MINUTE: int = 0
    SCHEDULER_HEADLINE_REFRESH_HOURS: int = 6
    SCHEDULER_DAILY_CAP: int = 25

    # Optional Proxy Configuration (e.g., http://user:pass@proxy.example.com:8080)
    PROXY_URL: Optional[str] = None
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173", "*"]

    # Database (PostgreSQL / SQLite)
    DATABASE_URL: Optional[str] = "sqlite:///./data/autoapply.db"

    # Notifications & Webhook Alerts
    ENABLE_DESKTOP_NOTIFICATIONS: bool = True
    ENABLE_WEBHOOK_NOTIFICATIONS: bool = False
    WEBHOOK_URL: Optional[str] = None
    NOTIFICATION_EMAIL: Optional[str] = None

    # Recruiter Response Monitoring (IMAP)
    INBOX_MONITOR_ENABLED: bool = False
    IMAP_HOST: Optional[str] = None
    IMAP_PORT: int = 993
    IMAP_USER: Optional[str] = None
    IMAP_PASSWORD: Optional[str] = None
    IMAP_USE_SSL: bool = True

    # Security & Recovery Configuration
    ENCRYPTION_KEY: Optional[str] = None
    CHECKPOINTS_DIR: Path = DATA_DIR / "checkpoints"


    @property
    def COOKIE_DIR(self) -> Path:
        """Compatibility alias for COOKIES_DIR."""
        return self.COOKIES_DIR

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
        "extra": "ignore"
    }

settings = Settings()
settings.COOKIES_DIR.mkdir(exist_ok=True, parents=True)
settings.LOGS_DIR.mkdir(exist_ok=True, parents=True)
settings.OUTREACH_DIR.mkdir(exist_ok=True, parents=True)
settings.BROWSER_USER_DATA_DIR.mkdir(exist_ok=True, parents=True)
settings.CHECKPOINTS_DIR.mkdir(exist_ok=True, parents=True)


