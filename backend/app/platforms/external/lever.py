"""
Lever ATS Application Adapter.
Automates job application submissions on jobs.lever.co and embedded Lever postings.
"""

from typing import Dict, Any, Optional, Tuple, List

from app.core.config import settings
from app.core.logger import logger
from app.models.job import (
    ResumeProfile,
    QAVault,
    ApplicationStatus,
    ReasonCode,
)
from app.platforms.adapter_interface import ApplicationAdapter, AdapterApplicationResult
from app.services.qa_vault_service import qa_vault_service


class LeverAdapter(ApplicationAdapter):
    """
    Adapter for Lever ATS application workflows.
    Supports standard Lever job postings (jobs.lever.co/<company>/<id>/apply).
    """

    def detect(self, url: str, page_content: Optional[str] = None) -> bool:
        """Detect Lever posting by URL domain or application form markup."""
        url_lower = url.lower()
        if "lever.co" in url_lower:
            return True
        if page_content:
            content_lower = page_content.lower()
            if 'class="application-form"' in content_lower or 'action="https://jobs.lever.co' in content_lower:
                return True
        return False

    async def authenticate(self) -> bool:
        """Lever job postings are publicly accessible without authentication."""
        return True

    async def extract_form(self, page: Any) -> Dict[str, Any]:
        """Extract all visible and interactable form fields from the Lever form."""
        fields: Dict[str, Any] = {"inputs": [], "questions": []}
        try:
            inputs = await page.query_selector_all(".application-form input, form input")
            for inp in inputs:
                name = await inp.get_attribute("name") or await inp.get_attribute("id") or ""
                inp_type = await inp.get_attribute("type") or "text"
                if name:
                    fields["inputs"].append({"name": name, "type": inp_type})

            questions = await page.query_selector_all(".application-question")
            for q in questions:
                label_el = await q.query_selector(".application-label, label")
                if label_el:
                    txt = (await label_el.inner_text()).strip()
                    if txt:
                        fields["questions"].append(txt)
        except Exception as e:
            logger.warning(f"Error extracting Lever form: {e}")
        return fields

    async def fill_form(
        self,
        page: Any,
        profile: ResumeProfile,
        qa_vault: Optional[QAVault] = None
    ) -> Dict[str, Any]:
        """Fill all standard Lever fields and custom application questions."""
        filled: Dict[str, Any] = {}
        unfilled: List[str] = []

        vault = qa_vault or profile.qa_vault

        try:
            # 1. Full Name
            name_input = await page.query_selector("input[name='name']")
            if name_input and await name_input.is_visible():
                await name_input.fill(profile.full_name)
                filled["name"] = profile.full_name

            # 2. Email & Phone
            email_input = await page.query_selector("input[name='email']")
            if email_input and await email_input.is_visible():
                await email_input.fill(profile.email)
                filled["email"] = profile.email

            phone_input = await page.query_selector("input[name='phone']")
            if phone_input and await phone_input.is_visible():
                await phone_input.fill(profile.phone)
                filled["phone"] = profile.phone

            # 3. Current Company / Organization
            org_input = await page.query_selector("input[name='org']")
            if org_input and await org_input.is_visible():
                curr_org = ""
                if profile.work_experience:
                    curr_org = profile.work_experience[0].company
                if curr_org:
                    await org_input.fill(curr_org)
                    filled["org"] = curr_org

            # 4. Social Links (LinkedIn, GitHub, Portfolio)
            linkedin_input = await page.query_selector("input[name='urls[LinkedIn]']")
            if linkedin_input and await linkedin_input.is_visible() and profile.linkedin_url:
                await linkedin_input.fill(profile.linkedin_url)
                filled["urls[LinkedIn]"] = profile.linkedin_url

            github_input = await page.query_selector("input[name='urls[GitHub]']")
            if github_input and await github_input.is_visible() and profile.github_url:
                await github_input.fill(profile.github_url)
                filled["urls[GitHub]"] = profile.github_url

            portfolio_input = await page.query_selector("input[name='urls[Portfolio]'], input[name='urls[Other]']")
            if portfolio_input and await portfolio_input.is_visible() and profile.portfolio_url:
                await portfolio_input.fill(profile.portfolio_url)
                filled["urls[Portfolio]"] = profile.portfolio_url

            # 5. Resume File Upload
            resume_path = settings.RESUME_FILE_PATH
            if resume_path.exists():
                file_input = await page.query_selector("input[type='file'], input[name='resume']")
                if file_input:
                    await file_input.set_input_files(str(resume_path))
                    filled["resume"] = resume_path.name

            # 6. Additional Questions
            question_divs = await page.query_selector_all(".application-question")
            for q_div in question_divs:
                label_el = await q_div.query_selector(".application-label, label")
                if not label_el:
                    continue
                label_text = (await label_el.inner_text()).strip()

                inp = await q_div.query_selector("input[type='text'], textarea")
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
                                    logger.warning(f"[LeverAdapter] Skipping unverified claim for '{label_text}': {ans}")
                                    continue
                            except Exception:
                                pass
                            await inp.fill(str(ans))
                            filled[label_text] = ans

                # Select / radio groups
                radio_inputs = await q_div.query_selector_all("input[type='radio']")
                if radio_inputs:
                    labels = []
                    for r in radio_inputs:
                        r_label = await q_div.query_selector(f"label[for='{await r.get_attribute('id')}']")
                        if r_label:
                            labels.append((await r_label.inner_text()).strip())
                    
                    matched_opt = qa_vault_service.resolve_answer(label_text, options=labels, candidate_profile=profile)
                    if matched_opt:
                        for idx, lbl in enumerate(labels):
                            if lbl == matched_opt and idx < len(radio_inputs):
                                await radio_inputs[idx].check()
                                filled[label_text] = matched_opt
                                break

        except Exception as e:
            logger.error(f"Error filling Lever form: {e}")

        return {"filled": filled, "unfilled": unfilled}

    async def submit(self, page: Any) -> bool:
        """Click submit button on Lever application with vision coordinate fallback."""
        submit_selectors = [
            "#btn-submit",
            "button[type='submit']",
            "button:has-text('Submit application')",
            "button:has-text('Apply now')"
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
        """Verify successful submission on Lever."""
        confirmation_selectors = [
            ".application-confirmation",
            "div:has-text('Application submitted')",
            "h2:has-text('Thank you')"
        ]
        for sel in confirmation_selectors:
            el = await page.query_selector(sel)
            if el and await el.is_visible():
                return True, "Application confirmation received from Lever."

        current_url = page.url.lower()
        if "thanks" in current_url or "confirmation" in current_url:
            return True, f"Redirected to confirmation page: {page.url}"

        return False, "Could not confirm submission on Lever."

    async def apply(
        self,
        job_url: str,
        profile: ResumeProfile,
        qa_vault: Optional[QAVault] = None
    ) -> AdapterApplicationResult:
        """End-to-end Lever application processor."""
        return AdapterApplicationResult(
            success=False,
            status=ApplicationStatus.FAILED,
            job_url=job_url,
            message="Lever standalone apply requires an active browser Page instance."
        )


lever_adapter = LeverAdapter()
