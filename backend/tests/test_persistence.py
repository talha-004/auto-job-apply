import pytest
from datetime import datetime, date
from sqlalchemy.orm import Session

from app.core.database import SessionLocal, init_db, check_db_connection
from app.models.db_models import (
    DBJobApplication,
    DBApplicationAttempt,
    DBRecruiterContact,
    DBOutreachMessage,
    DBInterventionTicket
)
from app.models.job import JobApplicationRecord, ApplicationStatus
from app.services.persistence_service import persistence_service


@pytest.fixture(scope="module", autouse=True)
def setup_database():
    """Ensure database connection and tables exist."""
    init_db()
    persistence_service.initialize()
    yield


def test_database_connection():
    """Verify active database connectivity."""
    assert check_db_connection() is True


def test_database_schema_and_tables():
    """Verify all required tables exist and are queryable."""
    with SessionLocal() as db:
        app_count = db.query(DBJobApplication).count()
        assert app_count >= 0

        attempt_count = db.query(DBApplicationAttempt).count()
        assert attempt_count >= 0

        contact_count = db.query(DBRecruiterContact).count()
        assert contact_count >= 0

        msg_count = db.query(DBOutreachMessage).count()
        assert msg_count >= 0

        ticket_count = db.query(DBInterventionTicket).count()
        assert ticket_count >= 0


def test_save_and_update_application():
    """Verify upserting an application record into PostgreSQL."""
    test_url = "https://www.linkedin.com/jobs/view/test-pg-persist-12345"
    record = JobApplicationRecord(
        timestamp=datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        platform="LinkedIn",
        job_title="Senior Python Architect",
        company="PostgreSQL Cloud Corp",
        job_url=test_url,
        job_id="pg_job_999",
        status=ApplicationStatus.APPLIED,
        applied_date=date.today().isoformat(),
        match_score=94,
        job_quality_score=88.0,
        priority_tier="HIGH",
        salary_raw="35-45 LPA",
        location_raw="Bengaluru, India",
        notes="Automated test application",
        hr_email="hiring@pgcloudcorp.com"
    )

    # 1. Insert
    saved = persistence_service.save_or_update_application(record)
    assert saved is not None
    assert saved.id is not None
    assert saved.job_url == test_url
    assert saved.company == "PostgreSQL Cloud Corp"
    assert saved.match_score == 94.0

    # 2. Update existing
    record.status = ApplicationStatus.SUCCESS
    record.notes = "Invited for technical round"
    updated = persistence_service.save_or_update_application(record)
    assert updated is not None
    assert updated.id == saved.id
    assert updated.status == "Success"
    assert updated.notes == "Invited for technical round"


def test_record_application_attempt():
    """Verify application attempt logging and foreign key relationship."""
    test_url = "https://www.linkedin.com/jobs/view/test-pg-persist-12345"
    attempt = persistence_service.record_attempt(
        job_url=test_url,
        status="SUCCESS",
        attempt_number=1,
        screenshot_path="/screenshots/attempt_1.png",
        error_message=None,
        duration_seconds=12.4
    )
    assert attempt is not None
    assert attempt.id is not None
    assert attempt.status == "SUCCESS"
    assert attempt.duration_seconds == 12.4

    with SessionLocal() as db:
        app_entry = db.query(DBJobApplication).filter(DBJobApplication.job_url == test_url).first()
        assert len(app_entry.attempts) >= 1
        assert app_entry.attempts[0].status == "SUCCESS"


def test_create_intervention_ticket():
    """Verify intervention ticket creation for CAPTCHAs or MFA."""
    ticket = persistence_service.create_intervention_ticket(
        job_url="https://jobs.example.com/apply/security-check",
        job_title="Backend Engineer",
        company="SecureTech Inc",
        ticket_type="CAPTCHA",
        notes="Cloudflare Turnstile challenge detected"
    )
    assert ticket is not None
    assert ticket.id is not None
    assert ticket.ticket_type == "CAPTCHA"
    assert ticket.status == "OPEN"


def test_get_applications_filtering_and_stats():
    """Verify querying and statistical calculations directly from database."""
    apps = persistence_service.get_applications(limit=10, platform="LinkedIn")
    assert isinstance(apps, list)
    assert len(apps) >= 1

    stats = persistence_service.get_statistics()
    assert isinstance(stats, dict)
    assert "total_applications" in stats
    assert "success_rate" in stats
    assert stats["total_applications"] >= 1
    assert "by_platform" in stats
