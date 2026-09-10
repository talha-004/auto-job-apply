from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class PlatformEnum(str, Enum):
    LINKEDIN = "LinkedIn"
    NAUKRI = "Naukri"
    INDEED = "Indeed"
    DINDIN = "Dindin"

class ApplicationStatus(str, Enum):
    APPLIED = "Applied"
    SUCCESS = "Success"
    FAILED = "Failed"
    SKIPPED = "Skipped"
    MANUAL_REVIEW_NEEDED = "Manual Review Needed"
    IN_PROGRESS = "In Progress"
    DRY_RUN_COMPLETED = "Dry Run Completed"

class BotState(str, Enum):
    IDLE = "Idle"
    RUNNING = "Running"
    PAUSED = "Paused"
    STOPPED = "Stopped"

class WorkExperience(BaseModel):
    company: str = ""
    title: str = ""
    start_date: str = ""
    end_date: str = ""
    location: str = ""
    description: str = ""

class Education(BaseModel):
    institution: str = ""
    degree: str = ""
    field: str = ""
    graduation_year: str = ""
    grade_or_gpa: Optional[str] = ""

class ResumeProfile(BaseModel):
    full_name: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    linkedin_url: Optional[str] = ""
    github_url: Optional[str] = ""
    portfolio_url: Optional[str] = ""
    years_of_experience: float = 0.0
    summary: str = ""
    skills: List[str] = Field(default_factory=list)
    work_experience: List[WorkExperience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    languages: List[str] = Field(default_factory=list)
    custom_answers: Dict[str, Any] = Field(
        default_factory=lambda: {
            "notice_period_days": 15,
            "expected_salary": "Negotiable",
            "current_salary": "",
            "work_authorization": "Yes",
            "require_sponsorship": "No",
            "willing_to_relocate": "Yes",
            "remote_preferred": "Yes",
            "gender": "Decline to specify",
            "veteran_status": "No",
            "disability_status": "No"
        }
    )

class SearchConfig(BaseModel):
    keywords: str = "Full Stack Developer"
    location: str = "Remote"
    experience_years: Optional[int] = None
    platforms: List[PlatformEnum] = Field(default_factory=lambda: [PlatformEnum.LINKEDIN, PlatformEnum.NAUKRI, PlatformEnum.INDEED, PlatformEnum.DINDIN])
    max_applications: int = 25
    cooldown_seconds: float = 15.0
    headless: bool = True
    dry_run: bool = False

class JobApplicationRecord(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    platform: str
    job_title: str
    company: str
    job_url: str
    status: ApplicationStatus
    applied_date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    notes: str = ""

class LogLevel(str, Enum):
    INFO = "INFO"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    ACTION = "ACTION"

class LogMessage(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%H:%M:%S"))
    level: LogLevel = LogLevel.INFO
    platform: Optional[str] = None
    message: str
    details: Optional[Dict[str, Any]] = None

class BotStatusResponse(BaseModel):
    state: BotState
    current_platform: Optional[str] = None
    current_job: Optional[str] = None
    applied_count: int = 0
    success_count: int = 0
    failed_count: int = 0
    skipped_count: int = 0
    total_target: int = 0
    is_paused_for_captcha: bool = False
    captcha_message: Optional[str] = None
    start_time: Optional[str] = None
