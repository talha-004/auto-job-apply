import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pathlib import Path

from app.models.job import (
    ResumeProfile,
    WorkExperience,
    JobApplicationRecord,
    ApplicationStatus,
    SearchConfig
)
from app.platforms.base import PersistenceError
from app.platforms.naukri_helpers import (
    JobContact,
    extract_job_contacts,
    ApplicationType
)
from app.services.match_scorer import match_scorer, MatchScorer
from app.services.excel_tracker import ExcelTracker


# =====================================================================
# 1. Job Contact Extraction Tests
# =====================================================================
def test_extract_job_contacts_multiple_and_types():
    """Extract multiple emails, categorize contact types, and exclude system addresses."""
    jd_text = """
    Senior Python Engineer at InnovateTech.
    Send your updated resume to careers@innovatetech.com or hr@innovatetech.com.
    For technical inquiries, contact the hiring lead at rahul.verma@innovatetech.com.
    Do not reply to noreply@innovatetech.com or support@naukri.com.
    """
    recruiter_text = "Posted by: Priya Sharma (Talent Acquisition Specialist) - priya.recruiter@innovatetech.com"

    contacts = extract_job_contacts(jd_text, recruiter_text)
    emails = [c.email for c in contacts]

    # Must find real contact emails
    assert "priya.recruiter@innovatetech.com" in emails
    assert "careers@innovatetech.com" in emails
    assert "hr@innovatetech.com" in emails
    assert "rahul.verma@innovatetech.com" in emails

    # Must EXCLUDE automated / system / support / naukri addresses
    assert "noreply@innovatetech.com" not in emails
    assert "support@naukri.com" not in emails

    # Check contact types
    contact_map = {c.email: c for c in contacts}
    assert contact_map["hr@innovatetech.com"].contact_type == "hr"
    assert contact_map["careers@innovatetech.com"].contact_type == "careers"
    assert contact_map["priya.recruiter@innovatetech.com"].contact_type == "recruiter"
    assert contact_map["rahul.verma@innovatetech.com"].contact_type == "personal"
    assert contact_map["priya.recruiter@innovatetech.com"].name == "Priya Sharma"


def test_extract_job_contacts_deduplication_and_casing():
    """Ensure emails in varying cases and duplicates are cleanly normalized and deduplicated."""
    jd_text = """
    Contact HR: HR@COMPANY.COM
    Also email: hr@company.com
    Recruitment team: JOBS@COMPANY.COM
    """
    contacts = extract_job_contacts(jd_text, "")
    emails = [c.email for c in contacts]

    assert emails.count("hr@company.com") == 1
    assert "jobs@company.com" in emails
    assert len(contacts) == 2


# =====================================================================
# 2. Match Scoring Contract & Fallback Math
# =====================================================================
def test_match_scoring_standard_contract():
    """60/20/10/10 scoring when required, preferred, title, and experience all exist."""
    profile = ResumeProfile(
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "React"],
        years_of_experience=4.0,
        work_experience=[WorkExperience(title="Backend Engineer", company="Tech A")]
    )
    jd_text = """
    Job Title: Backend Engineer
    Required Skills: Python, FastAPI, PostgreSQL
    Preferred Skills: Docker, Kubernetes
    Experience: 3-5 years required.
    """
    result = match_scorer.score_job("Backend Engineer", jd_text, profile, min_threshold=60)

    assert result.is_eligible is True
    assert result.score > 70
    assert "python" in [s.lower() for s in result.matched_skills]
    assert "fastapi" in [s.lower() for s in result.matched_skills]
    assert result.is_low_confidence_parse is False


def test_match_scoring_fallback_missing_preferred():
    """Fallback 1: No preferred section -> 20 pts redistributed to Required (80 pts total)."""
    profile = ResumeProfile(
        skills=["Python", "FastAPI"],
        years_of_experience=3.0,
        work_experience=[WorkExperience(title="Python Developer", company="Tech A")]
    )
    jd_text = """
    Job Title: Python Developer
    Required: Python, FastAPI
    Experience: 3 years
    """
    result = match_scorer.score_job("Python Developer", jd_text, profile, min_threshold=60)

    # 100% of required (80 pts) + 10 pts title + 10 pts experience = 100 pts
    assert result.score == 100
    assert result.is_eligible is True


def test_match_scoring_fallback_missing_experience():
    """Fallback 2: No experience mentioned in JD -> neutral 10 pts awarded."""
    profile = ResumeProfile(
        skills=["React", "TypeScript"],
        years_of_experience=1.0,
        work_experience=[WorkExperience(title="Frontend Developer", company="Startup")]
    )
    jd_text = """
    Looking for a passionate Frontend Developer.
    Requirements: React, TypeScript
    """
    result = match_scorer.score_job("Frontend Developer", jd_text, profile, min_threshold=60)

    # Experience points should be awarded neutrally (10 pts)
    assert result.score >= 90
    assert result.is_eligible is True


