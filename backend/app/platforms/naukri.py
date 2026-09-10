import asyncio
import json
import urllib.parse
import hashlib
from typing import Optional
from playwright.async_api import Page
from app.core.config import settings
from app.core.logger import broadcaster, logger
from app.core.llm import llm_client
from app.models.job import PlatformEnum, ApplicationStatus, LogLevel, ReasonCode, JobLifecycleStatus
from app.platforms.base import BasePlatform, PersistenceError, VerificationResult
from app.platforms.naukri_helpers import (
    ApplicationType,
    classify_application,
    ApplicationLimitDetected,
    detect_application_limit,
    normalize_token,
    validate_llm_answer,
    build_naukri_search_url,
    JobContact,
    extract_job_contacts,
)
from app.services.excel_tracker import excel_tracker
from app.services.match_scorer import match_scorer
from app.services.job_quality_scorer import job_quality_scorer


class NaukriPlatform(BasePlatform):
    def __init__(self, *args, **kwargs):
        super().__init__(PlatformEnum.NAUKRI, *args, **kwargs)
        self.base_url = "https://www.naukri.com"
        self.seen_jobs_this_run = set()
        self.seen_urls_this_run = set()

    async def verify_application_result(self, target_page: Page) -> VerificationResult:
        """Inspect Naukri page for post-apply confirmation or failure signals."""
        try:
            await asyncio.sleep(2)
            page_text = (await target_page.inner_text("body")).lower()

            # 1. Success signals in page text
            success_indicators = [
                "successfully applied",
                "application submitted",
                "your application has been sent",
                "already applied",
                "applied successfully",
                "you have applied",
                "application sent",
                "successfully sent",
                "thank you for applying",
                "applied to this job",
                "applied on",
            ]
            for phrase in success_indicators:
                if phrase in page_text:
                    return VerificationResult.CONFIRMED_SUCCESS

            # 2. Check applied button state on page
            applied_btn = await target_page.query_selector(
                "button:has-text('Applied'), span:has-text('Applied'), div:has-text('Applied'), .styles_applied-text__2_U3C, .already-applied, .applied-tag, [class*='applied']"
            )
            if applied_btn and await applied_btn.is_visible():
                btn_txt = (await applied_btn.inner_text()).lower().strip()
                if "applied" in btn_txt:
                    return VerificationResult.CONFIRMED_SUCCESS

            # 3. Check toast or alert banner messages
            toast_elems = await target_page.query_selector_all(
                ".toast, .toaster-msg, .alert-success, div[class*='toast'], div[class*='Toast'], .success-msg, [role='status']"
            )
            for t in toast_elems:
                if await t.is_visible():
                    t_txt = (await t.inner_text()).lower()
                    if any(w in t_txt for w in ["applied", "submitted", "success", "sent"]):
                        return VerificationResult.CONFIRMED_SUCCESS

            # 4. Failure signals
            failure_indicators = [
                "daily application limit reached",
                "error submitting application",
                "access denied",
                "something went wrong"
            ]
            for phrase in failure_indicators:
                if phrase in page_text:
                    return VerificationResult.CONFIRMED_FAILURE

            return VerificationResult.UNKNOWN
        except Exception as e:
            logger.debug(f"Error inspecting application verification result: {e}")
            return VerificationResult.UNKNOWN

    async def is_logged_in(self) -> bool:
        """Verify Naukri login status."""
        try:
            await self.page.goto(f"{self.base_url}/nlogin/login", wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(2)
            
            # If redirected away from login page to homepage or profile, user is logged in
            if "/nlogin/login" not in self.page.url and ("mnjuser" in self.page.url or "homepage" in self.page.url):
                if await self.page.query_selector(".nI-gNb-drawer__user-name, .view-profile-wrapper, a[href*='/mnjuser/profile']"):
                    return True

            # If login inputs are present on page, user is NOT logged in
            if await self.page.query_selector("input[placeholder*='Email'], #usernameField, .nI-gNb-header__login-btn"):
                return False
        except Exception as e:
            logger.warning(f"Error checking Naukri login status: {e}")
        return False

    async def login(self) -> bool:
        """Authenticate on Naukri using saved cookies or credentials."""
        await broadcaster.emit_log("Authenticating on Naukri...", platform=self.platform_name.value)
        
        if await self.is_logged_in():
            await broadcaster.emit_log("Reused valid Naukri session from cookies.", level=LogLevel.SUCCESS, platform=self.platform_name.value)
            return True

        email = settings.NAUKRI_EMAIL
        password = settings.NAUKRI_PASSWORD

        if not email or not password:
            await broadcaster.emit_log("No NAUKRI_EMAIL / NAUKRI_PASSWORD found in .env.", level=LogLevel.WARNING, platform=self.platform_name.value)
            return False

        try:
            await self.page.goto(f"{self.base_url}/nlogin/login", wait_until="domcontentloaded", timeout=30000)
            await self.human_delay(1.5, 2.5)

            email_input = await self.page.query_selector("input[placeholder*='Email'], #usernameField")
            pwd_input = await self.page.query_selector("input[type='password'], #passwordField")

            if email_input and pwd_input:
                await broadcaster.emit_log("Entering Naukri login credentials...", platform=self.platform_name.value)
                await self.human_type(email_input, email)
                await self.human_delay(0.5, 1.0)
                await self.human_type(pwd_input, password)
                await self.human_delay(0.5, 1.2)

                submit_btn = await self.page.query_selector("button[type='submit'], .btn-primary, button:has-text('Login')")
                if submit_btn:
                    await submit_btn.click()

            await self.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(4)

            # Check for OTP / Security Check
            if await self.check_for_captcha() or await self.page.query_selector("input[placeholder*='OTP'], .otp-container, input[type='tel']"):
                await broadcaster.emit_log(
                    "🔐 Naukri OTP verification challenge detected! Please enter OTP in browser, then resume bot.",
                    level=LogLevel.WARNING,
                    platform=self.platform_name.value
                )
                if self.pause_event:
                    self.pause_event.clear()
                await self.check_pause_and_stop()

            await asyncio.sleep(3)

            if "nlogin" not in self.page.url or await self.page.query_selector(".nI-gNb-drawer, a[href*='/mnjuser/profile'], .view-profile-wrapper"):
                await self._save_cookies()
                await broadcaster.emit_log("Successfully logged in to Naukri!", level=LogLevel.SUCCESS, platform=self.platform_name.value)
                return True
            else:
                await broadcaster.emit_log("Naukri login in progress. If browser is open, please complete login.", level=LogLevel.WARNING, platform=self.platform_name.value)
                await asyncio.sleep(5)
                if "nlogin" not in self.page.url:
                    await self._save_cookies()
                    return True
                return False

        except Exception as e:
            await broadcaster.emit_log(f"Naukri login error: {e}", level=LogLevel.ERROR, platform=self.platform_name.value)
            return False

    async def handle_naukri_chatbot(self, job_page: Page, job_title: str, company: str) -> bool:
        """
        Two-tier questionnaire solver for Naukri Quick Apply chatbot drawer.
        Tier 1: Deterministic matching from candidate profile custom answers.
        Tier 2: Constrained LLM fallback with strict displayed-option validation & zero fabrication.
        """
        max_rounds = 5
        round_count = 0
        while round_count < max_rounds:
            round_count += 1
            chat_modal = None
            modal_selectors = [
                ".chatbot_Drawer",
                ".apply-drawer",
                "div[class*='chatbot']",
                ".drawer-wrapper",
                "div[class*='drawer']",
                "div[class*='Drawer']",
                "div[class*='applyDrawer']",
                ".applyDrawer",
                "div[role='dialog']",
                ".modal-container",
                ".modal",
                "[class*='apply-modal']",
                ".apply-message"
            ]
            for sel in modal_selectors:
                el = await job_page.query_selector(sel)
                if el and await el.is_visible():
                    chat_modal = el
                    break

            if not chat_modal and round_count == 1:
                # Wait up to 3 seconds on round 1 for drawer animation
                for _ in range(3):
                    await asyncio.sleep(1)
                    for sel in modal_selectors:
                        el = await job_page.query_selector(sel)
                        if el and await el.is_visible():
                            chat_modal = el
                            break
                    if chat_modal:
                        break

            if not chat_modal:
                break

            # Boundary check: platform limit inside chatbot
            limit_reason = await detect_application_limit(job_page)
            if limit_reason:
                raise ApplicationLimitDetected(limit_reason)

            # 1. Fill standard inputs using local AI form mapping
            await self.fill_form_with_llm(job_title, company, target_page=job_page, container=chat_modal)

            # 2. Choice chips / questionnaire questions
            chips = await chat_modal.query_selector_all(".chip, .option-chip, .radio-chip, li.chip, .bot-option, .msg-choice")
            visible_chips = [c for c in chips if await c.is_visible()]

            if visible_chips:
                displayed_options = [(await c.inner_text()).strip() for c in visible_chips]
                question_elem = await chat_modal.query_selector(".bot-msg, .chat-msg, .question-text, .msgText, p.msg")
                question_text = (await question_elem.inner_text()).strip() if question_elem else ""
                q_lower = question_text.lower()

                chosen_chip = None

                # Tier 1: Deterministic resolution
                notice_period = self.profile.custom_answers.get("notice_period_days")
                if "notice" in q_lower and notice_period is not None:
                    norm_notice = normalize_token(f"{notice_period} days")
                    for idx, opt in enumerate(displayed_options):
                        if norm_notice == normalize_token(opt) or str(notice_period) in opt:
                            chosen_chip = visible_chips[idx]
                            break

                elif "authorization" in q_lower or "authorized" in q_lower:
                    auth = self.profile.custom_answers.get("work_authorization")
                    if auth:
                        norm_auth = normalize_token(auth)
                        for idx, opt in enumerate(displayed_options):
                            if norm_auth == normalize_token(opt):
                                chosen_chip = visible_chips[idx]
                                break

                elif "sponsorship" in q_lower:
                    spons = self.profile.custom_answers.get("require_sponsorship")
                    if spons:
                        norm_spons = normalize_token(spons)
                        for idx, opt in enumerate(displayed_options):
                            if norm_spons == normalize_token(opt):
                                chosen_chip = visible_chips[idx]
                                break

                # Tier 2: Constrained LLM fallback
                if not chosen_chip:
                    screening_context = {
                        "skills": self.profile.skills,
                        "years_experience": self.profile.years_of_experience,
                        "current_title": self.profile.work_experience[0].title if self.profile.work_experience else None,
                        "education": self.profile.education[0].degree if self.profile.education else None,
                        "notice_period_days": self.profile.custom_answers.get("notice_period_days"),
                        "location": self.profile.location or None,
                    }

                    prompt = (
                        f"Job: {job_title} at {company}\n"
                        f"Question: {question_text}\n"
                        f"Available Options: {displayed_options}\n"
                        f"Candidate Profile: {json.dumps(screening_context, default=str)}\n\n"
                        f"Task: Select the single option matching the candidate. Rules:\n"
                        f"1. Never fabricate information. If candidate context lacks the answer, return status 'UNANSWERABLE' and selected_option null.\n"
                        f"2. If status is 'ANSWERABLE', selected_option MUST exactly match one of the available options.\n"
                        f"3. Return strict JSON: {{\"status\": \"ANSWERABLE\" | \"UNANSWERABLE\" | \"AMBIGUOUS\", \"selected_option\": string | null, \"reason\": string}}."
                    )

                    try:
                        llm_res = await llm_client.generate_json(
                            prompt,
                            system_prompt="You are a strict screening questionnaire parser. Adhere strictly to the options and do not hallucinate candidate data."
                        )
                        validated_opt = validate_llm_answer(llm_res, displayed_options)
                        if validated_opt:
                            for idx, opt in enumerate(displayed_options):
                                if opt == validated_opt:
                                    chosen_chip = visible_chips[idx]
                                    break
                        else:
                            await broadcaster.emit_log(
                                f"Screening question skipped (unanswerable or unverified): '{question_text[:60]}...'",
                                platform=self.platform_name.value
                            )
                    except Exception as e:
                        logger.warning(f"Error evaluating screening question via LLM: {e}")

                if chosen_chip:
                    await chosen_chip.click()
                    await asyncio.sleep(1)

            # 3. Look for Submit / Save / Next inside chatbot
            advance_btn = await chat_modal.query_selector(
                "button:has-text('Submit'), button:has-text('Apply'), button:has-text('Save'), .save-btn, button:has-text('Next'), button:has-text('Send Application'), button:has-text('Confirm'), button:has-text('Done')"
            )
            if advance_btn and await advance_btn.is_visible():
                await advance_btn.click()
                await asyncio.sleep(2)
            else:
                page_advance = await job_page.query_selector(
                    "button:has-text('Submit Application'), button:has-text('Apply Now'), button:has-text('Confirm & Apply')"
                )
                if page_advance and await page_advance.is_visible():
                    await page_advance.click()
                    await asyncio.sleep(2)
                else:
                    break
        return True

    async def update_profile_headline(self, headline: str) -> bool:
        """
        Navigate to Naukri candidate profile and update the Resume Headline using authenticated session cookies.
        """
        headline = headline.strip() if headline else ""
        if not headline or len(headline) < 5 or len(headline) > 250:
            raise ValueError("Headline must be between 5 and 250 characters.")
        
        await broadcaster.emit_log("Navigating to Naukri profile to update headline...", platform=self.platform_name.value)
        profile_url = f"{self.base_url}/mnjuser/profile"
        await self.page.goto(profile_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        if "nlogin" in self.page.url:
            await broadcaster.emit_log("Session expired. Cannot update headline without active login.", level=LogLevel.ERROR, platform=self.platform_name.value)
            return False

        # Look for headline edit button
        edit_btn = await self.page.query_selector("span:has-text('Resume Headline') ~ span.edit, .resumeHeadline .edit, .widgetHead:has-text('Resume Headline') .edit, span.edit")
        if edit_btn:
            await edit_btn.click()
            await asyncio.sleep(1.5)

        textarea = await self.page.query_selector("textarea#resumeHeadlineTxt, .resumeHeadlineTxt, textarea[placeholder*='headline']")
        if textarea:
            await textarea.fill("")
            await self.human_type(textarea, headline)
            await asyncio.sleep(1)

            save_btn = await self.page.query_selector("button.btn-dark-ot:has-text('Save'), form button:has-text('Save'), .action button:has-text('Save'), button:has-text('Save')")
            if save_btn:
                await save_btn.click()
                await asyncio.sleep(2)
                await broadcaster.emit_log(f"Successfully updated Naukri profile headline to: '{headline}'", level=LogLevel.SUCCESS, platform=self.platform_name.value)
                return True

        await broadcaster.emit_log("Could not locate Resume Headline input on Naukri profile.", level=LogLevel.WARNING, platform=self.platform_name.value)
        return False

    async def search_and_apply(self) -> int:
        """Search jobs on Naukri and apply automatically with smart filtering and external portal support."""
        keywords_slug = self.config.keywords.lower().replace(" ", "-")
        location_slug = self.config.location.lower().replace(" ", "-")
        
        # Smart search URL construction with experience filter
        exp_param = f"&experience={self.config.experience_years}" if self.config.experience_years is not None else ""
        if location_slug and location_slug != "remote":
            raw_url = f"{self.base_url}/{keywords_slug}-jobs-in-{location_slug}?k={urllib.parse.quote(self.config.keywords)}&l={urllib.parse.quote(self.config.location)}{exp_param}"
        elif location_slug == "remote":
            raw_url = f"{self.base_url}/{keywords_slug}-jobs?k={urllib.parse.quote(self.config.keywords)}&wfhType=0{exp_param}"
        else:
            raw_url = f"{self.base_url}/{keywords_slug}-jobs?k={urllib.parse.quote(self.config.keywords)}{exp_param}"

        # Canonical freshness URL parameter preservation
        search_url = build_naukri_search_url(raw_url, self.config.freshness_days)

        exp_log = f" with {self.config.experience_years} YOE" if self.config.experience_years is not None else ""
        fresh_log = f" [Freshness: {self.config.freshness_days}d]" if self.config.freshness_days is not None else ""
        await broadcaster.emit_log(
            f"Searching Naukri: '{self.config.keywords}' in '{self.config.location}'{exp_log}{fresh_log}...",
            platform=self.platform_name.value
        )

        try:
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=35000)
            await self.human_delay(2.0, 4.0)

            # Check if initial search page has limit/quota block
            limit_reason = await detect_application_limit(self.page)
            if limit_reason:
                raise ApplicationLimitDetected(limit_reason)

            try:
                await self.page.wait_for_selector(".srp-jobtuple-wrapper, .cust-job-tuple, article.jobTuple, div[data-job-id]", timeout=12000)
            except Exception:
                pass
        except ApplicationLimitDetected as e:
            await broadcaster.emit_log(f"🛑 Naukri stopped applications: {e.reason}", level=LogLevel.WARNING, platform=self.platform_name.value)
            return 0
        except Exception as e:
            await broadcaster.emit_log(f"Error accessing Naukri search: {e}", level=LogLevel.ERROR, platform=self.platform_name.value)
            return 0

        applied_count = 0
        current_page = 1

        try:
            while applied_count < self.config.max_applications:
                await self.check_pause_and_stop()
                await self.human_scroll(600)
                await self.human_delay(1.5, 2.5)

                # Query parent card containers without duplicate matches on nested children
                job_tuples = await self.page.query_selector_all(".srp-jobtuple-wrapper, .cust-job-tuple, article.jobTuple")
                if not job_tuples:
                    job_tuples = await self.page.query_selector_all("div[data-job-id]")
                if not job_tuples:
                    if "Access Denied" in (await self.page.title()):
                        await broadcaster.emit_log("⚠️ Naukri security checkpoint / Access Denied. Pausing for human verification...", level=LogLevel.WARNING, platform=self.platform_name.value)
                        if self.pause_event:
                            self.pause_event.clear()
                        await self.check_pause_and_stop()
                        continue

                    await broadcaster.emit_log("No more job listings found on Naukri.", platform=self.platform_name.value)
                    break

                await broadcaster.emit_log(f"Found {len(job_tuples)} job cards on Naukri page {current_page}.", platform=self.platform_name.value)

                seen_links_this_page = set()

                for idx, tuple_elem in enumerate(job_tuples):
                    if applied_count >= self.config.max_applications:
                        break

                    await self.check_pause_and_stop()

                    job_page: Optional[Page] = None
                    job_link = ""
                    job_id = ""
                    job_title = "Software Engineer"
                    company = "Tech Firm"
                    try:
                        title_elem = await tuple_elem.query_selector(".title, a.title")
                        company_elem = await tuple_elem.query_selector(".comp-name, a.comp-name")
                        loc_elem = await tuple_elem.query_selector(".loc-wrap, .loc, .styles_loc-wrap__nn_1b, .location")
                        
                        job_title = (await title_elem.inner_text()).strip() if title_elem else "Software Engineer"
                        company = (await company_elem.inner_text()).strip() if company_elem else "Tech Firm"
                        location = (await loc_elem.inner_text()).strip() if loc_elem else ""
                        job_link = ((await title_elem.get_attribute("href")) if title_elem else None) or self.page.url

                        norm_job_link = excel_tracker._normalize_url(job_link)

                        # Layer 2: Stable Job ID extraction with canonical URL fallback
                        card_job_id = await tuple_elem.get_attribute("data-job-id")
                        if not card_job_id:
                            child_id_el = await tuple_elem.query_selector("[data-job-id]")
                            if child_id_el:
                                card_job_id = await child_id_el.get_attribute("data-job-id")

                        job_id = f"JOB-{card_job_id}" if card_job_id else f"JOB-{hashlib.md5(norm_job_link.encode('utf-8')).hexdigest()[:8]}"

                        # Session deduplication across pages & scrolling
                        if (card_job_id and card_job_id in self.seen_jobs_this_run) or (norm_job_link and norm_job_link in self.seen_urls_this_run) or (norm_job_link and norm_job_link in seen_links_this_page):
                            continue

                        if card_job_id:
                            self.seen_jobs_this_run.add(card_job_id)
                        if norm_job_link:
                            self.seen_urls_this_run.add(norm_job_link)
                            seen_links_this_page.add(norm_job_link)

                        # 1. Quick check if already marked as 'Applied' directly on the card badge
                        applied_badge = await tuple_elem.query_selector(".applied, span:has-text('Applied'), .already-applied, .applied-tag")
                        if applied_badge and await applied_badge.is_visible():
                            await broadcaster.emit_log(f"Skipping already applied job on card: {job_title} at {company}", platform=self.platform_name.value)
                            continue

                        # 2. Check title relevance
                        if not self.is_title_relevant(job_title):
                            await broadcaster.emit_log(
                                f"Skipping non-matching role: '{job_title}' at {company} (conflicts with target stack '{self.config.keywords}')",
                                platform=self.platform_name.value
                            )
                            continue

                        # 3. Check deduplication across all past states (exact Job ID, exact URL, or semantic fingerprint)
                        is_dup, dup_type, matched_id = excel_tracker.check_duplicate(job_link, company, job_title, location, job_id=job_id)
                        if is_dup:
                            if dup_type in ("EXACT_URL", "EXACT_JOB_ID"):
                                prev_status = excel_tracker.get_processed_status(job_link) or matched_id
                                await broadcaster.emit_log(
                                    f"Skipping exact duplicate Naukri job ({dup_type}): '{job_title}' at {company} (Status: {prev_status})",
                                    platform=self.platform_name.value
                                )
                                continue
                            elif dup_type == "POSSIBLE_DUPLICATE":
                                # Requirement: Semantic fingerprint is POSSIBLE duplicate -> MANUAL_REVIEW, never skip automatically
                                await broadcaster.emit_log(
                                    f"⚠️ Possible semantic duplicate detected: '{job_title}' at {company} (matches {matched_id}). Routing to Manual Review.",
                                    level=LogLevel.WARNING,
                                    platform=self.platform_name.value
                                )
                                try:
                                    self.record_job_result(
                                        job_id=job_id,
                                        job_title=job_title,
                                        company=company,
                                        job_url=job_link,
                                        status=ApplicationStatus.MANUAL_REVIEW_NEEDED,
                                        reason_code=ReasonCode.POSSIBLE_DUPLICATE,
                                        status_reason=f"Possible duplicate of previously seen job {matched_id}",
                                        notes=f"Possible duplicate of {matched_id}",
                                        application_type="QUICK_APPLY"
                                    )
                                except PersistenceError as pe:
                                    logger.error(f"Persistence error on possible duplicate: {pe}")
                                continue

                        # 4. Card classification
                        app_type = await classify_application(tuple_elem)
                        
                        # Inspectability contract:
                        # - QUICK_APPLY: Inspect & apply subject to gates
                        # - EXTERNAL: Inspect & extract intelligence, never apply
                        # - UNKNOWN: Inspect only if standard URL, extract intelligence, never apply
                        if app_type == ApplicationType.UNKNOWN and "naukri.com/job-listings" not in (job_link or ""):
                            await broadcaster.emit_log(
                                f"Skipping unrecognized non-inspectable card layout ({app_type.value}): {job_title} at {company}",
                                platform=self.platform_name.value
                            )
                            continue

                        # 5. Open job details in new tab to DISCOVER intelligence first
                        await broadcaster.emit_log(f"Inspecting Naukri job details: {job_title} at {company}", level=LogLevel.ACTION, platform=self.platform_name.value)
                        
                        job_page = await self.context.new_page()
                        await job_page.goto(job_link, wait_until="domcontentloaded", timeout=30000)
                        await asyncio.sleep(2)
                        await self.dismiss_notification_prompts(job_page)

                        # Boundary check: platform limit on opened job
                        limit_reason = await detect_application_limit(job_page)
                        if limit_reason:
                            raise ApplicationLimitDetected(limit_reason)

                        # Strip out platform disclaimer / anti-fraud alert elements before reading text
                        try:
                            await job_page.evaluate("""() => {
                                const disclaimerSels = ['.styles_disclaimer__nNZjJ', '.disclaimer', '.fraud-alert', '.warning-container', 'div[class*="disclaimer"]'];
                                disclaimerSels.forEach(s => document.querySelectorAll(s).forEach(el => el.remove()));
                            }""")
                        except Exception:
                            pass

                        # 6. Extract Job Description Text
                        jd_elem = await job_page.query_selector("section.styles_job-desc-container__g_JuN, section.job-desc, .job-desc, .styles_job-desc-container__tx70f, .styles_JDJOB-wrap__nNZjJ, .jdContainer, .clearJobs")
                        jd_text = (await jd_elem.inner_text()).strip() if jd_elem else (await job_page.inner_text("body"))

                        # 7. Extract Recruiter Text & Contacts
                        rec_elem = await job_page.query_selector(".recruiter-details, .rec-name, .posted-by, .rec-details")
                        recruiter_text = (await rec_elem.inner_text()).strip() if rec_elem else ""

                        contacts = extract_job_contacts(jd_text, recruiter_text)
                        primary_email = contacts[0].email if contacts else None
                        recruiter_name = contacts[0].name if (contacts and contacts[0].name) else None
                        if not recruiter_name and recruiter_text:
                            import re as regex_mod
                            rec_m = regex_mod.search(r"(?:posted by|recruiter:?)\s*([A-Za-z\s]{2,30})", recruiter_text, regex_mod.IGNORECASE)
                            if rec_m:
                                recruiter_name = rec_m.group(1).strip()
                                recruiter_name = regex_mod.sub(r"\s+(?:at|hiring|from|for).*$", "", recruiter_name, flags=regex_mod.IGNORECASE).strip()

                        if primary_email:
                            await broadcaster.emit_log(
                                f"📧 Recruiter / HR Contact found: {primary_email} ({recruiter_name or 'Hiring Team'}) [{len(contacts)} found]",
                                level=LogLevel.SUCCESS,
                                platform=self.platform_name.value
                            )

                        # 8. Deterministic Match Scoring
                        match_res = match_scorer.score_job(job_title, jd_text, self.profile, min_threshold=self.config.min_match_score)
                        await broadcaster.emit_log(
                            f"📊 Match Score for '{job_title}': {match_res.score}% (Matched: {', '.join(match_res.matched_skills[:4]) or 'General'})",
                            platform=self.platform_name.value
                        )

                        # 9. Job Quality & Risk Scoring
                        quality_eval = job_quality_scorer.evaluate(
                            title=job_title,
                            company=company,
                            location=location,
                            jd_text=jd_text,
                            contacts=contacts,
                            match_score=match_res.score
                        )
                        await broadcaster.emit_log(
                            f"⭐ Quality: {quality_eval.quality_score}/100 | Priority: {quality_eval.priority_score}/100 ({', '.join(quality_eval.priority_reasons) or 'standard'})",
                            platform=self.platform_name.value
                        )

                        # 10. Suggested Recruiter Outreach Template (Manual review/copy)
                        suggested_outreach = None
                        if recruiter_name or primary_email:
                            top_skills = ", ".join(self.profile.skills[:3]) if self.profile.skills else "software engineering"
                            suggested_outreach = (
                                f"Hi {recruiter_name or 'Hiring Team'}, I noticed your opening for {job_title} at {company}. "
                                f"With my background in {top_skills}, I believe my experience aligns well with your team's needs "
                                f"and would love to connect."
                            )

                        # 11. Check Risk Flags: Hard Warning -> Route to MANUAL_REVIEW
                        if quality_eval.risk_flags:
                            risk_str = ", ".join(quality_eval.risk_flags)
                            await broadcaster.emit_log(
                                f"🚨 High Risk Flags detected ({risk_str}) for '{job_title}' at {company}. Flagging for MANUAL REVIEW.",
                                level=LogLevel.WARNING,
                                platform=self.platform_name.value
                            )
                            try:
                                self.record_job_result(
                                    job_id=job_id,
                                    job_title=job_title,
                                    company=company,
                                    job_url=job_link,
                                    status=ApplicationStatus.MANUAL_REVIEW_NEEDED,
                                    reason_code=ReasonCode.JOB_RISK_FLAG,
                                    status_reason=f"Risk flags detected: {risk_str}",
                                    notes=f"Risk flags: {risk_str}",
                                    hr_email=primary_email,
                                    recruiter_name=recruiter_name,
                                    match_score=match_res.score,
                                    job_quality_score=quality_eval.quality_score,
                                    priority_score=quality_eval.priority_score,
                                    priority_reasons=quality_eval.priority_reasons,
                                    risk_flags=quality_eval.risk_flags,
                                    risk_evidence=quality_eval.risk_evidence,
                                    lifecycle_status=JobLifecycleStatus.MANUAL_REVIEW,
                                    contacts=contacts,
                                    suggested_outreach=suggested_outreach,
                                    application_type=app_type.value
                                )
                            except PersistenceError as pe:
                                logger.error(f"Persistence error on risk job: {pe}")
                            continue

                        # 12. Check Match Gating (if mode is enforce)
                        if self.config.match_gating_mode == "enforce" and not match_res.is_eligible:
                            skip_reason = f"Low match score ({match_res.score}% < {self.config.min_match_score}%)"
                            try:
                                self.record_job_result(
                                    job_id=job_id,
                                    job_title=job_title,
                                    company=company,
                                    job_url=job_link,
                                    status=ApplicationStatus.SKIPPED,
                                    reason_code=ReasonCode.LOW_MATCH,
                                    status_reason=skip_reason,
                                    notes=f"Skipped: {skip_reason}",
                                    hr_email=primary_email,
                                    recruiter_name=recruiter_name,
                                    match_score=match_res.score,
                                    job_quality_score=quality_eval.quality_score,
                                    priority_score=quality_eval.priority_score,
                                    priority_reasons=quality_eval.priority_reasons,
                                    risk_flags=quality_eval.risk_flags,
                                    contacts=contacts,
                                    skip_reason=skip_reason,
                                    suggested_outreach=suggested_outreach,
                                    application_type=app_type.value
                                )
                            except PersistenceError as pe:
                                logger.error(f"Persistence error on low match job: {pe}")

                            await broadcaster.emit_log(
                                f"⚠️ Skipping application: '{job_title}' at {company} - {skip_reason} (Missing: {', '.join(match_res.missing_required[:3])})",
                                platform=self.platform_name.value
                            )
                            continue

                        # 13. Persistence Prerequisite Invariant:
                        # Invariant: No job may transition to ELIGIBLE or APPLYING unless the discovery record is successfully persisted.
                        try:
                            self.record_job_result(
                                job_id=job_id,
                                job_title=job_title,
                                company=company,
                                job_url=job_link,
                                status=ApplicationStatus.DISCOVERED,
                                reason_code=None,
                                status_reason="Discovered and persisted; evaluating application prerequisites",
                                notes="Discovered & eligible for application",
                                hr_email=primary_email,
                                recruiter_name=recruiter_name,
                                match_score=match_res.score,
                                job_quality_score=quality_eval.quality_score,
                                priority_score=quality_eval.priority_score,
                                priority_reasons=quality_eval.priority_reasons,
                                risk_flags=quality_eval.risk_flags,
                                contacts=contacts,
                                suggested_outreach=suggested_outreach,
                                application_type=app_type.value
                            )
                        except PersistenceError as pe:
                            await broadcaster.emit_log(
                                f"❌ Persistence failed for '{job_title}' at {company}: {pe}. Aborting application submission.",
                                level=LogLevel.ERROR,
                                platform=self.platform_name.value
                            )
                            continue

                        # 14. Apply Execution Gate
                        apply_btn = await job_page.query_selector(
                            "#apply-button, button.apply-button, .apply-message, button:has-text('Apply'), a:has-text('Apply'), button:has-text('Apply on company site'), a:has-text('Apply on company site'), a:has-text('Apply on website')"
                        )
                        if not apply_btn:
                            excel_tracker.update_application_status(
                                job_link,
                                ApplicationStatus.SKIPPED,
                                notes="Apply button not found on page",
                                reason_code=ReasonCode.APPLY_BUTTON_MISSING
                            )
                            continue

                        btn_text = (await apply_btn.inner_text()).lower()
                        if "already applied" in btn_text or btn_text.strip() == "applied":
                            excel_tracker.update_application_status(
                                job_link,
                                ApplicationStatus.SUCCESS,
                                notes="Already applied previously on Naukri"
                            )
                            await broadcaster.emit_log(
                                f"ℹ️ Job '{job_title}' at {company} was already applied previously on Naukri.",
                                platform=self.platform_name.value
                            )
                            continue

                        btn_href = (await apply_btn.get_attribute("href")) or ""
                        is_external = ("company site" in btn_text or "redirect" in btn_text or "website" in btn_text or (btn_href and "naukri.com" not in btn_href) or app_type == ApplicationType.EXTERNAL)

                        attempt_id = self.get_attempt_id(job_id)

                        # --- ROUTE A: EXTERNAL COMPANY PORTAL APPLICATION ---
                        if is_external:
                            excel_tracker.update_application_status(
                                job_link,
                                ApplicationStatus.APPLYING,
                                notes=f"Attempt {attempt_id}: Navigating to external company website"
                            )
                            await broadcaster.emit_log(
                                f"🌐 Opening external company portal for '{job_title}' at {company}...",
                                level=LogLevel.ACTION,
                                platform=self.platform_name.value
                            )

                            external_page = None
                            try:
                                if btn_href and btn_href.startswith("http") and "naukri.com" not in btn_href:
                                    external_page = await self.context.new_page()
                                    await external_page.goto(btn_href, wait_until="domcontentloaded", timeout=30000)
                                else:
                                    try:
                                        async with self.context.expect_page(timeout=8000) as new_page_info:
                                            await self.safe_click(apply_btn)
                                        external_page = await new_page_info.value
                                    except Exception:
                                        await asyncio.sleep(3)
                                        if "naukri.com/job-listings" not in job_page.url:
                                            external_page = job_page

                                if not external_page:
                                    excel_tracker.update_application_status(
                                        job_link,
                                        ApplicationStatus.SKIPPED,
                                        notes="Could not open external company application URL",
                                        reason_code=ReasonCode.SAFE_CLICK_FAILED
                                    )
                                    continue

                                await external_page.wait_for_load_state("domcontentloaded", timeout=15000)
                                await asyncio.sleep(2)
                                await self.dismiss_notification_prompts(external_page)

                                # 1. Check if external company site requires login / account creation
                                login_required, login_reason = await self.check_external_requires_login(external_page)
                                if login_required:
                                    await broadcaster.emit_log(
                                        f"ℹ️ Skipping external portal for '{job_title}' at {company}: {login_reason}",
                                        platform=self.platform_name.value
                                    )
                                    excel_tracker.update_application_status(
                                        job_link,
                                        ApplicationStatus.SKIPPED,
                                        notes=f"Skipped: {login_reason}",
                                        reason_code=ReasonCode.LOGIN_REQUIRED
                                    )
                                    continue

                                # 2. Direct application: Traverse & fill form with local AI
                                await broadcaster.emit_log(
                                    f"📝 Filling form on external company website: '{job_title}' at {company}...",
                                    level=LogLevel.ACTION,
                                    platform=self.platform_name.value
                                )

                                if self.config.dry_run:
                                    applied_count += 1
                                    excel_tracker.update_application_status(
                                        job_link,
                                        ApplicationStatus.DRY_RUN_COMPLETED,
                                        notes="Dry run completed on external company website"
                                    )
                                    await broadcaster.emit_log(
                                        f"✅ [DRY RUN {applied_count}/{self.config.max_applications}] Simulated apply on external site: {job_title} at {company} (Match: {match_res.score}%)",
                                        level=LogLevel.SUCCESS,
                                        platform=self.platform_name.value
                                    )
                                else:
                                    applied = await self.apply_external_portal(external_page, job_title, company)
                                    if applied:
                                        applied_count += 1
                                        excel_tracker.update_application_status(
                                            job_link,
                                            ApplicationStatus.SUCCESS,
                                            notes="Successfully applied on external company website"
                                        )
                                        await broadcaster.emit_log(
                                            f"✅ [{applied_count}/{self.config.max_applications}] Applied on external company website: {job_title} at {company}!",
                                            level=LogLevel.SUCCESS,
                                            platform=self.platform_name.value
                                        )
                                    else:
                                        excel_tracker.update_application_status(
                                            job_link,
                                            ApplicationStatus.MANUAL_REVIEW_NEEDED,
                                            notes="External application form could not be submitted automatically; flagged for manual review",
                                            reason_code=ReasonCode.SUBMISSION_UNKNOWN
                                        )
                                        await broadcaster.emit_log(
                                            f"⚠️ External application form could not be submitted automatically for {job_title} at {company}. Routed to MANUAL REVIEW.",
                                            level=LogLevel.WARNING,
                                            platform=self.platform_name.value
                                        )
                            finally:
                                if external_page and external_page != job_page and not external_page.is_closed():
                                    try:
                                        await external_page.close()
                                    except Exception:
                                        pass

                            await asyncio.sleep(self.config.cooldown_seconds)
                            continue

                        # --- ROUTE B: NAUKRI QUICK APPLY PATH ---
                        excel_tracker.update_application_status(
                            job_link,
                            ApplicationStatus.APPLYING,
                            notes=f"Attempt {attempt_id}: Submitting Quick Apply"
                        )

                        # Quick Apply on Naukri
                        if self.config.dry_run:
                            applied_count += 1
                            excel_tracker.update_application_status(
                                job_link,
                                ApplicationStatus.DRY_RUN_COMPLETED,
                                notes="Dry run completed successfully"
                            )
                            await broadcaster.emit_log(
                                f"✅ [DRY RUN {applied_count}/{self.config.max_applications}] Simulated apply on Naukri: {job_title} at {company} (Match: {match_res.score}%, Quality: {quality_eval.quality_score})",
                                level=LogLevel.SUCCESS,
                                platform=self.platform_name.value
                            )
                        else:
                            clicked = await self.safe_click(apply_btn)
                            if not clicked:
                                excel_tracker.update_application_status(
                                    job_link,
                                    ApplicationStatus.FAILED,
                                    notes="Could not safely click Apply button"
                                )
                                await broadcaster.emit_log(f"Could not safely click Apply button for {job_title}", level=LogLevel.WARNING, platform=self.platform_name.value)
                                continue

                            await asyncio.sleep(2)
                            
                            # Check limit right after clicking apply
                            limit_reason = await detect_application_limit(job_page)
                            if limit_reason:
                                excel_tracker.update_application_status(
                                    job_link,
                                    ApplicationStatus.FAILED,
                                    notes=f"Application limit: {limit_reason}",
                                    reason_code=ReasonCode.APPLICATION_LIMIT
                                )
                                raise ApplicationLimitDetected(limit_reason)

                            # Handle interactive chatbot questionnaire if opened
                            await self.handle_naukri_chatbot(job_page, job_title, company)

                            # Check limit post-submission
                            limit_reason = await detect_application_limit(job_page)
                            if limit_reason:
                                excel_tracker.update_application_status(
                                    job_link,
                                    ApplicationStatus.FAILED,
                                    notes=f"Application limit: {limit_reason}",
                                    reason_code=ReasonCode.APPLICATION_LIMIT
                                )
                                raise ApplicationLimitDetected(limit_reason)

                            # 15. Verify Application Result
                            verify_result = await self.verify_application_result(job_page)
                            if verify_result == VerificationResult.CONFIRMED_SUCCESS:
                                applied_count += 1
                                excel_tracker.update_application_status(
                                    job_link,
                                    ApplicationStatus.SUCCESS,
                                    notes="Successfully applied and verified via Naukri Quick Apply"
                                )
                                await broadcaster.emit_log(
                                    f"✅ [{applied_count}/{self.config.max_applications}] Applied & Verified on Naukri: {job_title} at {company} (Match: {match_res.score}%, Priority: {quality_eval.priority_score})!",
                                    level=LogLevel.SUCCESS,
                                    platform=self.platform_name.value
                                )
                            elif verify_result == VerificationResult.CONFIRMED_FAILURE:
                                excel_tracker.update_application_status(
                                    job_link,
                                    ApplicationStatus.FAILED,
                                    notes="Application submission confirmed failed post-verification",
                                    reason_code=ReasonCode.PROFILE_INCOMPLETE
                                )
                                await broadcaster.emit_log(
                                    f"❌ Application failed for {job_title} at {company} after submission.",
                                    level=LogLevel.WARNING,
                                    platform=self.platform_name.value
                                )
                            else:
                                # UNKNOWN outcome: Safety guarantee - DO NOT blindly retry, route to MANUAL_REVIEW
                                excel_tracker.update_application_status(
                                    job_link,
                                    ApplicationStatus.MANUAL_REVIEW_NEEDED,
                                    notes=f"Submission outcome unconfirmed (Attempt: {attempt_id}); routed to Manual Review",
                                    reason_code=ReasonCode.SUBMISSION_UNKNOWN
                                )
                                await broadcaster.emit_log(
                                    f"⚠️ Submission outcome could not be verified automatically for {job_title} at {company}. Routed to MANUAL REVIEW (no blind retry).",
                                    level=LogLevel.WARNING,
                                    platform=self.platform_name.value
                                )

                        # Cooldown
                        await asyncio.sleep(self.config.cooldown_seconds)

                    except ApplicationLimitDetected:
                        raise
                    except Exception as e:
                        logger.warning(f"Error applying on Naukri item #{idx}: {e}")
                        try:
                            # Persistence invariant: Never leave a discovered/analyzed job unrecorded
                            if job_link and not excel_tracker.is_already_processed(job_link):
                                self.record_job_result(
                                    job_id=job_id,
                                    job_title=job_title,
                                    company=company,
                                    job_url=job_link,
                                    status=ApplicationStatus.MANUAL_REVIEW_NEEDED,
                                    lifecycle_status=JobLifecycleStatus.MANUAL_REVIEW,
                                    reason_code=ReasonCode.SUBMISSION_UNKNOWN,
                                    status_reason=f"Processing exception: {str(e)[:100]}",
                                    notes=f"Exception during processing: {e}"
                                )
                        except Exception as pe:
                            logger.error(f"Failed to persist exception fallback record: {pe}")
                    finally:
                        if job_page and not job_page.is_closed():
                            try:
                                await job_page.close()
                            except Exception:
                                pass
                        await self.cleanup_extra_pages()

                # Pagination
                await self.dismiss_notification_prompts(self.page)
                next_btn = await self.page.query_selector("a.styles_btn-secondary__2AsIS:has-text('Next'), a:has-text('Next')")
                if next_btn:
                    current_page += 1
                    await next_btn.click()
                    await self.human_delay(3.0, 5.0)
                else:
                    break

        except ApplicationLimitDetected as e:
            await broadcaster.emit_log(
                f"🛑 Naukri stopped applications: {e.reason}",
                level=LogLevel.WARNING,
                platform=self.platform_name.value
            )

        return applied_count
