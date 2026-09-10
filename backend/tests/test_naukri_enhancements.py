import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import ValidationError

from app.models.job import SearchConfig, ResumeProfile
from app.platforms.naukri_helpers import (
    ApplicationType,
    ApplicationLimitDetected,
    classify_application,
    detect_application_limit,
    normalize_token,
    validate_llm_answer,
    build_naukri_search_url,
)


# =====================================================================
# 1. Pydantic Model & SearchConfig Validation
# =====================================================================
def test_search_config_freshness_valid():
    """Verify accepted freshness_days values {None, 1, 3, 7}."""
    cfg_none = SearchConfig(freshness_days=None)
    assert cfg_none.freshness_days is None

    cfg_1 = SearchConfig(freshness_days=1)
    assert cfg_1.freshness_days == 1

    cfg_3 = SearchConfig(freshness_days=3)
    assert cfg_3.freshness_days == 3

    cfg_7 = SearchConfig(freshness_days=7)
    assert cfg_7.freshness_days == 7

    assert cfg_3.quick_apply_only is True


def test_search_config_freshness_invalid():
    """Reject unverified or out-of-contract freshness values like 42."""
    with pytest.raises(ValidationError):
        SearchConfig(freshness_days=42)

    with pytest.raises(ValidationError):
        SearchConfig(freshness_days=10)


def test_resume_profile_zero_fabrication():
    """Default notice_period_days must be None (never fabricate default 15)."""
    profile = ResumeProfile()
    assert profile.custom_answers.get("notice_period_days") is None


# =====================================================================
# 2. Canonical URL Construction & Parameter Preservation
# =====================================================================
def test_build_naukri_search_url_preserves_parameters():
    """Verify URL builder preserves existing parameters and correctly applies jobAge."""
    base = "https://www.naukri.com/jobs?k=react&l=hyderabad&sort=recent"

    # Set freshness to 3 days
    url_3d = build_naukri_search_url(base, freshness_days=3)
    assert "k=react" in url_3d
    assert "l=hyderabad" in url_3d
    assert "sort=recent" in url_3d
    assert "jobAge=3" in url_3d

    # Update freshness to 1 day
    url_1d = build_naukri_search_url(url_3d, freshness_days=1)
    assert "jobAge=1" in url_1d
    assert "jobAge=3" not in url_1d

    # Clear freshness (None -> Any Time)
    url_none = build_naukri_search_url(url_1d, freshness_days=None)
    assert "jobAge" not in url_none
    assert "k=react" in url_none
    assert "l=hyderabad" in url_none
    assert "sort=recent" in url_none


# =====================================================================
# 3. Card Classification Precedence & Safety
# =====================================================================
@pytest.mark.asyncio
async def test_classify_quick_apply_card():
    """Card with Quick Apply button and no external indicators."""
    mock_card = AsyncMock()
    mock_card.inner_text.return_value = "Senior Frontend Developer - Tech Corp - Quick Apply"
    mock_card.inner_html.return_value = "<div class='tuple'><button class='apply-button'>Apply</button></div>"
    mock_card.query_selector.return_value = MagicMock()  # apply button found

    res = await classify_application(mock_card)
    assert res == ApplicationType.QUICK_APPLY


@pytest.mark.asyncio
async def test_classify_external_card():
    """Card with Company Site / external redirect indicator."""
    mock_card = AsyncMock()
    mock_card.inner_text.return_value = "Full Stack Engineer - Global Tech - Apply on company site"
    mock_card.inner_html.return_value = "<div class='tuple'><a class='company-apply'>Apply on Company Site</a></div>"
    mock_card.query_selector.return_value = None

    res = await classify_application(mock_card)
    assert res == ApplicationType.EXTERNAL


@pytest.mark.asyncio
async def test_classify_conflict_external_precedence():
    """
    CRITICAL CONFLICT TEST:
    Card with BOTH Quick Apply text and Company Site indicator.
    Precedence rule: EXTERNAL MUST WIN to prevent accidental ATS entrapment.
    """
    mock_card = AsyncMock()
    mock_card.inner_text.return_value = "React Developer - Quick Apply - Apply on company site"
    mock_card.inner_html.return_value = "<div class='tuple'><span class='external-apply'>Company Site</span></div>"
    mock_card.query_selector.return_value = MagicMock()

    res = await classify_application(mock_card)
    assert res == ApplicationType.EXTERNAL


@pytest.mark.asyncio
async def test_classify_unknown_card():
    """Card with no recognizable indicators -> UNKNOWN."""
    mock_card = AsyncMock()
    mock_card.inner_text.return_value = "Designer - Creative Studios - View Details"
    mock_card.inner_html.return_value = "<div class='tuple'><span>View</span></div>"
    mock_card.query_selector.return_value = None

    res = await classify_application(mock_card)
    assert res == ApplicationType.UNKNOWN


