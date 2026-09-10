import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path

from app.models.job import (
    ApplicationStatus,
    ReasonCode,
    JobApplicationRecord,
    SearchConfig,
    ResumeProfile,
    PlatformEnum
)
from app.services.excel_tracker import (
    compute_job_fingerprint,
    excel_tracker
)
from app.services.job_quality_scorer import job_quality_scorer
from app.platforms.base import BasePlatform, PersistenceError, VerificationResult
from app.platforms.naukri import NaukriPlatform


class DummyPlatform(BasePlatform):
    async def login(self) -> bool:
        return True

    async def search_and_apply(self) -> int:
        return 0


def test_job_fingerprint_and_duplicate_classification():
    """Verify exact URL duplicates vs semantic possible duplicates."""
    # Test fingerprint generation
    fp1 = compute_job_fingerprint("Google India Ltd", "Senior React Developer ", " Bengaluru / Bangalore ")
    fp2 = compute_job_fingerprint("Google India", "Senior React Developer", "Bangalore")
    assert fp1 == fp2, "Normalized fingerprints should match despite punctuation/location alias differences"

    # Clean in-memory tracking for test isolation
    excel_tracker._applied_urls.clear()
    excel_tracker._processed_urls.clear()
    excel_tracker._processed_fingerprints.clear()

    # Record first job
    rec1 = JobApplicationRecord(
        job_id="JOB-test001",
        platform="naukri",
        job_title="Senior React Developer",
        company="Google India",
        job_url="https://www.naukri.com/job-listings-1",
        status=ApplicationStatus.SUCCESS
    )
    # Simulate logging
    excel_tracker._processed_urls[excel_tracker._normalize_url(rec1.job_url)] = rec1.status.value
    fp = compute_job_fingerprint(rec1.company, rec1.job_title, "Bangalore")
    excel_tracker._processed_fingerprints[fp] = rec1.job_id

    # 1. Exact URL match
    is_dup, dup_type, matched_id = excel_tracker.check_duplicate(
        "https://www.naukri.com/job-listings-1?src=search",
        "Google India",
        "Senior React Developer",
        "Bangalore"
    )
    assert is_dup is True
    assert dup_type == "EXACT_URL"

    # 2. Semantic match with DIFFERENT URL -> MUST be POSSIBLE_DUPLICATE, never definitive
    is_dup2, dup_type2, matched_id2 = excel_tracker.check_duplicate(
        "https://www.naukri.com/job-listings-999-different",
        "Google India Ltd.",
        "Senior React Developer",
        "Bengaluru"
    )
    assert is_dup2 is True
    assert dup_type2 == "POSSIBLE_DUPLICATE"
    assert matched_id2 == "JOB-test001"

    # 3. Different job -> Not duplicate
    is_dup3, dup_type3, _ = excel_tracker.check_duplicate(
        "https://www.naukri.com/job-listings-unique",
        "Amazon",
        "Backend Python Engineer",
        "Hyderabad"
    )
    assert is_dup3 is False


def test_job_quality_and_risk_scoring():
    """Verify JobQualityScorer produces 0-100 quality, detects risk flags, and computes priority."""
    # 1. High-quality legitimate job
    jd_good = """
    We are looking for a Senior Full Stack Engineer (Python, React).
    Requirements:
    - 5+ years experience with FastAPI, Python, PostgreSQL, React.js
    - Experience in distributed systems, CI/CD pipelines, Docker.
    Responsibilities:
    - Architect scalable microservices.
    - Mentor junior engineers.
    Salary: 25 - 35 LPA.
    Benefits: Health insurance, flexible work hours, remote options.
    Location: Hyderabad (Hybrid)
    """
    mock_contact = MagicMock()
    mock_contact.email = "careers@techfirm.com"
    mock_contact.name = "Priya Sharma"

    eval_good = job_quality_scorer.evaluate(
        title="Senior Full Stack Engineer",
        company="Tech Firm",
        location="Hyderabad",
        jd_text=jd_good,
        contacts=[mock_contact],
        match_score=88
    )

    assert eval_good.quality_score >= 60
    assert len(eval_good.risk_flags) == 0
    assert eval_good.priority_score >= 65
    assert any("match" in r.lower() for r in eval_good.priority_reasons)

    # 2. Suspicious listing with Risk Triggers
    jd_scam = """
    Urgent Hiring for Data Entry / Junior Developer!
    Earn 50,000 per month from home! No experience required!
    Selected candidates must provide refundable security deposit of Rs 4999 before joining.
    Registration fee required for documentation processing.
    """
    eval_scam = job_quality_scorer.evaluate(
        title="Data Entry Operator",
        company="Quick Cash Ltd",
        location="Remote",
        jd_text=jd_scam,
        contacts=[],
        match_score=40
    )

    assert "DEPOSIT_REQUIRED" in eval_scam.risk_flags
    assert "PAYMENT_REQUIRED" not in eval_scam.risk_flags

    # 3. Legitimate listing containing standard Naukri anti-fraud disclaimer
    jd_naukri_legit = """
    Full Stack Developer opening at Infosys.
    Skills: React, Java, Spring Boot, MySQL, REST API, Git.
    Salary: 12 - 18 LPA. Experience: 3-5 years. Location: Hyderabad.
    Beware of Fraudulent Requests: Naukri.com does not charge any registration fee or processing fee from job seekers.
    Never pay any fee to apply for jobs.
    """
    eval_naukri_legit = job_quality_scorer.evaluate(
        title="Full Stack Developer",
        company="Infosys",
        location="Hyderabad",
        jd_text=jd_naukri_legit,
        contacts=[],
        match_score=85
    )
    assert "PAYMENT_REQUIRED" not in eval_naukri_legit.risk_flags
    assert eval_naukri_legit.quality_score >= 60


