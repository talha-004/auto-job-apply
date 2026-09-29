import pytest
from app.services.job_fingerprinter import JobFingerprinter, job_fingerprinter


def test_company_normalization():
    """Verify company names are normalized across corporate designations and punctuation."""
    assert job_fingerprinter.normalize_company("Google, Inc.") == "google"
    assert job_fingerprinter.normalize_company("Stripe LLC") == "stripe"
    assert job_fingerprinter.normalize_company("Amazon Technologies Corp.") == "amazon"
    assert job_fingerprinter.normalize_company("Infosys Limited") == "infosys"
    assert job_fingerprinter.normalize_company("Microsoft") == "microsoft"


def test_title_normalization():
    """Verify job titles are normalized across common abbreviations and synonyms."""
    assert job_fingerprinter.normalize_title("Sr. Software Engineer") == "senior software engineer"
    assert job_fingerprinter.normalize_title("Senior SWE") == "senior software engineer"
    assert job_fingerprinter.normalize_title("Jr. Python Dev") == "junior python developer"
    assert job_fingerprinter.normalize_title("Full Stack Developer for Web") == "full stack developer web"


def test_location_normalization():
    """Verify location normalization maps remote synonyms to 'remote'."""
    assert job_fingerprinter.normalize_location("Remote") == "remote"
    assert job_fingerprinter.normalize_location("Work From Home - US") == "remote"
    assert job_fingerprinter.normalize_location("Anywhere in India") == "remote"
    assert job_fingerprinter.normalize_location("San Francisco, CA") == "san"


def test_url_normalization():
    """Verify tracking parameters and fragments are stripped from job URLs."""
    url1 = "https://www.linkedin.com/jobs/view/39201928?refId=a1b2c3&trackingId=xyz123&utm_source=email"
    url2 = "https://www.linkedin.com/jobs/view/39201928?origin=JOB_SEARCH_PAGE_JOB_CARD"
    url3 = "https://www.linkedin.com/jobs/view/39201928/#apply-now"

    clean1 = job_fingerprinter.normalize_url(url1)
    clean2 = job_fingerprinter.normalize_url(url2)
    clean3 = job_fingerprinter.normalize_url(url3)

    assert clean1 == "https://www.linkedin.com/jobs/view/39201928"
    assert clean2 == "https://www.linkedin.com/jobs/view/39201928"
    assert clean3 == "https://www.linkedin.com/jobs/view/39201928"


def test_canonical_fingerprint_deduplication():
    """Verify that identical jobs across different portals or URLs yield the same fingerprint."""
    fp1 = job_fingerprinter.generate_fingerprint(
        company="Datadog, Inc.",
        title="Sr. Python Engineer",
        location="Remote",
        job_url="https://linkedin.com/jobs/view/1001?tracking=123",
        description="We are seeking a senior python engineer to scale distributed telemetry pipelines."
    )

    fp2 = job_fingerprinter.generate_fingerprint(
        company="Datadog LLC",
        title="Senior Python Engineer",
        location="Work From Home",
        job_url="https://indeed.com/viewjob?jk=abc987",
        description="We are seeking a senior python engineer to scale distributed telemetry pipelines."
    )

    assert fp1 == fp2


def test_idempotency_key_generation():
    """Verify candidate-specific idempotency keys are deterministic and unique per candidate."""
    identity_a = job_fingerprinter.build_identity(
        candidate_id="candidate_123",
        company="Stripe",
        title="Software Engineer",
        location="Remote",
        job_url="https://stripe.com/jobs/123",
        description="Building payment APIs."
    )

    identity_b = job_fingerprinter.build_identity(
        candidate_id="candidate_123",
        company="Stripe Inc",
        title="SWE",
        location="Remote",
        job_url="https://stripe.com/jobs/123?utm_medium=referral",
        description="Building payment APIs."
    )

    identity_c = job_fingerprinter.build_identity(
        candidate_id="candidate_456",
        company="Stripe",
        title="Software Engineer",
        location="Remote",
        job_url="https://stripe.com/jobs/123",
        description="Building payment APIs."
    )

    # Same candidate + same job fingerprint => identical idempotency key
    assert identity_a.idempotency_key == identity_b.idempotency_key
    # Different candidate => different idempotency key
    assert identity_a.idempotency_key != identity_c.idempotency_key
