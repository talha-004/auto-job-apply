"""
SmartRecruiters ATS Application Adapter.
Automates job application submissions on enterprise SmartRecruiters portals (*.smartrecruiters.com).
Handles candidate personal info, resume PDF upload, work experience, LinkedIn profile link,
custom screening questions via Fact Ledger / QA Vault, and submission verification.
"""

import re
import asyncio
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path

from app.core.config import settings
from app.core.logger import broadcaster, logger, LogLevel
from app.models.job import (
    ResumeProfile,
    QAVault,
    ApplicationStatus,
    ReasonCode
)
from app.platforms.adapter_interface import ApplicationAdapter, AdapterApplicationResult
from app.services.qa_vault_service import qa_vault_service


class SmartRecruitersAdapter(ApplicationAdapter):
    """
    Adapter for SmartRecruiters ATS application workflows (jobs.smartrecruiters.com/*).
    Supports personal info autofill, resume upload, screening questions, and verification.
    """

    SMARTRECRUITERS_SELECTORS = {
        "first_name": 'input[name="firstName"], input#first-name-input, [data-qa="first-name-input"]',
        "last_name": 'input[name="lastName"], input#last-name-input, [data-qa="last-name-input"]',
        "email": 'input[name="email"], input#email-input, [data-qa="email-input"]',
        "phone": 'input[name="phoneNumber"], input#phone-number-input, [data-qa="phone-number-input"]',
        "city": 'input[name="city"], input#city-input, [data-qa="location-input"]',
        "linkedin": 'input[name="web_site_url"], input[placeholder*="LinkedIn"], input[id*="linkedin"]',
        "resume_upload": 'input[type="file"], [data-qa="resume-upload"], input#resume-upload',
        "submit_button": 'button[data-qa="btn-submit"], button[type="submit"], button:has-text("Submit Application"), button:has-text("Submit")',
        "confirmation": '[data-qa="thank-you-message"], h2:has-text("Thank you"), div:has-text("application was successfully submitted"), div:has-text("Thank you for applying")'
    }

    def detect(self, url: str, page_content: Optional[str] = None) -> bool:
        """Detect SmartRecruiters portal by URL domain or embedded markup."""
        url_lower = url.lower()
        if "smartrecruiters.com" in url_lower or "jobs.smartrecruiters.com" in url_lower or "careers.smartrecruiters.com" in url_lower:
            return True
        if page_content:
            content_lower = page_content.lower()
            if 'data-qa="smartrecruiters"' in content_lower or 'data-qa="btn-submit"' in content_lower or 'smartrecruiters' in content_lower:
                return True
        return False

    async def authenticate(self) -> bool:
        """SmartRecruiters applications are public or link-based, no pre-auth credentials required."""
        return True

    async def extract_form(self, page: Any) -> Dict[str, Any]:
        """Extract all visible SmartRecruiters form fields."""
        fields: Dict[str, Any] = {
            "inputs": [],
            "has_file_upload": False,
            "has_submit_button": False
        }
        try:
            file_input = await page.query_selector(self.SMARTRECRUITERS_SELECTORS["resume_upload"])
            if file_input:
                fields["has_file_upload"] = True

            inputs = await page.query_selector_all("input:visible, textarea:visible")
            for inp in inputs:
                name = await inp.get_attribute("name") or await inp.get_attribute("id") or ""
                inp_type = await inp.get_attribute("type") or "text"
                if name:
                    fields["inputs"].append({"id": name, "type": inp_type})

            submit_btn = await page.query_selector(self.SMARTRECRUITERS_SELECTORS["submit_button"])
            if submit_btn:
                fields["has_submit_button"] = True

        except Exception as e:
            logger.warning(f"[SmartRecruitersAdapter] Error extracting form: {e}")

        return fields

    async def fill_form(
        self,
        page: Any,
        profile: ResumeProfile,
        qa_vault: QAVault,
        resume_pdf_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fill candidate info and attach resume PDF on SmartRecruiters form."""
        filled_fields: Dict[str, Any] = {}

        try:
            # 1. Attach Resume
            if resume_pdf_path and Path(resume_pdf_path).exists():
                file_input = await page.query_selector(self.SMARTRECRUITERS_SELECTORS["resume_upload"])
                if file_input:
                    await file_input.set_input_files(resume_pdf_path)
                    filled_fields["resume"] = resume_pdf_path
                    logger.info(f"[SmartRecruitersAdapter] Uploaded resume: {resume_pdf_path}")
                    await asyncio.sleep(1.0)

            # 2. First & Last Name
            first_name = profile.full_name.split()[0] if profile.full_name else ""
            last_name = " ".join(profile.full_name.split()[1:]) if len(profile.full_name.split()) > 1 else ""

            first_el = await page.query_selector(self.SMARTRECRUITERS_SELECTORS["first_name"])
            if first_el and first_name:
                await first_el.fill(first_name)
                filled_fields["first_name"] = first_name

            last_el = await page.query_selector(self.SMARTRECRUITERS_SELECTORS["last_name"])
            if last_el and last_name:
                await last_el.fill(last_name)
                filled_fields["last_name"] = last_name

            # 3. Email & Phone
            email_el = await page.query_selector(self.SMARTRECRUITERS_SELECTORS["email"])
            if email_el and profile.email:
                await email_el.fill(profile.email)
                filled_fields["email"] = profile.email

            phone_el = await page.query_selector(self.SMARTRECRUITERS_SELECTORS["phone"])
            if phone_el and profile.phone:
                await phone_el.fill(profile.phone)
                filled_fields["phone"] = profile.phone

            # 4. Location / City
            city_el = await page.query_selector(self.SMARTRECRUITERS_SELECTORS["city"])
            if city_el and profile.location:
                city = profile.location.split(",")[0].strip()
                await city_el.fill(city)
                filled_fields["city"] = city

            # 5. LinkedIn Profile URL
            linkedin_el = await page.query_selector(self.SMARTRECRUITERS_SELECTORS["linkedin"])
            if linkedin_el and getattr(profile, "linkedin_url", None):
                await linkedin_el.fill(profile.linkedin_url)
                filled_fields["linkedin"] = profile.linkedin_url

            # 6. Common screening questions via QA Vault
            screening_inputs = await page.query_selector_all("textarea, input[type='text']")
            for field in screening_inputs:
                label_text = await page.evaluate(
                    """(el) => {
                        const label = document.querySelector(`label[for="${el.id}"]`);
                        return label ? label.innerText : (el.placeholder || el.name || '');
                    }""",
                    field
                )
                if label_text and len(label_text.strip()) > 3:
                    ans, confidence = qa_vault_service.find_answer(qa_vault, label_text)
                    if ans:
                        await field.fill(ans)
                        filled_fields[label_text[:30]] = ans

        except Exception as e:
            logger.error(f"[SmartRecruitersAdapter] Error filling form: {e}")

        return filled_fields

    async def submit(self, page: Any) -> bool:
        """Clicks SmartRecruiters submit button."""
        try:
            submit_btn = await page.query_selector(self.SMARTRECRUITERS_SELECTORS["submit_button"])
            if submit_btn and await submit_btn.is_visible():
                await submit_btn.click()
                logger.info("[SmartRecruitersAdapter] Clicked Submit button.")
                await asyncio.sleep(3.0)
                return True
        except Exception as e:
            logger.error(f"[SmartRecruitersAdapter] Error submitting: {e}")
        return False

    async def verify_submission(self, page: Any) -> bool:
        """Verifies SmartRecruiters confirmation message or URL redirect."""
        try:
            await asyncio.sleep(2)
            page_text = (await page.inner_text("body")).lower()
            success_keywords = [
                "thank you for applying",
                "application was successfully submitted",
                "your application has been sent",
                "thank you for your interest"
            ]
            for kw in success_keywords:
                if kw in page_text:
                    return True

            conf_el = await page.query_selector(self.SMARTRECRUITERS_SELECTORS["confirmation"])
            if conf_el and await conf_el.is_visible():
                return True
        except Exception as e:
            logger.warning(f"[SmartRecruitersAdapter] Verification check exception: {e}")
        return False

    async def apply(
        self,
        page: Any,
        job_url: str,
        profile: ResumeProfile,
        qa_vault: QAVault,
        resume_pdf_path: Optional[str] = None
    ) -> AdapterApplicationResult:
        """Full end-to-end SmartRecruiters execution."""
        try:
            await page.goto(job_url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(2)

            filled = await self.fill_form(page, profile, qa_vault, resume_pdf_path=resume_pdf_path)
            submitted = await self.submit(page)

            if submitted and await self.verify_submission(page):
                return AdapterApplicationResult(
                    success=True,
                    status=ApplicationStatus.SUCCESS,
                    job_url=job_url,
                    reason_code=ReasonCode.SUBMISSION_CONFIRMED,
                    message="Successfully submitted application on SmartRecruiters.",
                    filled_fields=filled
                )
            elif submitted:
                return AdapterApplicationResult(
                    success=True,
                    status=ApplicationStatus.SUCCESS,
                    job_url=job_url,
                    reason_code=ReasonCode.SUBMISSION_UNKNOWN,
                    message="Submitted SmartRecruiters form, verification pending.",
                    filled_fields=filled
                )
            else:
                return AdapterApplicationResult(
                    success=False,
                    status=ApplicationStatus.FAILED,
                    job_url=job_url,
                    reason_code=ReasonCode.SUBMISSION_FAILED,
                    message="Could not click submit button on SmartRecruiters portal.",
                    filled_fields=filled
                )
        except Exception as e:
            return AdapterApplicationResult(
                success=False,
                status=ApplicationStatus.FAILED,
                job_url=job_url,
                reason_code=ReasonCode.SUBMISSION_FAILED,
                message=f"SmartRecruiters automation error: {str(e)}"
            )


smartrecruiters_adapter = SmartRecruitersAdapter()
