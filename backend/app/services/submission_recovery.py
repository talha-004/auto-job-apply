"""
Submission Recovery & Confirmation Engine.
Manages ambiguous submission states (SUBMISSION_UNKNOWN) when network timeouts occur.
Inspects confirmation receipts and prevents duplicate submissions.
"""

import asyncio
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from app.core.logger import logger
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

    @classmethod
    async def safe_step_advance(
        cls,
        page: Any,
        button_target: Any,
        timeout_seconds: float = 8.0,
        url_before: Optional[str] = None
    ) -> bool:
        """
        Executes a form progression click (Next, Continue, Review, Submit) and monitors
        for state advancement within timeout_seconds.
        If the page remains unchanged/stalled, triggers self-healing recovery:
        1. Scrolls the target element into the center of the viewport.
        2. Focuses the button element.
        3. Dispatches keyboard 'Enter' as a reliable fallback.
        Returns True if the form advanced or submit registered, False if stalled after recovery.
        """
        initial_url = url_before or getattr(page, "url", "")

        # 1. Primary Click Attempt
        try:
            if hasattr(button_target, "click"):
                await button_target.click(timeout=3000)
            elif isinstance(button_target, str) and hasattr(page, "click"):
                await page.click(button_target, timeout=3000)
        except Exception as e:
            logger.debug(f"[SubmissionRecovery] Primary click error on {button_target}: {e}")

        # 2. Wait up to timeout_seconds / 2 for natural mutation or navigation
        poll_interval = 0.5
        elapsed = 0.0
        half_timeout = max(2.0, timeout_seconds / 2.0)

        while elapsed < half_timeout:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval
            current_url = getattr(page, "url", "")
            if current_url and current_url != initial_url:
                return True

        # Check if button has disappeared or disabled (indicating form moved forward)
        try:
            if hasattr(button_target, "is_visible"):
                is_vis = await button_target.is_visible()
                if not is_vis:
                    return True
            elif isinstance(button_target, str) and hasattr(page, "is_visible"):
                is_vis = await page.is_visible(button_target)
                if not is_vis:
                    return True
        except Exception:
            pass

        # 3. Form is stalled: Trigger Self-Healing Recovery Sequence
        logger.info(f"[SubmissionRecovery] Form advance stalled after {elapsed:.1f}s. Triggering self-healing recovery...")
        try:
            # Step A: Scroll into view
            if hasattr(button_target, "scroll_into_view_if_needed"):
                await button_target.scroll_into_view_if_needed(timeout=2000)
            elif isinstance(button_target, str) and hasattr(page, "locator"):
                loc = page.locator(button_target).first
                if hasattr(loc, "scroll_into_view_if_needed"):
                    await loc.scroll_into_view_if_needed(timeout=2000)

            # Step B: Focus element
            if hasattr(button_target, "focus"):
                await button_target.focus(timeout=1000)
            elif isinstance(button_target, str) and hasattr(page, "locator"):
                loc = page.locator(button_target).first
                if hasattr(loc, "focus"):
                    await loc.focus(timeout=1000)

            # Step C: Dispatch keyboard Enter fallback
            if hasattr(page, "keyboard") and hasattr(page.keyboard, "press"):
                await page.keyboard.press("Enter")

            # Step D: Observe post-recovery state for remainder of timeout
            recovery_wait = max(2.0, timeout_seconds - elapsed)
            recovery_elapsed = 0.0
            while recovery_elapsed < recovery_wait:
                await asyncio.sleep(poll_interval)
                recovery_elapsed += poll_interval
                current_url = getattr(page, "url", "")
                if current_url and current_url != initial_url:
                    logger.info("[SubmissionRecovery] Self-healing recovery succeeded (URL advanced).")
                    return True

                # Check if button disappeared
                try:
                    if hasattr(button_target, "is_visible"):
                        if not (await button_target.is_visible()):
                            logger.info("[SubmissionRecovery] Self-healing recovery succeeded (button advanced).")
                            return True
                    elif isinstance(button_target, str) and hasattr(page, "is_visible"):
                        if not (await page.is_visible(button_target)):
                            logger.info("[SubmissionRecovery] Self-healing recovery succeeded (button advanced).")
                            return True
                except Exception:
                    pass
        except Exception as recovery_err:
            logger.debug(f"[SubmissionRecovery] Self-healing recovery fallback error: {recovery_err}")

        logger.warning(f"[SubmissionRecovery] Safe step advance failed to transition page within {timeout_seconds}s.")
        return False


submission_recovery_manager = SubmissionRecoveryManager()
