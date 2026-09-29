import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.job import DiscoveredJob, DiscoveryConfig
from app.services.discovery.base import JobDiscoveryProvider
from app.services.discovery.jobspy_provider import JobSpyProvider
from app.services.discovery.discovery_manager import DiscoveryManager
from app.services.excel_tracker import excel_tracker


def test_discovered_job_schema():
    """Verify DiscoveredJob model serialization and defaults."""
    job = DiscoveredJob(
        job_id="JOB-abc12345",
        platform="LinkedIn",
        title="Full Stack Developer",
        company="TechCorp India",
        location="Hyderabad, India",
        job_url="https://www.linkedin.com/jobs/view/999888",
        description="Looking for React and FastAPI developer."
    )
    assert job.job_id == "JOB-abc12345"
    assert job.platform == "LinkedIn"
    assert job.is_remote is False
    assert job.currency == "INR"
    assert "discovered_at" in job.model_dump()


def test_discovery_config_defaults():
    """Verify default search parameters in DiscoveryConfig."""
    cfg = DiscoveryConfig()
    assert cfg.keywords == "Full Stack Developer"
    assert cfg.location == "India"
    assert "linkedin" in cfg.platforms
    assert "indeed" in cfg.platforms
    assert cfg.results_wanted == 25


@pytest.mark.asyncio
async def test_jobspy_provider_mock_scrape():
    """Verify JobSpyProvider correctly normalizes scrape_jobs DataFrame."""
    provider = JobSpyProvider()
    assert provider.provider_name == "JobSpy Fast Scraper"

    mock_row = {
        "title": "Senior Python Engineer",
        "company": "FastAPI Labs",
        "site": "linkedin",
        "location": "Remote",
        "job_url": "https://www.linkedin.com/jobs/view/11223344",
        "description": "Python, FastAPI, and Playwright experience required.",
        "is_remote": True,
        "date_posted": "2026-09-28",
        "min_amount": 1500000,
        "max_amount": 2500000,
        "currency": "INR",
        "job_type": "fulltime"
    }

    mock_df = MagicMock()
    mock_df.empty = False
    mock_df.iterrows.return_value = [(0, mock_row)]

    with patch("jobspy.scrape_jobs", return_value=mock_df):
        cfg = DiscoveryConfig(keywords="Python Engineer", location="Remote", results_wanted=5)
        results = await provider.discover(cfg)

        assert len(results) == 1
        job = results[0]
        assert job.title == "Senior Python Engineer"
        assert job.company == "FastAPI Labs"
        assert job.platform == "Linkedin"
        assert job.is_remote is True
        assert job.salary_min == 1500000.0


@pytest.mark.asyncio
async def test_jobspy_provider_fallback_on_error():
    """Verify that when scrape_jobs fails, provider executes resilient guest search fallback."""
    provider = JobSpyProvider()

    # Simulate scrape_jobs failure
    with patch("jobspy.scrape_jobs", side_effect=Exception("Network connection failed")):
        # Mock guest search fallback to return 1 listing
        mock_fallback = [
            DiscoveredJob(
                job_id="JOB-fallback01",
                platform="LinkedIn",
                title="Frontend Developer",
                company="WebCorp",
                location="India",
                job_url="https://www.linkedin.com/jobs/view/fallback01"
            )
        ]
        with patch.object(provider, "_run_linkedin_guest_search", new_callable=AsyncMock, return_value=mock_fallback):
            cfg = DiscoveryConfig(keywords="Frontend Developer")
            results = await provider.discover(cfg)
            assert len(results) == 1
            assert results[0].job_id == "JOB-fallback01"


@pytest.mark.asyncio
async def test_discovery_manager_deduplication():
    """Verify DiscoveryManager filters out duplicates using excel_tracker."""
    manager = DiscoveryManager()
    manager.clear_session_cache()

    class MockProvider(JobDiscoveryProvider):
        @property
        def provider_name(self) -> str:
            return "Mock Provider"

        async def discover(self, config: DiscoveryConfig):
            return [
                DiscoveredJob(
                    job_id="JOB-fresh01",
                    platform="LinkedIn",
                    title="React Developer",
                    company="Innovate Solutions",
                    location="Hyderabad",
                    job_url="https://www.linkedin.com/jobs/view/fresh01"
                ),
                DiscoveredJob(
                    job_id="JOB-dup01",
                    platform="Indeed",
                    title="React Developer",
                    company="Innovate Solutions",
                    location="Hyderabad",
                    job_url="https://www.indeed.com/viewjob?jk=dup01"
                )
            ]

    manager.providers = [MockProvider()]

    # Mock excel_tracker.check_duplicate to flag the second job as duplicate
    def mock_check_dup(job_url, company, job_title, location):
        if "dup01" in job_url:
            return True, "EXACT_URL", "JOB-dup01"
        return False, "NONE", None

    with patch.object(excel_tracker, "check_duplicate", side_effect=mock_check_dup):
        cfg = DiscoveryConfig()
        fresh_jobs = await manager.discover_jobs(cfg)

        assert len(fresh_jobs) == 1
        assert fresh_jobs[0].job_id == "JOB-fresh01"


def test_api_discover_endpoint():
    """Verify POST /api/bot/discover endpoint."""
    client = TestClient(app)

    mock_discovered = [
        DiscoveredJob(
            job_id="JOB-api01",
            platform="LinkedIn",
            title="Full Stack Engineer",
            company="Global Tech",
            location="Remote",
            job_url="https://www.linkedin.com/jobs/view/api01"
        )
    ]

    with patch("app.services.discovery.discovery_manager.discovery_manager.discover_jobs", new_callable=AsyncMock, return_value=mock_discovered):
        resp = client.post("/api/bot/discover", json={"keywords": "Full Stack Engineer", "location": "Remote"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["count"] == 1
        assert data["jobs"][0]["job_id"] == "JOB-api01"
