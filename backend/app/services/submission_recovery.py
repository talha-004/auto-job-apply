"""
Submission Recovery & Confirmation Engine.
Manages ambiguous submission states (SUBMISSION_UNKNOWN) when network timeouts occur.
Inspects confirmation receipts and prevents duplicate submissions.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.models.job import JobLifecycleStatus, ApplicationStatus, ReasonCode


class ReceiptConfidence(str, Enum):
    CONFIRMED = "confirmed"
    FAILED = "failed"
    UNKNOWN = "unknown"


class SubmissionReceipt(BaseModel):
    status: ReceiptConfidence
    evidence_text: Optional[str] = None
    suggested_status: JobLifecycleStatus
    reason_code: ReasonCode
    can_retry: bool = False


class SubmissionRecoveryManager:
    """
    Evaluates page state, text, and signals after a submission action or timeout.
    """

    CONFIRMATION_SIGNALS = [
        "application submitted",
        "your application was sent",
        "application received",
        "thank you for applying",
        "applied on",
        "application status: submitted",
        "we've received your application",
        "successfully submitted",
        "application sent"
    ]

    FAILURE_SIGNALS = [
        "there was an error submitting",
        "please fix the errors below",
        "submission failed",
        "required field is missing",
        "an error occurred",
        "try again later"
    ]

    @classmethod
    def evaluate_submission_state(
        cls,
        page_text: str,
        http_timed_out: bool = False,
        submit_button_visible: bool = False
    ) -> SubmissionReceipt:
        text_lower = page_text.lower() if page_text else ""

        # 1. Search for positive confirmation signals
        for signal in cls.CONFIRMATION_SIGNALS:
            if signal in text_lower:
                return SubmissionReceipt(
                    status=ReceiptConfidence.CONFIRMED,
                    evidence_text=f"Matched confirmation signal: '{signal}'",
                    suggested_status=JobLifecycleStatus.SUCCESS,
                    reason_code=ReasonCode.SUBMISSION_CONFIRMED,
                    can_retry=False
                )

        # 2. Search for explicit failure signals
        for failure_signal in cls.FAILURE_SIGNALS:
            if failure_signal in text_lower:
                return SubmissionReceipt(
                    status=ReceiptConfidence.FAILED,
                    evidence_text=f"Matched failure signal: '{failure_signal}'",
                    suggested_status=JobLifecycleStatus.FAILED,
                    reason_code=ReasonCode.SUBMISSION_FAILED,
                    can_retry=True
                )

        # 3. Timeout or Ambiguous State Handling
        if http_timed_out:
            return SubmissionReceipt(
                status=ReceiptConfidence.UNKNOWN,
                evidence_text="HTTP / Network timeout encountered while submitting form.",
                suggested_status=JobLifecycleStatus.SUBMISSION_UNKNOWN,
                reason_code=ReasonCode.SUBMISSION_UNKNOWN,
                can_retry=False  # Must verify before retrying to prevent duplicate applications
            )

        # If submit button is still visible and enabled with no confirmation
        if submit_button_visible:
            return SubmissionReceipt(
                status=ReceiptConfidence.UNKNOWN,
                evidence_text="Submit button still visible without confirmation screen.",
                suggested_status=JobLifecycleStatus.SUBMISSION_UNKNOWN,
                reason_code=ReasonCode.SAFE_CLICK_FAILED,
                can_retry=True
            )

        return SubmissionReceipt(
            status=ReceiptConfidence.UNKNOWN,
            evidence_text="Unrecognized post-submit page state.",
            suggested_status=JobLifecycleStatus.SUBMISSION_UNKNOWN,
            reason_code=ReasonCode.SUBMISSION_UNKNOWN,
            can_retry=False
        )


submission_recovery_manager = SubmissionRecoveryManager()