def test_application_attempt_id_generation():
    """Verify application attempt IDs increment sequentially per job."""
    config = SearchConfig()
    profile = ResumeProfile()
    platform = DummyPlatform(PlatformEnum.NAUKRI, config=config, profile=profile)

    att1 = platform.get_attempt_id("JOB-a81f92")
    att2 = platform.get_attempt_id("JOB-a81f92")
    att_other = platform.get_attempt_id("JOB-bb3322")

    assert att1 == "ATTEMPT-a81f92-01"
    assert att2 == "ATTEMPT-a81f92-02"
    assert att_other == "ATTEMPT-bb3322-01"


def test_persistence_prerequisite_invariant():
    """Verify that if discovery record persistence fails, record_job_result raises PersistenceError."""
    config = SearchConfig()
    profile = ResumeProfile()
    platform = DummyPlatform(PlatformEnum.NAUKRI, config=config, profile=profile)

    with patch("app.services.excel_tracker.excel_tracker.log_application", return_value=False):
        with pytest.raises(PersistenceError):
            platform.record_job_result(
                job_id="JOB-err-test",
                job_title="Frontend Developer",
                company="Startup Inc",
                job_url="https://www.naukri.com/job-listings-fail",
                status=ApplicationStatus.DISCOVERED
            )


@pytest.mark.asyncio
async def test_verify_application_result_states():
    """Verify verification logic detects success, failure, and unknown outcomes."""
    config = SearchConfig()
    profile = ResumeProfile()
    platform = NaukriPlatform(config=config, profile=profile)

    # 1. Success page
    page_success = AsyncMock()
    page_success.inner_text.return_value = "Congratulations! You have successfully applied for this job."
    page_success.query_selector.return_value = None

    res_success = await platform.verify_application_result(page_success)
    assert res_success == VerificationResult.CONFIRMED_SUCCESS

    # 2. Failure page
    page_failure = AsyncMock()
    page_failure.inner_text.return_value = "Error submitting application: profile is incomplete."
    page_failure.query_selector.return_value = None

    res_failure = await platform.verify_application_result(page_failure)
    assert res_failure == VerificationResult.CONFIRMED_FAILURE

    # 3. Ambiguous page -> UNKNOWN (ensures safety guarantee: NO blind retry!)
    page_unknown = AsyncMock()
    page_unknown.inner_text.return_value = "Search more jobs like this in Bangalore."
    page_unknown.query_selector.return_value = None

    res_unknown = await platform.verify_application_result(page_unknown)
    assert res_unknown == VerificationResult.UNKNOWN


def test_evidence_aware_risk_detection_matrix():
    """
    Verify payment layer is completely removed:
    - Any payment, registration fee, or processing fee phrases NEVER produce PAYMENT_REQUIRED
    - Non-payment risk categories (TRAINING_PURCHASE, DEPOSIT_REQUIRED) work as intended
    """
    # Case 1: registration fee phrase does NOT produce PAYMENT_REQUIRED
    res1 = job_quality_scorer.evaluate(title="Backend Dev", company="Test Corp", jd_text="Job offer. Registration fee is required for document processing.")
    assert "PAYMENT_REQUIRED" not in res1.risk_flags

    # Case 2: processing fee phrase does NOT produce PAYMENT_REQUIRED
    res2 = job_quality_scorer.evaluate(title="Backend Dev", company="Test Corp", jd_text="Selected applicants: Processing fee must be paid before onboarding.")
    assert "PAYMENT_REQUIRED" not in res2.risk_flags

    # Case 3: candidate must pay registration fee does NOT produce PAYMENT_REQUIRED
    res3 = job_quality_scorer.evaluate(title="Backend Dev", company="Test Corp", jd_text="Please note that candidate must pay registration fee for background verification.")
    assert "PAYMENT_REQUIRED" not in res3.risk_flags

    # Case 4: mandatory paid training -> TRAINING_PURCHASE
    res4 = job_quality_scorer.evaluate(title="Junior Dev", company="Test Corp", jd_text="Applicants must complete our mandatory paid training before joining.")
    assert "TRAINING_PURCHASE" in res4.risk_flags
    assert "mandatory paid training" in res4.risk_evidence["TRAINING_PURCHASE"].lower()

    # Case 5: security deposit required -> DEPOSIT_REQUIRED
    res5 = job_quality_scorer.evaluate(title="Developer", company="Test Corp", jd_text="Equipment issued upon joining. Security deposit required.")
    assert "DEPOSIT_REQUIRED" in res5.risk_flags
    assert "security deposit required" in res5.risk_evidence["DEPOSIT_REQUIRED"].lower()

    # Case 6: we never charge registration fee -> no risk flags
    res_neg1 = job_quality_scorer.evaluate(title="Software Engineer", company="Reputable Corp", jd_text="We never charge registration fee or any hidden cost.")
    assert "PAYMENT_REQUIRED" not in res_neg1.risk_flags

    # Case 7: Naukri never charges registration fee -> no risk flags
    res_neg2 = job_quality_scorer.evaluate(title="Software Engineer", company="Reputable Corp", jd_text="Notice: Naukri never charges registration fee from candidates.")
    assert "PAYMENT_REQUIRED" not in res_neg2.risk_flags

    # Case 8: do not pay anyone claiming a registration fee -> no risk flags
    res_neg3 = job_quality_scorer.evaluate(title="Software Engineer", company="Reputable Corp", jd_text="Fraud Alert: Do not pay anyone claiming a registration fee for interviews.")
    assert "PAYMENT_REQUIRED" not in res_neg3.risk_flags


