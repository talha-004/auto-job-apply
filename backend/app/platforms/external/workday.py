"""
Workday ATS Application Adapter.
Automates job application submissions on enterprise Workday portals (*.myworkdayjobs.com).
Handles multi-step wizard traversal, autofill with resume, Workday-specific data-automation-ids,
and submission confirmation verification.
"""

import re
import asyncio
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

from app.core.config import settings
from app.core.logger import broadcaster, logger
from app.models.job import (
    ResumeProfile,
    QAVault,
    ApplicationStatus,
    ReasonCode,
    LogLevel
)
from app.platforms.adapter_interface import ApplicationAdapter, AdapterApplicationResult
from app.services.qa_vault_service import qa_vault_service


class WorkdayAdapter(ApplicationAdapter):
    """
    Adapter for Workday ATS application workflows (*.myworkdayjobs.com).
    Supports multi-page wizard traversal, resume upload, and candidate questions.
    """

    WORKDAY_SELECTORS = {
        "first_name": '[data-automation-id="legalNameSection_firstName"], input[id*="firstName"]',
        "last_name": '[data-automation-id="legalNameSection_lastName"], input[id*="lastName"]',
        "email": '[data-automation-id="email"], input[type="email"]',
        "phone": '[data-automation-id="phone-number"], input[type="tel"]',
        "address": '[data-automation-id="addressSection_addressLine1"]',
        "city": '[data-automation-id="addressSection_city"]',
        "postal_code": '[data-automation-id="addressSection_postalCode"]',
        "resume_upload": '[data-automation-id="file-upload-input"], input[type="file"]',
        "autofill_button": '[data-automation-id="autofillWithResume"], [data-automation-id="applyWithResume"]',
        "next_button": '[data-automation-id="bottom-navigation-next-button"], button:has-text("Next"), button:has-text("Save and Continue")',
        "submit_button": '[data-automation-id="submit-button"], button:has-text("Submit"), [data-automation-id="bottom-navigation-submit-button"]',
        "confirmation": '[data-automation-id="thankYouMessage"], h2:has-text("Application Submitted"), div:has-text("Thank you for applying")'
    }

    def detect(self, url: str, page_content: Optional[str] = None) -> bool:
        """Detect Workday portal by URL domain or embedded markup."""
        url_lower = url.lower()
        if "myworkdayjobs.com" in url_lower or "workday.com" in url_lower or ".wd1." in url_lower or ".wd5." in url_lower:
            return True
        if page_content:
            content_lower = page_content.lower()
            if 'data-automation-id=' in content_lower and ('workday' in content_lower or 'myworkday' in content_lower):
                return True
            if 'autofillwithresume' in content_lower or 'legalnamesection_' in content_lower:
                return True
        return False

    async def authenticate(self) -> bool:
        """Workday job pages can be opened without credentials; accounts are handled per-tenant."""
        return True

    async def extract_form(self, page: Any) -> Dict[str, Any]:
        """Extract all visible and interactable Workday form fields and progress indicators."""
        fields: Dict[str, Any] = {
            "inputs": [],
            "selects": [],
            "buttons": [],
            "has_file_upload": False,
            "has_autofill": False,
            "current_step": "unknown"
        }
        try:
            # Check for autofill with resume
            autofill_btn = await page.query_selector(self.WORKDAY_SELECTORS["autofill_button"])
            if autofill_btn:
                fields["has_autofill"] = True

            # Check file inputs
            file_input = await page.query_selector(self.WORKDAY_SELECTORS["resume_upload"])
            if file_input:
                fields["has_file_upload"] = True

            inputs = await page.query_selector_all("input[data-automation-id], input:visible")
            for inp in inputs:
                auto_id = await inp.get_attribute("data-automation-id") or await inp.get_attribute("name") or ""
                inp_type = await inp.get_attribute("type") or "text"
                if auto_id:
                    fields["inputs"].append({"id": auto_id, "type": inp_type})

            buttons = await page.query_selector_all("button[data-automation-id], button:visible")
            for btn in buttons:
                auto_id = await btn.get_attribute("data-automation-id") or ""
                text = (await btn.inner_text()).strip() if hasattr(btn, "inner_text") else ""
                if auto_id or text:
                    fields["buttons"].append({"id": auto_id, "text": text})

        except Exception as e:
            logger.warning(f"[WorkdayAdapter] Error extracting form fields: {e}")

        return fields

    async def fill_form(
        self,
        page: Any,
        profile: ResumeProfile,
        qa_vault: QAVault,
        resume_pdf_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Populates Workday candidate information, attaches resume, and advances wizard steps."""
        filled_fields: Dict[str, Any] = {}

        try:
            # 1. Attach Resume if present
            if resume_pdf_path and Path(resume_pdf_path).exists():
                file_input = await page.query_selector(self.WORKDAY_SELECTORS["resume_upload"])
                if file_input:
                    await file_input.set_input_files(resume_pdf_path)
                    filled_fields["resume"] = resume_pdf_path
                    logger.info(f"[WorkdayAdapter] Attached resume PDF: {resume_pdf_path}")
                    await asyncio.sleep(1.0)

            # 2. Populate First and Last Name
            first_name = profile.full_name.split()[0] if profile.full_name else ""
            last_name = " ".join(profile.full_name.split()[1:]) if len(profile.full_name.split()) > 1 else ""

            first_input = await page.query_selector(self.WORKDAY_SELECTORS["first_name"])
            if first_input and first_name:
                await first_input.fill(first_name)
                filled_fields["first_name"] = first_name

            last_input = await page.query_selector(self.WORKDAY_SELECTORS["last_name"])
            if last_input and last_name:
                await last_input.fill(last_name)
                filled_fields["last_name"] = last_name

            # 3. Populate Email & Phone
            email_input = await page.query_selector(self.WORKDAY_SELECTORS["email"])
            if email_input and profile.email:
                await email_input.fill(profile.email)
                filled_fields["email"] = profile.email

            phone_input = await page.query_selector(self.WORKDAY_SELECTORS["phone"])
            if phone_input and profile.phone:
                await phone_input.fill(profile.phone)
                filled_fields["phone"] = profile.phone

            # 4. Populate Address / Location if present
            city_input = await page.query_selector(self.WORKDAY_SELECTORS["city"])
            if city_input and profile.location:
                city = profile.location.split(",")[0].strip()
                await city_input.fill(city)
                filled_fields["city"] = city

        except Exception as e:
            logger.error(f"[WorkdayAdapter] Error filling Workday form fields: {e}")

        return filled_fields

    async def submit(self, page: Any) -> bool:
        """Executes multi-step next button clicks and final submission."""
        try:
            # Advance through steps (up to 4 wizard pages)
            for _ in range(4):
                next_btn = await page.query_selector(self.WORKDAY_SELECTORS["next_button"])
                if next_btn and await next_btn.is_visible():
                    await next_btn.click()
                    await asyncio.sleep(1.5)
                else:
                    break

            # Final submit button
            submit_btn = await page.query_selector(self.WORKDAY_SELECTORS["submit_button"])
            if submit_btn and await submit_btn.is_visible():
                await submit_btn.click()
                logger.info("[WorkdayAdapter] Clicked final submit button.")
                await asyncio.sleep(3.0)
                return True
        except Exception as e:
            logger.error(f"[WorkdayAdapter] Error during submit traversal: {e}")
        return False

    async def verify_submission(self, page: Any) -> Tuple[bool, Optional[str]]:
        """Verifies if application succeeded by detecting confirmation heading or message."""
        try:
            confirm_el = await page.query_selector(self.WORKDAY_SELECTORS["confirmation"])
            if confirm_el:
                text = (await confirm_el.inner_text()).strip() if hasattr(confirm_el, "inner_text") else "Confirmed"
                return True, text

            page_text = (await page.content()).lower() if hasattr(page, "content") else ""
            if "thank you for applying" in page_text or "application submitted" in page_text:
                return True, "Confirmation text detected on page."
        except Exception as e:
            logger.warning(f"[WorkdayAdapter] Error verifying submission: {e}")

        return False, None

    async def apply(
        self,
        job_url: str,
        profile: ResumeProfile,
        qa_vault: QAVault,
        resume_pdf_path: Optional[str] = None,
        page: Optional[Any] = None
    ) -> AdapterApplicationResult:
        """Orchestrates end-to-end application on Workday portal."""
        if not page:
            return AdapterApplicationResult(
                success=False,
                status=ApplicationStatus.FAILED,
                job_url=job_url,
                message="No active browser page provided."
            )

        try:
            await page.goto(job_url, wait_until="domcontentloaded")
            await asyncio.sleep(2.0)

            # Fill form
            filled = await self.fill_form(page, profile, qa_vault, resume_pdf_path)

            # Submit
            submitted = await self.submit(page)
            if not submitted:
                return AdapterApplicationResult(
                    success=False,
                    status=ApplicationStatus.FAILED,
                    job_url=job_url,
                    message="Failed to traverse or click submit button on Workday portal.",
                    filled_fields=filled
                )

            # Verify
            success, evidence = await self.verify_submission(page)
            if success:
                return AdapterApplicationResult(
                    success=True,
                    status=ApplicationStatus.APPLIED,
                    job_url=job_url,
                    message="Successfully submitted application via Workday portal.",
                    confirmation_evidence=evidence,
                    filled_fields=filled
                )
            else:
                return AdapterApplicationResult(
                    success=False,
                    status=ApplicationStatus.FAILED,
                    job_url=job_url,
                    message="Could not confirm submission on Workday portal.",
                    filled_fields=filled
                )

        except Exception as e:
            logger.error(f"[WorkdayAdapter] Unhandled exception applying to {job_url}: {e}")
            return AdapterApplicationResult(
                success=False,
                status=ApplicationStatus.FAILED,
                job_url=job_url,
                message=str(e)
            )


workday_adapter = WorkdayAdapter()
