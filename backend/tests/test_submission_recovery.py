import pytest
from app.models.job import JobLifecycleStatus, ApplicationStatus, ReasonCode
from app.services.submission_recovery import (
    SubmissionRecoveryManager,
    submission_recovery_manager,
    ReceiptConfidence,
)


def test_positive_confirmation_detection():
    """Verify that successful application messages are accurately recognized as confirmed."""
    page_html = """
    <div class="modal-content">
        <h2>Application Submitted!</h2>
        <p>Your application was sent to Stripe. Thank you for applying.</p>
    </div>
    """
    receipt = submission_recovery_manager.evaluate_submission_state(page_text=page_html)
    assert receipt.status == ReceiptConfidence.CONFIRMED
    assert receipt.suggested_status == JobLifecycleStatus.SUCCESS
    assert receipt.reason_code == ReasonCode.SUBMISSION_CONFIRMED
    assert receipt.can_retry is False
    assert "application submitted" in receipt.evidence_text.lower()


def test_failure_signal_detection():
    """Verify that form validation or submission errors are detected as retryable failures."""
    page_html = """
    <div class="error-banner">
        <span>Submission failed: A required field is missing. Please fix the errors below.</span>
    </div>
    """
    receipt = submission_recovery_manager.evaluate_submission_state(page_text=page_html)
    assert receipt.status == ReceiptConfidence.FAILED
    assert receipt.suggested_status == JobLifecycleStatus.FAILED
    assert receipt.reason_code == ReasonCode.SUBMISSION_FAILED
    assert receipt.can_retry is True


def test_network_timeout_triggers_submission_unknown():
    """Verify that a network timeout sets state to SUBMISSION_UNKNOWN and forbids blind retries."""
    receipt = submission_recovery_manager.evaluate_submission_state(
        page_text="",
        http_timed_out=True
    )
    assert receipt.status == ReceiptConfidence.UNKNOWN
    assert receipt.suggested_status == JobLifecycleStatus.SUBMISSION_UNKNOWN
    assert receipt.reason_code == ReasonCode.SUBMISSION_UNKNOWN
    assert receipt.can_retry is False  # Forbid automatic retry without confirmation check!


def test_granular_14_states_integrity():
    """Verify that all 14 granular lifecycle states are defined and valid."""
    expected_states = [
        "DISCOVERED", "EVALUATING", "ANALYZED", "ELIGIBLE", "PREPARING",
        "TAILORING", "FORM_ANALYSIS", "FILLING", "VALIDATING",
        "READY_TO_SUBMIT", "SUBMITTING", "CONFIRMATION_PENDING",
        "SUBMITTED", "SUCCESS", "APPLIED", "SKIPPED", "MANUAL_REVIEW",
        "FAILED", "SUBMISSION_UNKNOWN", "POSSIBLE_DUPLICATE"
    ]
    for s in expected_states:
        assert hasattr(JobLifecycleStatus, s)
        assert JobLifecycleStatus(s).value == s


@pytest.mark.asyncio
async def test_safe_step_advance_immediate_success():
    """Verify safe_step_advance returns True immediately when URL advances."""
    from unittest.mock import AsyncMock, MagicMock
    mock_page = MagicMock()
    mock_page.url = "https://boards.greenhouse.io/job/apply/step-1"
    mock_page.click = AsyncMock()

    mock_btn = AsyncMock()
    mock_btn.click = AsyncMock()

    # Change URL on click
    async def simulate_click(*args, **kwargs):
        mock_page.url = "https://boards.greenhouse.io/job/apply/step-2"

    mock_btn.click.side_effect = simulate_click

    advanced = await submission_recovery_manager.safe_step_advance(
        page=mock_page,
        button_target=mock_btn,
        timeout_seconds=2.0
    )

    assert advanced is True
    mock_btn.click.assert_called_once()


@pytest.mark.asyncio
async def test_safe_step_advance_self_healing_recovery():
    """Verify safe_step_advance executes scroll-into-view, focus, and Enter fallback when click stalls."""
    from unittest.mock import AsyncMock, MagicMock
    mock_page = MagicMock()
    mock_page.url = "https://workday.com/apply/page1"
    mock_page.keyboard = MagicMock()
    mock_page.keyboard.press = AsyncMock()

    mock_btn = MagicMock()
    mock_btn.click = AsyncMock()  # Click happens but page stalls
    mock_btn.is_visible = AsyncMock(return_value=True)
    mock_btn.scroll_into_view_if_needed = AsyncMock()
    mock_btn.focus = AsyncMock()

    # Keyboard Enter succeeds in transitioning page
    async def simulate_enter(key):
        if key == "Enter":
            mock_page.url = "https://workday.com/apply/page2"

    mock_page.keyboard.press.side_effect = simulate_enter

    advanced = await submission_recovery_manager.safe_step_advance(
        page=mock_page,
        button_target=mock_btn,
        timeout_seconds=2.0
    )

    assert advanced is True
    mock_btn.scroll_into_view_if_needed.assert_called_once()
    mock_btn.focus.assert_called_once()
    mock_page.keyboard.press.assert_called_once_with("Enter")


@pytest.mark.asyncio
async def test_safe_step_advance_clean_timeout():
    """Verify safe_step_advance cleanly returns False when broken portal does not advance."""
    from unittest.mock import AsyncMock, MagicMock
    mock_page = MagicMock()
    mock_page.url = "https://brokenportal.com/stalled"
    mock_page.keyboard = MagicMock()
    mock_page.keyboard.press = AsyncMock()

    mock_btn = MagicMock()
    mock_btn.click = AsyncMock()
    mock_btn.is_visible = AsyncMock(return_value=True)
    mock_btn.scroll_into_view_if_needed = AsyncMock()
    mock_btn.focus = AsyncMock()

    advanced = await submission_recovery_manager.safe_step_advance(
        page=mock_page,
        button_target=mock_btn,
        timeout_seconds=1.5
    )

    assert advanced is False