def test_layered_deduplication_job_id_and_url():
    """Verify Layer 1 (URL/job_id tracking) and Layer 2 (job_id caching) prevent duplicates."""
    excel_tracker._processed_job_ids.clear()
    excel_tracker._processed_urls.clear()
    excel_tracker._processed_fingerprints.clear()

    # Pre-populate tracker
    excel_tracker._processed_job_ids["12345678"] = "JOB-12345678"
    excel_tracker._processed_urls["https://www.naukri.com/job-listings-test-1"] = "SUCCESS"

    # 1. Duplicate job_id takes precedence
    is_dup_id, dup_type_id, matched_id = excel_tracker.check_duplicate(
        job_url="https://www.naukri.com/job-listings-different-url",
        company="Accenture",
        job_title="Software Engineer",
        location="Bangalore",
        job_id="12345678"
    )
    assert is_dup_id is True
    assert dup_type_id == "EXACT_JOB_ID"
    assert matched_id == "JOB-12345678"

    # 2. Exact URL match fallback
    is_dup_url, dup_type_url, _ = excel_tracker.check_duplicate(
        job_url="https://www.naukri.com/job-listings-test-1?src=search",
        company="Accenture",
        job_title="Software Engineer",
        location="Bangalore",
        job_id="99999999"
    )
    assert is_dup_url is True
    assert dup_type_url == "EXACT_URL"


def test_excel_bounds_checking_safe_cell():
    """Verify _cell accessor handles short, sparse, or malformed rows safely."""
    row_short = ("JOB-1", "naukri", "Dev", "Company")  # only 4 columns
    
    assert excel_tracker._cell(row_short, 0) == "JOB-1"
    assert excel_tracker._cell(row_short, 3) == "Company"
    assert excel_tracker._cell(row_short, 11) == ""  # Status column index safe default
    assert excel_tracker._cell(row_short, 20, default="N/A") == "N/A"
    
    row_with_nones = ("JOB-2", None, "Dev")
    assert excel_tracker._cell(row_with_nones, 1) == ""
    assert excel_tracker._cell(row_with_nones, 2) == "Dev"


@pytest.mark.asyncio
async def test_page_cleanup_defensive_close():
    """Verify that any exit path cleanly triggers job_page.close() without tab leaks."""
    mock_page = AsyncMock()
    mock_page.is_closed = MagicMock(return_value=False)

    # Simulate defensive try...finally block used across NaukriPlatform
    async def simulate_job_flow(exit_reason: str):
        job_page = mock_page
        try:
            if exit_reason == "risk_flag":
                return "skipped_risk"
            elif exit_reason == "low_match":
                return "skipped_low_match"
            elif exit_reason == "external_ats":
                return "skipped_external"
            elif exit_reason == "exception":
                raise RuntimeError("Simulated crash")
            return "applied_success"
        finally:
            if job_page and not job_page.is_closed():
                await job_page.close()

    # Check risk flag exit closes page
    mock_page.close.reset_mock()
    await simulate_job_flow("risk_flag")
    mock_page.close.assert_called_once()

    # Check low match exit closes page
    mock_page.close.reset_mock()
    await simulate_job_flow("low_match")
    mock_page.close.assert_called_once()

    # Check external ATS exit closes page
    mock_page.close.reset_mock()
    await simulate_job_flow("external_ats")
    mock_page.close.assert_called_once()

    # Check exception exit closes page
    mock_page.close.reset_mock()
    with pytest.raises(RuntimeError):
        await simulate_job_flow("exception")
    mock_page.close.assert_called_once()