# =====================================================================
# 4. Application Loop Integration Test (5 Cards Simulation)
# =====================================================================
@pytest.mark.asyncio
async def test_application_loop_classification_pipeline():
    """
    Simulate processing 5 mock cards:
    [Quick Apply, External, Unknown, Quick Apply, Already Applied]
    Under quick_apply_only=True:
      - processed: 2
      - external skipped: 1
      - unknown skipped: 1
      - already applied skipped: 1
    """
    cards_data = [
        {"text": "Dev 1 - Quick Apply", "html": "<button>Apply</button>", "has_btn": True, "applied": False},
        {"text": "Dev 2 - Company Site", "html": "<span class='external-apply'>Redirect</span>", "has_btn": False, "applied": False},
        {"text": "Dev 3 - Unknown layout", "html": "<span>Random</span>", "has_btn": False, "applied": False},
        {"text": "Dev 4 - Quick Apply", "html": "<button>Apply</button>", "has_btn": True, "applied": False},
        {"text": "Dev 5 - Applied Card", "html": "<span class='applied'>Applied</span>", "has_btn": False, "applied": True},
    ]

    processed = 0
    external_skipped = 0
    unknown_skipped = 0
    already_applied_skipped = 0
    quick_apply_only = True

    for item in cards_data:
        # Check already applied badge
        if item["applied"]:
            already_applied_skipped += 1
            continue

        mock_elem = AsyncMock()
        mock_elem.inner_text.return_value = item["text"]
        mock_elem.inner_html.return_value = item["html"]
        mock_elem.query_selector.return_value = MagicMock() if item["has_btn"] else None

        app_type = await classify_application(mock_elem)

        if quick_apply_only and app_type != ApplicationType.QUICK_APPLY:
            if app_type == ApplicationType.EXTERNAL:
                external_skipped += 1
            elif app_type == ApplicationType.UNKNOWN:
                unknown_skipped += 1
            continue

        processed += 1

    assert processed == 2
    assert external_skipped == 1
    assert unknown_skipped == 1
    assert already_applied_skipped == 1


# =====================================================================
# 5. Questionnaire Safety & Strict Invariants
# =====================================================================
def test_normalize_token():
    """Normalize hyphens, whitespace, punctuation."""
    assert normalize_token("30-day") == "30 day"
    assert normalize_token("30 Days ") == "30 days"
    assert normalize_token("15_days") == "15 days"
    assert normalize_token(" immediate! ") == "immediate"


def test_validate_llm_answer_valid():
    """Valid ANSWERABLE with displayed option match."""
    displayed = ["Immediate", "15 Days", "30 Days"]
    res = {
        "status": "ANSWERABLE",
        "selected_option": "15 Days",
        "reason": "Candidate specified 15 days in profile"
    }
    assert validate_llm_answer(res, displayed) == "15 Days"

    # Case / punctuation normalization match
    res_norm = {
        "status": "ANSWERABLE",
        "selected_option": "15-days",
        "reason": "Normalized match"
    }
    assert validate_llm_answer(res_norm, displayed) == "15 Days"


def test_validate_llm_answer_not_in_displayed_options():
    """Option not displayed in UI must be rejected (do not click)."""
    displayed = ["Immediate", "15 Days", "30 Days"]
    res = {
        "status": "ANSWERABLE",
        "selected_option": "45 Days",  # NOT in displayed options!
        "reason": "Model hallucination"
    }
    assert validate_llm_answer(res, displayed) is None


def test_validate_llm_answer_schema_invariants():
    """Strict rejection of malformed status / selected_option combinations."""
    displayed = ["Immediate", "15 Days", "30 Days"]

    # Invariant 1: ANSWERABLE with null option -> rejected
    assert validate_llm_answer({"status": "ANSWERABLE", "selected_option": None}, displayed) is None

    # Invariant 2: UNANSWERABLE with proposed option -> rejected as malformed
    assert validate_llm_answer({"status": "UNANSWERABLE", "selected_option": "30 Days"}, displayed) is None

    # Invariant 3: AMBIGUOUS with proposed option -> rejected as malformed
    assert validate_llm_answer({"status": "AMBIGUOUS", "selected_option": "15 Days"}, displayed) is None

    # Valid UNANSWERABLE with null -> safely returns None (do not click)
    assert validate_llm_answer({"status": "UNANSWERABLE", "selected_option": None}, displayed) is None

    # Reason is ignored and not treated as evidence
    assert validate_llm_answer({"status": "UNANSWERABLE", "selected_option": None, "reason": "Trusted candidate evidence"}, displayed) is None


# =====================================================================
# 6. Dynamic Limit Detection
# =====================================================================
@pytest.mark.asyncio
async def test_detect_application_limit_found():
    """Detect dynamic application limit banner."""
    mock_page = AsyncMock()
    mock_el = AsyncMock()
    mock_el.is_visible.return_value = True
    mock_el.inner_text.return_value = "You have reached your daily application limit on Naukri."
    mock_page.query_selector_all.return_value = [mock_el]
    mock_page.inner_text.return_value = ""

    reason = await detect_application_limit(mock_page)
    assert reason is not None
    assert "daily" in reason.lower() or "limit" in reason.lower()


@pytest.mark.asyncio
async def test_detect_application_limit_not_found():
    """No limit when page has regular content."""
    mock_page = AsyncMock()
    mock_page.query_selector_all.return_value = []
    mock_page.inner_text.return_value = "Welcome to Naukri Search. Apply to jobs."

    reason = await detect_application_limit(mock_page)
    assert reason is None


def test_application_limit_detected_exception():
    """ApplicationLimitDetected has reason attribute and descriptive string."""
    exc = ApplicationLimitDetected("Daily application quota reached")
    assert exc.reason == "Daily application quota reached"
    assert str(exc) == "Daily application quota reached"
