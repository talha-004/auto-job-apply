from datetime import datetime
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

class PlatformEnum(str, Enum):
    LINKEDIN = "LinkedIn"
    NAUKRI = "Naukri"
    INDEED = "Indeed"
    DINDIN = "Dindin"

class ReasonCode(str, Enum):
    LOW_MATCH = "LOW_MATCH"
    EXTERNAL_APPLICATION = "EXTERNAL_APPLICATION"
    UNKNOWN_APPLICATION_TYPE = "UNKNOWN_APPLICATION_TYPE"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    EXACT_DUPLICATE = "EXACT_DUPLICATE"
    PROFILE_INCOMPLETE = "PROFILE_INCOMPLETE"
    AMBIGUOUS_QUESTION = "AMBIGUOUS_QUESTION"
    SUBMISSION_UNKNOWN = "SUBMISSION_UNKNOWN"
    SUBMISSION_FAILED = "SUBMISSION_FAILED"
    SUBMISSION_CONFIRMED = "SUBMISSION_CONFIRMED"
    APPLICATION_LIMIT = "APPLICATION_LIMIT"
    PERSISTENCE_FAILURE = "PERSISTENCE_FAILURE"
    JOB_RISK_FLAG = "JOB_RISK_FLAG"
    APPLY_BUTTON_MISSING = "APPLY_BUTTON_MISSING"
    SAFE_CLICK_FAILED = "SAFE_CLICK_FAILED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"


class JobLifecycleStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    ANALYZED = "ANALYZED"
    ELIGIBLE = "ELIGIBLE"
    APPLYING = "APPLYING"
    SUCCESS = "SUCCESS"
    SKIPPED = "SKIPPED"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    FAILED = "FAILED"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"


class ApplicationStatus(str, Enum):
    APPLIED = "Applied"
    SUCCESS = "Success"
    FAILED = "Failed"
    SKIPPED = "Skipped"
    DISCOVERED = "Discovered"
    MANUAL_REVIEW_NEEDED = "Manual Review Needed"
    MANUAL_REVIEW = "Manual Review Needed"
    IN_PROGRESS = "In Progress"
    APPLYING = "Applying"
    DRY_RUN_COMPLETED = "Dry Run Completed"
    POSSIBLE_DUPLICATE = "Possible Duplicate"

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
            "notice_period_days": None,
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
    quick_apply_only: bool = True
    freshness_days: Optional[int] = 3
    min_match_score: int = 60
    match_gating_mode: str = "observe"

    @field_validator("freshness_days")
    @classmethod
    def validate_freshness_days(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v not in (1, 3, 7):
            raise ValueError("freshness_days must be None (Any Time), 1 (24h), 3 (3 days), or 7 (7 days)")
        return v

    @field_validator("min_match_score")
    @classmethod
    def validate_min_match_score(cls, v: int) -> int:
        if v < 0 or v > 100:
            raise ValueError("min_match_score must be between 0 and 100")
        return v

    @field_validator("match_gating_mode")
    @classmethod
    def validate_match_gating_mode(cls, v: str) -> str:
        if v not in ("observe", "enforce"):
            raise ValueError("match_gating_mode must be 'observe' or 'enforce'")
        return v

class JobApplicationRecord(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    job_id: Optional[str] = None
    run_id: Optional[str] = None
    application_attempt_id: Optional[str] = None
    platform: str
    job_title: str
    company: str
    job_url: str
    status: ApplicationStatus
    lifecycle_status: Optional[JobLifecycleStatus] = None
    application_type: str = "quick_apply"
    applied_date: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    match_score: Optional[int] = None
    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    job_quality_score: Optional[int] = None
    priority_score: Optional[int] = None
    priority_reasons: List[str] = Field(default_factory=list)
    risk_flags: List[str] = Field(default_factory=list)
    risk_evidence: Dict[str, str] = Field(default_factory=dict)
    reason_code: Optional[str] = None
    status_reason: Optional[str] = None
    hr_email: Optional[str] = None
    recruiter_name: Optional[str] = None
    contacts: List[Dict[str, Any]] = Field(default_factory=list)
    skip_reason: Optional[str] = None
    suggested_outreach: Optional[str] = None
    lifecycle_history: List[Dict[str, str]] = Field(default_factory=list)
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
