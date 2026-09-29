from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy import (
    Column, 
    Integer, 
    String, 
    Text, 
    Float, 
    DateTime, 
    Boolean, 
    JSON, 
    ForeignKey,
    Index
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class DBJobApplication(Base):
    """Primary application record tracking candidate submissions across all boards and platforms."""
    __tablename__ = "job_applications"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    platform = Column(String(50), nullable=False, index=True)
    job_title = Column(String(255), nullable=False, index=True)
    company = Column(String(255), nullable=False, index=True)
    job_url = Column(Text, unique=True, nullable=False, index=True)
    job_id = Column(String(100), nullable=True, index=True)
    status = Column(String(50), nullable=False, index=True)
    applied_date = Column(String(20), nullable=False, index=True)

    # Scoring & Quality
    match_score = Column(Float, nullable=True, default=0.0)
    job_quality_score = Column(Float, nullable=True, default=0.0)
    priority_tier = Column(String(20), nullable=True, default="STANDARD")

    # Job Attributes
    salary_raw = Column(String(100), nullable=True)
    location_raw = Column(String(255), nullable=True)
    experience_raw = Column(String(100), nullable=True)

    # Recruiter & Contact Metadata
    hr_email = Column(String(255), nullable=True, index=True)
    hr_name = Column(String(255), nullable=True)
    hr_phone = Column(String(50), nullable=True)

    # Diagnostics & Resolutions
    reason_code = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    tailored_resume_path = Column(Text, nullable=True)
    metadata_json = Column(JSON, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    attempts = relationship("DBApplicationAttempt", back_populates="application", cascade="all, delete-orphan")


class DBApplicationAttempt(Base):
    """Audit trail of automated browser/API application attempts for a job."""
    __tablename__ = "application_attempts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    application_id = Column(Integer, ForeignKey("job_applications.id", ondelete="CASCADE"), nullable=False, index=True)
    attempt_number = Column(Integer, default=1)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    status = Column(String(50), nullable=False)
    screenshot_path = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    duration_seconds = Column(Float, nullable=True)

    application = relationship("DBJobApplication", back_populates="attempts")


class DBRecruiterContact(Base):
    """Recruiter contact discovered from job postings or external ATS."""
    __tablename__ = "recruiter_contacts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=True, index=True)
    email = Column(String(255), nullable=True, unique=True, index=True)
    phone = Column(String(50), nullable=True)
    whatsapp_number = Column(String(50), nullable=True)
    company = Column(String(255), nullable=True, index=True)
    designation = Column(String(255), nullable=True)
    linkedin_url = Column(Text, nullable=True)
    confidence = Column(String(20), default="medium")
    source = Column(String(50), default="job_description")
    created_at = Column(DateTime, default=datetime.utcnow)


class DBOutreachMessage(Base):
    """Personalized cold email or WhatsApp message drafted/sent to recruiters."""
    __tablename__ = "outreach_messages"

    id = Column(String(100), primary_key=True, index=True)
    job_id = Column(String(100), nullable=True, index=True)
    job_title = Column(String(255), nullable=False)
    company = Column(String(255), nullable=False)
    recipient_email = Column(String(255), nullable=True)
    recipient_name = Column(String(255), nullable=True)
    channel = Column(String(20), default="EMAIL")
    subject = Column(Text, nullable=True)
    body_text = Column(Text, nullable=False)
    status = Column(String(50), default="DRAFTED", index=True)
    attachment_path = Column(Text, nullable=True)
    whatsapp_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)


class DBInterventionTicket(Base):
    """Manual intervention items (CAPTCHA, 2FA, unconfirmed submissions, sensitive questions)."""
    __tablename__ = "intervention_tickets"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    job_url = Column(Text, nullable=False, index=True)
    job_title = Column(String(255), nullable=True)
    company = Column(String(255), nullable=True)
    ticket_type = Column(String(50), nullable=False, index=True)  # CAPTCHA, 2FA, REVIEW, QUESTION
    status = Column(String(50), default="OPEN", index=True)  # OPEN, RESOLVED, DISMISSED
    notes = Column(Text, nullable=True)
    resolution_action = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class DBCandidateProfile(Base):
    """Candidate profile and QA Vault snapshot."""
    __tablename__ = "candidate_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    phone = Column(String(50), nullable=True)
    location = Column(String(255), nullable=True)
    profile_json = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DBBotSession(Base):
    """Autonomous runner execution session history."""
    __tablename__ = "bot_sessions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    total_applied = Column(Integer, default=0)
    total_success = Column(Integer, default=0)
    total_failed = Column(Integer, default=0)
    config_json = Column(JSON, nullable=True)
