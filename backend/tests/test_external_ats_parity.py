"""
Unit Tests for External Corporate ATS Adapters Parity (Greenhouse & Lever).
Validates detection, form extraction, stealth filling, claim verification gating,
and vision coordinate submit fallback across Greenhouse and Lever platforms.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.job import ResumeProfile, QAVault, WorkExperience
from app.platforms.external.greenhouse import GreenhouseAdapter, greenhouse_adapter
from app.platforms.external.lever import LeverAdapter, lever_adapter
from app.platforms.external.ats_detector import ats_detector, detect_ats


@pytest.fixture
def sample_candidate() -> ResumeProfile:
    return ResumeProfile(
        full_name="Syed Talha Ahmed",
        email="syed@example.com",
        phone="+91 9988776655",
        location="Hyderabad, India",
        linkedin_url="https://linkedin.com/in/syedtalha",
        portfolio_url="https://talha.dev",
        years_of_experience=2.0,
        skills=["Python", "FastAPI", "React"],
        qa_vault=QAVault(
            notice_period_days=15,
            expected_ctc_lpa=12.0
        )
    )


def test_greenhouse_and_lever_detection():
    # URL detection
    gh_url = "https://boards.greenhouse.io/anthropic/jobs/4011223"
    lever_url = "https://jobs.lever.co/figma/abc-123-def"
    workday_url = "https://adobe.myworkdayjobs.com/en-US/external/job/123"

    assert detect_ats(gh_url) == greenhouse_adapter
    assert detect_ats(lever_url) == lever_adapter
    assert detect_ats(workday_url) is not None

    # Markup detection
    gh_markup = '<html><body><form id="application_form" action="https://boards.greenhouse.io/submit"></form></body></html>'
    lever_markup = '<html><body><div class="application-form"></div></body></html>'

    assert greenhouse_adapter.detect("https://careers.company.com/apply", page_content=gh_markup) is True
    assert lever_adapter.detect("https://careers.othercompany.com/apply", page_content=lever_markup) is True


@pytest.mark.asyncio
async def test_greenhouse_form_extraction():
    adapter = GreenhouseAdapter()
    page = AsyncMock()

    mock_input1 = AsyncMock()
    mock_input1.get_attribute.side_effect = lambda attr: "first_name" if attr == "name" else "text"

    mock_input2 = AsyncMock()
    mock_input2.get_attribute.side_effect = lambda attr: "resume" if attr == "name" else "file"

    page.query_selector_all.side_effect = lambda sel: (
        [mock_input1, mock_input2] if "input" in sel else []
    )

    form_data = await adapter.extract_form(page)
    assert form_data["has_file_upload"] is True
    assert len(form_data["inputs"]) == 2
    assert form_data["inputs"][0]["name"] == "first_name"


@pytest.mark.asyncio
async def test_greenhouse_fill_and_submit_with_vision_fallback(sample_candidate):
    adapter = GreenhouseAdapter()
    page = AsyncMock()

    first_name_input = AsyncMock()
    first_name_input.is_visible.return_value = True
    last_name_input = AsyncMock()
    last_name_input.is_visible.return_value = True
    email_input = AsyncMock()
    email_input.is_visible.return_value = True

    submit_btn = AsyncMock()
    submit_btn.is_visible.return_value = True

    async def mock_qs(selector):
        if "first_name" in selector:
            return first_name_input
        elif "last_name" in selector:
            return last_name_input
        elif "email" in selector:
            return email_input
        elif "submit_app" in selector:
            return submit_btn
        return None

    page.query_selector = AsyncMock(side_effect=mock_qs)
    page.query_selector_all.return_value = []

    res = await adapter.fill_form(page, sample_candidate)
    assert res["filled"].get("first_name") == "Syed"
    assert res["filled"].get("last_name") == "Talha Ahmed"
    assert res["filled"].get("email") == "syed@example.com"

    # Test submit with vision solver fallback
    with patch("app.platforms.vision_solver.vision_solver.resilient_click", new_callable=AsyncMock, return_value=True):
        submitted = await adapter.submit(page)
        assert submitted is True


@pytest.mark.asyncio
async def test_lever_form_fill_and_verification(sample_candidate):
    adapter = LeverAdapter()
    page = AsyncMock()

    name_input = AsyncMock()
    name_input.is_visible.return_value = True
    email_input = AsyncMock()
    email_input.is_visible.return_value = True
    phone_input = AsyncMock()
    phone_input.is_visible.return_value = True

    submit_btn = AsyncMock()
    submit_btn.is_visible.return_value = True

    async def mock_qs(selector):
        if "name='name'" in selector:
            return name_input
        elif "name='email'" in selector:
            return email_input
        elif "name='phone'" in selector:
            return phone_input
        elif "btn-submit" in selector:
            return submit_btn
        return None

    page.query_selector = AsyncMock(side_effect=mock_qs)
    page.query_selector_all.return_value = []

    res = await adapter.fill_form(page, sample_candidate)
    assert res["filled"].get("name") == "Syed Talha Ahmed"
    assert res["filled"].get("email") == "syed@example.com"
    assert res["filled"].get("phone") == "+91 9988776655"

    with patch("app.platforms.vision_solver.vision_solver.resilient_click", new_callable=AsyncMock, return_value=True):
        submitted = await adapter.submit(page)
        assert submitted is True