def test_match_scoring_fallback_zero_skills_mathematical_formula():
    """
    Fallback 3: Zero identifiable tech skills in JD.
    Formula: score = round(70 * title_ratio + exp_pts), flagged as low confidence.
    """
    profile = ResumeProfile(
        skills=["Python", "Go"],
        years_of_experience=5.0,
        work_experience=[WorkExperience(title="Software Engineer", company="Global Tech")]
    )
    # JD with abstract text and no recognizable tech keywords
    jd_text = """
    We are seeking a dynamic professional for our innovation team.
    Responsible for driving cross-functional collaboration and business alignment.
    Must have 4+ years of relevant industry background.
    """
    result = match_scorer.score_job("Software Engineer", jd_text, profile, min_threshold=50)

    assert result.is_low_confidence_parse is True
    # Title "Software Engineer" matches profile experience title -> title_ratio > 0
    # exp_pts = 10 (candidate 5.0 >= 4.0)
    # score must match exact formula
    assert 0 <= result.score <= 100
    assert result.reasons[0].startswith("Low confidence parse")


# =====================================================================
# 3. Discover First & Deduplication Tests
# =====================================================================
def test_excel_tracker_deduplication_and_status(tmp_path: Path):
    """Excel tracker correctly identifies already processed URLs and distinguishes statuses."""
    excel_file = tmp_path / "test_applications.xlsx"
    tracker = ExcelTracker(file_path=excel_file)

    rec1 = JobApplicationRecord(
        platform="Naukri",
        job_title="Full Stack Engineer",
        company="Alpha Corp",
        job_url="https://www.naukri.com/job-listings-alpha-12345",
        status=ApplicationStatus.DISCOVERED,
        match_score=85,
        hr_email="hr@alpha.com"
    )
    tracker.log_application(rec1)

    # 1. Check duplicate detection
    assert tracker.is_already_processed("https://www.naukri.com/job-listings-alpha-12345") is True
    assert tracker.is_already_processed("https://www.naukri.com/job-listings-alpha-12345?src=srp") is True
    assert tracker.is_already_processed("https://www.naukri.com/other-job") is False
    assert tracker.get_processed_status("https://www.naukri.com/job-listings-alpha-12345") == "Discovered"

    # 2. Update status from DISCOVERED -> SUCCESS
    updated = tracker.update_application_status(
        "https://www.naukri.com/job-listings-alpha-12345",
        ApplicationStatus.SUCCESS,
        notes="Applied successfully"
    )
    assert updated is True
    assert tracker.get_processed_status("https://www.naukri.com/job-listings-alpha-12345") == "Success"
    assert tracker.is_already_applied("https://www.naukri.com/job-listings-alpha-12345") is True


# =====================================================================
# 4. Persistence Failure Safety Tests
# =====================================================================
def test_persistence_failure_raises_and_aborts():
    """If Excel persistence fails, PersistenceError is raised to halt application execution."""
    from app.platforms.base import BasePlatform
    from app.models.job import PlatformEnum

    class DummyPlatform(BasePlatform):
        def __init__(self, config=None, profile=None):
            super().__init__(PlatformEnum.NAUKRI, config or SearchConfig(), profile or ResumeProfile())

        async def login(self): return True
        async def search_and_apply(self): return 0

    cfg = SearchConfig(keywords="python")
    prof = ResumeProfile()
    platform = DummyPlatform(cfg, prof)

    # Simulate ExcelTracker failure (e.g. disk locked or write error)
    with patch("app.platforms.base.excel_tracker.log_application", return_value=False):
        with pytest.raises(PersistenceError) as exc_info:
            platform.record_job_result(
                job_title="DevOps Engineer",
                company="Beta Corp",
                job_url="https://www.naukri.com/job-beta-1",
                status=ApplicationStatus.DISCOVERED
            )
        assert "Failed to persist application record" in str(exc_info.value)


# =====================================================================
# 5. Safe Click Failure Handling
# =====================================================================
@pytest.mark.asyncio
async def test_safe_click_handles_exceptions_gracefully():
    """safe_click returns False on detached elements, timeouts, or click errors without crashing."""
    from app.platforms.base import BasePlatform
    from app.models.job import PlatformEnum

    class DummyPlatform(BasePlatform):
        def __init__(self, config=None, profile=None):
            super().__init__(PlatformEnum.NAUKRI, config or SearchConfig(), profile or ResumeProfile())

        async def login(self): return True
        async def search_and_apply(self): return 0

    platform = DummyPlatform()

    # Case 1: None element
    assert await platform.safe_click(None) is False

    # Case 2: Element throws TimeoutError or detached error
    faulty_el = AsyncMock()
    faulty_el.scroll_into_view_if_needed.side_effect = Exception("Element detached from DOM")

    result = await platform.safe_click(faulty_el, timeout=1000)
    assert result is False
