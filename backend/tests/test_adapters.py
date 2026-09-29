"""
Unit and integration tests for ApplicationAdapter and External ATS Adapters (Phase 5).
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.models.job import (
    ResumeProfile,
    WorkExperience,
    QAVault,
    ApplicationStatus,
    PlatformEnum,
    SearchConfig
)
from app.platforms.adapter_interface import ApplicationAdapter, AdapterApplicationResult
from app.platforms.base import BasePlatform, VerificationResult
from app.platforms.external.greenhouse import GreenhouseAdapter, greenhouse_adapter
from app.platforms.external.lever import LeverAdapter, lever_adapter
from app.platforms.external.ats_detector import detect_ats, ats_detector


@pytest.fixture
def candidate_profile() -> ResumeProfile:
    return ResumeProfile(
        full_name="Syed Talha Ahmed",
        email="syedtalhaahmed004@gmail.com",
        phone="+91 81439 23984",
        location="Hyderabad, India",
        linkedin_url="https://linkedin.com/in/talha004",
        github_url="https://github.com/talha-004",
        portfolio_url="https://talha.dev",
        years_of_experience=2.0,
        skills=["React", "Node.js", "TypeScript", "Python"],
        work_experience=[
            WorkExperience(
                title="Software Developer Associate",
                company="Invertio Software Solutions"
            )
        ],
        qa_vault=QAVault(
            notice_period_days=15,
            expected_salary_inr="12 LPA",
            work_authorization="Yes",
            require_sponsorship="No"
        )
    )


def test_adapter_application_result_schema():
    """Verify AdapterApplicationResult model fields and defaults."""
    res = AdapterApplicationResult(
        success=True,
        status=ApplicationStatus.APPLIED,
        job_url="https://boards.greenhouse.io/demo/jobs/1",
        job_title="Full Stack Engineer",
        company="Demo Corp",
        message="Submitted successfully"
    )
    assert res.success is True
    assert res.status == ApplicationStatus.APPLIED
    assert res.job_url == "https://boards.greenhouse.io/demo/jobs/1"
    assert res.filled_fields == {}


def test_ats_detection_greenhouse_and_lever():
    """Verify ATS detection by URL and HTML markup."""
    # Greenhouse URLs
    gh_url = "https://boards.greenhouse.io/stripe/jobs/123456"
    assert greenhouse_adapter.detect(gh_url) is True
    assert detect_ats(gh_url) is greenhouse_adapter

    # Greenhouse markup detection
    assert greenhouse_adapter.detect("https://example.com/careers/1", page_content='<form id="application_form">') is True

    # Lever URLs
    lever_url = "https://jobs.lever.co/netflix/abcdef-1234"
    assert lever_adapter.detect(lever_url) is True
    assert detect_ats(lever_url) is lever_adapter

    # Lever markup detection
    assert lever_adapter.detect("https://company.com/apply", page_content='<div class="application-form">') is True

    # Unrecognized URL
    assert detect_ats("https://unknown-job-site.com/view/999") is None


@pytest.mark.asyncio
async def test_greenhouse_adapter_form_filling(candidate_profile):
    """Verify GreenhouseAdapter extracts and fills standard fields."""
    adapter = GreenhouseAdapter()

    # Mock Page and elements
    mock_page = AsyncMock()

    mock_first_name = AsyncMock()
    mock_first_name.is_visible.return_value = True

    mock_last_name = AsyncMock()
    mock_last_name.is_visible.return_value = True

    mock_email = AsyncMock()
    mock_email.is_visible.return_value = True

    mock_phone = AsyncMock()
    mock_phone.is_visible.return_value = True

    mock_linkedin = AsyncMock()
    mock_linkedin.is_visible.return_value = True

    def query_selector_side_effect(selector):
        if "first_name" in selector:
            return mock_first_name
        elif "last_name" in selector:
            return mock_last_name
        elif "email" in selector:
            return mock_email
        elif "phone" in selector:
            return mock_phone
        elif "linkedin" in selector:
            return mock_linkedin
        return None

    mock_page.query_selector = AsyncMock(side_effect=query_selector_side_effect)
    mock_page.query_selector_all = AsyncMock(return_value=[])

    result = await adapter.fill_form(mock_page, candidate_profile)

    assert "first_name" in result["filled"]
    assert result["filled"]["first_name"] == "Syed"
    assert "last_name" in result["filled"]
    assert result["filled"]["last_name"] == "Talha Ahmed"
    assert result["filled"]["email"] == "syedtalhaahmed004@gmail.com"
    assert result["filled"]["phone"] == "+91 81439 23984"


@pytest.mark.asyncio
async def test_lever_adapter_form_filling(candidate_profile):
    """Verify LeverAdapter fills standard fields and current organization."""
    adapter = LeverAdapter()

    mock_page = AsyncMock()

    mock_name = AsyncMock()
    mock_name.is_visible.return_value = True

    mock_email = AsyncMock()
    mock_email.is_visible.return_value = True

    mock_phone = AsyncMock()
    mock_phone.is_visible.return_value = True

    mock_org = AsyncMock()
    mock_org.is_visible.return_value = True

    def query_selector_side_effect(selector):
        if "name='name'" in selector:
            return mock_name
        elif "name='email'" in selector:
            return mock_email
        elif "name='phone'" in selector:
            return mock_phone
        elif "name='org'" in selector:
            return mock_org
        return None

    mock_page.query_selector = AsyncMock(side_effect=query_selector_side_effect)
    mock_page.query_selector_all = AsyncMock(return_value=[])

    result = await adapter.fill_form(mock_page, candidate_profile)

    assert result["filled"]["name"] == "Syed Talha Ahmed"
    assert result["filled"]["email"] == "syedtalhaahmed004@gmail.com"
    assert result["filled"]["phone"] == "+91 81439 23984"
    assert result["filled"]["org"] == "Invertio Software Solutions"


@pytest.mark.asyncio
async def test_submission_verification_greenhouse():
    """Verify Greenhouse confirmation checks."""
    adapter = GreenhouseAdapter()

    # Confirmed via element
    mock_page_success = AsyncMock()
    mock_confirm_el = AsyncMock()
    mock_confirm_el.is_visible.return_value = True
    mock_page_success.query_selector = AsyncMock(return_value=mock_confirm_el)
    mock_page_success.url = "https://boards.greenhouse.io/demo/jobs/1"

    success, msg = await adapter.verify_submission(mock_page_success)
    assert success is True
    assert "confirmation received" in msg.lower()

    # Failed / not confirmed
    mock_page_fail = AsyncMock()
    mock_page_fail.query_selector = AsyncMock(return_value=None)
    mock_page_fail.url = "https://boards.greenhouse.io/demo/jobs/1"

    failed, fail_msg = await adapter.verify_submission(mock_page_fail)
    assert failed is False


@pytest.mark.asyncio
async def test_submission_verification_lever():
    """Verify Lever confirmation checks."""
    adapter = LeverAdapter()

    # Confirmed via redirect URL
    mock_page_redirect = AsyncMock()
    mock_page_redirect.query_selector = AsyncMock(return_value=None)
    mock_page_redirect.url = "https://jobs.lever.co/company/thanks"

    success, msg = await adapter.verify_submission(mock_page_redirect)
    assert success is True
    assert "redirected to confirmation" in msg.lower()


def test_base_platform_conforms_to_application_adapter(candidate_profile):
    """Verify BasePlatform subclasses inherit ApplicationAdapter correctly."""
    class DummyPlatform(BasePlatform):
        async def login(self) -> bool:
            return True
        async def search_and_apply(self) -> int:
            return 1

    config = SearchConfig()
    platform = DummyPlatform(PlatformEnum.LINKEDIN, config, candidate_profile)

    assert isinstance(platform, ApplicationAdapter)
    assert platform.detect("https://www.linkedin.com/jobs/view/123") is True
    assert platform.detect("https://www.naukri.com/job/456") is False
