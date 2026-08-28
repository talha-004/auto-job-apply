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
    COOKIES_DIR: Path = DATA_DIR / "cookies"
    LOGS_DIR: Path = DATA_DIR / "logs"
    LOG_FILE_PATH: Path = DATA_DIR / "logs" / "app.log"
    
    # Platform Credentials (loaded from .env)
    LINKEDIN_EMAIL: Optional[str] = None
    LINKEDIN_PASSWORD: Optional[str] = None
    
    NAUKRI_EMAIL: Optional[str] = None
    NAUKRI_PASSWORD: Optional[str] = None
    
    INDEED_EMAIL: Optional[str] = None
    INDEED_PASSWORD: Optional[str] = None
    
    DINDIN_EMAIL: Optional[str] = None
    DINDIN_PASSWORD: Optional[str] = None

    # Application Defaults & Safety Limits
    DEFAULT_MAX_APPLICATIONS: int = 25
    MIN_DELAY_SECONDS: float = 2.0
    MAX_DELAY_SECONDS: float = 5.0
    COOLDOWN_BETWEEN_JOBS_SECONDS: float = 15.0
    MAX_RETRIES_PER_JOB: int = 2
    CAPTCHA_TIMEOUT_SECONDS: int = 300
    HEADLESS: bool = True
    DRY_RUN: bool = False

    # Optional Proxy Configuration (e.g., http://user:pass@proxy.example.com:8080)
    PROXY_URL: Optional[str] = None
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:5173", "*"]

    # Database (Optional PostgreSQL)
    DATABASE_URL: Optional[str] = "sqlite:///./data/autoapply.db"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

settings = Settings()
settings.COOKIES_DIR.mkdir(exist_ok=True, parents=True)
settings.LOGS_DIR.mkdir(exist_ok=True, parents=True)
