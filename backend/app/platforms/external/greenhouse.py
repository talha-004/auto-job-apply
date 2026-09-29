"""
Greenhouse ATS Application Adapter.
Automates job application submissions on boards.greenhouse.io and embedded Greenhouse forms.
"""

import re
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


class GreenhouseAdapter(ApplicationAdapter):
    """
    Adapter for Greenhouse ATS application workflows.
    Supports standard Greenhouse job boards (boards.greenhouse.io/<company>/jobs/<id>)
    and iframe/embedded application forms.
    """

    def detect(self, url: str, page_content: Optional[str] = None) -> bool:
        """Detect Greenhouse board by URL domain or embedded form markup."""
        url_lower = url.lower()
        if "greenhouse.io" in url_lower:
            return True
        if page_content:
            content_lower = page_content.lower()
            if 'id="application_form"' in content_lower or 'action="https://boards.greenhouse.io' in content_lower:
                return True
            if 'data-mapped-field="greenhouse' in content_lower:
                return True
        return False

    async def authenticate(self) -> bool:
        """Greenhouse job boards are publicly accessible without authentication."""
        return True

    async def extract_form(self, page: Any) -> Dict[str, Any]:
        """Extract all visible and interactable form fields from the Greenhouse form."""
        fields: Dict[str, Any] = {"inputs": [], "selects": [], "has_file_upload": False}
        try:
            inputs = await page.query_selector_all("#application_form input, form input")
            for inp in inputs:
                name = await inp.get_attribute("name") or await inp.get_attribute("id") or ""
                inp_type = await inp.get_attribute("type") or "text"
                if inp_type == "file":
                    fields["has_file_upload"] = True
                if name:
                    fields["inputs"].append({"name": name, "type": inp_type})

            selects = await page.query_selector_all("#application_form select, form select")
            for sel in selects:
                name = await sel.get_attribute("name") or await sel.get_attribute("id") or ""
                if name:
                    fields["selects"].append(name)
        except Exception as e:
            logger.warning(f"Error extracting Greenhouse form: {e}")
        return fields

    async def fill_form(
        self,
        page: Any,
        profile: ResumeProfile,
        qa_vault: Optional[QAVault] = None
    ) -> Dict[str, Any]:
        """Fill all standard and custom Greenhouse fields using candidate profile and QA Vault."""
        filled: Dict[str, Any] = {}
        unfilled: List[str] = []

        vault = qa_vault or profile.qa_vault

        # 1. First & Last Name
        name_parts = (profile.full_name or "").strip().split(maxsplit=1)
        first_name = name_parts[0] if name_parts else ""
        last_name = name_parts[1] if len(name_parts) > 1 else first_name

        try:
            # Check unified name vs split first/last name
            first_name_input = await page.query_selector("#first_name, input[autocomplete='given-name']")
            last_name_input = await page.query_selector("#last_name, input[autocomplete='family-name']")
            
            if first_name_input and await first_name_input.is_visible():
                await first_name_input.fill(first_name)
                filled["first_name"] = first_name
            if last_name_input and await last_name_input.is_visible():
                await last_name_input.fill(last_name)
                filled["last_name"] = last_name

            # Fallback unified name
            name_input = await page.query_selector("#name, input[autocomplete='name']")
            if name_input and await name_input.is_visible() and "first_name" not in filled:
                await name_input.fill(profile.full_name)
                filled["name"] = profile.full_name

            # 2. Email & Phone
            email_input = await page.query_selector("#email, input[type='email']")
            if email_input and await email_input.is_visible():
                await email_input.fill(profile.email)
                filled["email"] = profile.email

            phone_input = await page.query_selector("#phone, input[type='tel']")
            if phone_input and await phone_input.is_visible():
                await phone_input.fill(profile.phone)
                filled["phone"] = profile.phone

            # 3. Resume File Upload
            resume_path = settings.RESUME_FILE_PATH
            if resume_path.exists():
                file_input = await page.query_selector("input[type='file'], input[data-qa='resume-upload']")
                if file_input:
                    await file_input.set_input_files(str(resume_path))
                    filled["resume"] = resume_path.name

            # 4. Social Links (LinkedIn, GitHub, Website)
            linkedin_input = await page.query_selector("input[id*='linkedin'], input[name*='linkedin' i]")
            if linkedin_input and await linkedin_input.is_visible() and profile.linkedin_url:
                await linkedin_input.fill(profile.linkedin_url)
                filled["linkedin"] = profile.linkedin_url

            website_input = await page.query_selector("input[id*='website'], input[name*='website' i], input[id*='portfolio']")
            if website_input and await website_input.is_visible() and profile.portfolio_url:
                await website_input.fill(profile.portfolio_url)
                filled["website"] = profile.portfolio_url

            # 5. Dynamic Questions and Select Fields
            field_divs = await page.query_selector_all(".field, [class*='field--']")
            for div in field_divs:
                label_el = await div.query_selector("label")
                if not label_el:
                    continue
                label_text = (await label_el.inner_text()).strip()

                # Check text inputs
                inp = await div.query_selector("input[type='text'], textarea")
                if inp and await inp.is_visible():
                    val = await inp.input_value()
                    if not val:
                        ans = qa_vault_service.resolve_answer(label_text, candidate_profile=profile)
                        if ans:
                            # Fact ledger zero-hallucination verification
                            try:
                                from app.services.claim_verifier import claim_verifier
                                v_res = claim_verifier.verify_claim(label_text, str(ans))
                                if not v_res.verified and v_res.confidence < 0.5:
                                    logger.warning(f"[GreenhouseAdapter] Skipping unverified claim for '{label_text}': {ans}")
                                    continue
                            except Exception:
                                pass
                            await inp.fill(str(ans))
                            filled[label_text] = ans

                # Check select dropdowns
                select_el = await div.query_selector("select")
                if select_el and await select_el.is_visible():
                    option_els = await select_el.query_selector_all("option")
                    options = []
                    for opt in option_els:
                        txt = (await opt.inner_text()).strip()
                        if txt:
                            options.append(txt)
                    
                    matched_opt = qa_vault_service.resolve_answer(label_text, options=options, candidate_profile=profile)
                    if matched_opt:
                        await select_el.select_option(label=str(matched_opt))
                        filled[label_text] = matched_opt

        except Exception as e:
            logger.error(f"Error filling Greenhouse form: {e}")

        return {"filled": filled, "unfilled": unfilled}

    async def submit(self, page: Any) -> bool:
        """Click submit button on Greenhouse form with vision coordinate fallback."""
        submit_selectors = [
            "#submit_app",
            "input[type='submit']",
            "button:has-text('Submit Application')",
            "button:has-text('Apply')",
            "#submit_application"
        ]
        for sel in submit_selectors:
            btn = await page.query_selector(sel)
            if btn and await btn.is_visible():
                try:
                    from app.platforms.vision_solver import vision_solver
                    clicked = await vision_solver.resilient_click(page, sel, timeout_ms=2500)
                    if clicked:
                        return True
                except Exception:
                    pass
                await btn.click()
                return True
        return False

    async def verify_submission(self, page: Any) -> Tuple[bool, str]:
        """Verify successful submission on Greenhouse."""
        # Check confirmation elements or thank you message
        confirmation_selectors = [
            "#application_confirmation",
            ".application-confirmation",
            "div:has-text('Thank you for applying')",
            "h1:has-text('Thank you')"
        ]
        for sel in confirmation_selectors:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                return True, "Application confirmation received from Greenhouse."

        current_url = page.url.lower()
        if "confirmation" in current_url or "thank_you" in current_url or "thanks" in current_url:
            return True, f"Redirected to confirmation page: {page.url}"

        return False, "Could not confirm submission on Greenhouse."

    async def apply(
        self,
        job_url: str,
        profile: ResumeProfile,
        qa_vault: Optional[QAVault] = None
    ) -> AdapterApplicationResult:
        """End-to-end Greenhouse application processor."""
        return AdapterApplicationResult(
            success=False,
            status=ApplicationStatus.FAILED,
            job_url=job_url,
            message="Greenhouse standalone apply requires an active browser Page instance."
        )


greenhouse_adapter = GreenhouseAdapter()
