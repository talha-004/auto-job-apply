"""
Unit Tests for Phase 12 (Pillar 3): Workday ATS Application Adapter.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.platforms.external.workday import workday_adapter, WorkdayAdapter
from app.platforms.external.ats_detector import ats_detector
from app.models.job import ResumeProfile, QAVault


@pytest.fixture
def sample_profile():
    return ResumeProfile(
        full_name="Alex Morgan",
        email="alex.morgan@example.com",
        phone="+1 (555) 234-5678",
        location="Seattle, WA",
        years_of_experience=5.0,
        summary="Senior Software Engineer specializing in backend microservices.",
        skills=["Python", "FastAPI", "Docker", "AWS"]
    )


def test_workday_detection():
    # URL detection
    assert workday_adapter.detect("https://netflix.wd1.myworkdayjobs.com/en-US/jobs/job/Backend-Engineer_123") is True
    assert workday_adapter.detect("https://salesforce.myworkdayjobs.com/careers/job/Lead-Dev") is True
    assert workday_adapter.detect("https://amazon.jobs/en/jobs/1234") is False
    assert workday_adapter.detect("https://boards.greenhouse.io/stripe/jobs/123") is False

    # Markup detection
    markup = '<div data-automation-id="workdayApplication"><button data-automation-id="autofillWithResume">Autofill</button></div>'
    assert workday_adapter.detect("https://careers.company.com/job/123", page_content=markup) is True


def test_ats_detector_routes_to_workday():
    adapter = ats_detector.detect_adapter("https://target.wd5.myworkdayjobs.com/jobs/job_456")
    assert adapter is not None
    assert isinstance(adapter, WorkdayAdapter)


@pytest.mark.asyncio
async def test_workday_extract_form():
    mock_page = MagicMock()
    mock_autofill = MagicMock()
    mock_file = MagicMock()

    mock_inp = MagicMock()
    mock_inp.get_attribute = AsyncMock(side_effect=lambda attr: "legalNameSection_firstName" if attr == "data-automation-id" else "text")

    mock_btn = MagicMock()
    mock_btn.get_attribute = AsyncMock(return_value="bottom-navigation-next-button")
    mock_btn.inner_text = AsyncMock(return_value="Next")

    mock_page.query_selector = AsyncMock(side_effect=lambda sel: mock_autofill if "autofillWithResume" in sel else (mock_file if "file-upload" in sel else None))
    mock_page.query_selector_all = AsyncMock(side_effect=lambda sel: [mock_inp] if "input" in sel else ([mock_btn] if "button" in sel else []))

    form_data = await workday_adapter.extract_form(mock_page)
    assert form_data["has_autofill"] is True
    assert form_data["has_file_upload"] is True
    assert len(form_data["inputs"]) >= 1
    assert form_data["inputs"][0]["id"] == "legalNameSection_firstName"


@pytest.mark.asyncio
async def test_workday_fill_form(sample_profile):
    mock_page = MagicMock()
    mock_first = MagicMock()
    mock_first.fill = AsyncMock()
    mock_last = MagicMock()
    mock_last.fill = AsyncMock()
    mock_email = MagicMock()
    mock_email.fill = AsyncMock()
    mock_phone = MagicMock()
    mock_phone.fill = AsyncMock()
    mock_city = MagicMock()
    mock_city.fill = AsyncMock()

    def selector_router(sel):
        if "firstName" in sel:
            return mock_first
        elif "lastName" in sel:
            return mock_last
        elif "email" in sel:
            return mock_email
        elif "phone" in sel:
            return mock_phone
        elif "city" in sel:
            return mock_city
        return None

    mock_page.query_selector = AsyncMock(side_effect=selector_router)

    filled = await workday_adapter.fill_form(
        page=mock_page,
        profile=sample_profile,
        qa_vault=QAVault()
    )

    assert filled["first_name"] == "Alex"
    assert filled["last_name"] == "Morgan"
    assert filled["email"] == "alex.morgan@example.com"
    assert filled["phone"] == "+1 (555) 234-5678"
    assert filled["city"] == "Seattle"

    mock_first.fill.assert_awaited_with("Alex")
    mock_last.fill.assert_awaited_with("Morgan")
    mock_email.fill.assert_awaited_with("alex.morgan@example.com")


@pytest.mark.asyncio
async def test_workday_verify_submission():
    mock_page = MagicMock()
    mock_confirm_el = MagicMock()
    mock_confirm_el.inner_text = AsyncMock(return_value="Thank you for applying to Workday")
    mock_page.query_selector = AsyncMock(return_value=mock_confirm_el)

    success, evidence = await workday_adapter.verify_submission(mock_page)
    assert success is True
    assert "Thank you for applying" in evidence
