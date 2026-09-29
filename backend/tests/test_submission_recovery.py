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
