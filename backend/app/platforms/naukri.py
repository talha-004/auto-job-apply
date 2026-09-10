import asyncio
import urllib.parse
from typing import Optional
from playwright.async_api import Page
from app.core.config import settings
from app.core.logger import broadcaster, logger
from app.models.job import PlatformEnum, ApplicationStatus, LogLevel
from app.platforms.base import BasePlatform
from app.services.excel_tracker import excel_tracker

class NaukriPlatform(BasePlatform):
    def __init__(self, *args, **kwargs):
        super().__init__(PlatformEnum.NAUKRI, *args, **kwargs)
        self.base_url = "https://www.naukri.com"

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
                # Allow a short grace period
                await asyncio.sleep(5)
                if "nlogin" not in self.page.url:
                    await self._save_cookies()
                    return True
                return False

        except Exception as e:
            await broadcaster.emit_log(f"Naukri login error: {e}", level=LogLevel.ERROR, platform=self.platform_name.value)
            return False

    async def handle_naukri_chatbot(self, job_page: Page, job_title: str, company: str) -> bool:
        """Iteratively answer questions and advance Naukri's Quick Apply chatbot drawer."""
        max_rounds = 5
        round_count = 0
        while round_count < max_rounds:
            round_count += 1
            chat_modal = await job_page.query_selector(".chatbot_Drawer, .apply-drawer, div[class*='chatbot']")
            if not chat_modal or not await chat_modal.is_visible():
                break

            # 1. Fill standard inputs using local AI
            await self.fill_form_with_llm(job_title, company, target_page=job_page, container=chat_modal)

            # 2. Click any interactive choice chips (e.g. Yes/No, Notice Period chips)
            chips = await chat_modal.query_selector_all(".chip, .option-chip, .radio-chip, li.chip, .bot-option")
            for chip in chips:
                try:
                    if await chip.is_visible():
                        chip_text = (await chip.inner_text()).lower()
                        # Prefer affirmative or standard choices
                        if any(w in chip_text for w in ["yes", "immediate", "15 days", "1 month", "full time"]):
                            await chip.click()
                            await asyncio.sleep(1)
                            break
                except Exception:
                    pass

            # 3. Look for Submit / Save / Next inside chatbot
            advance_btn = await chat_modal.query_selector("button:has-text('Submit'), button:has-text('Apply'), button:has-text('Save'), .save-btn, button:has-text('Next')")
            if advance_btn and await advance_btn.is_visible():
                await advance_btn.click()
                await asyncio.sleep(2)
            else:
                break
        return True

    async def search_and_apply(self) -> int:
        """Search jobs on Naukri and apply automatically with smart filtering and external portal support."""
        keywords_slug = self.config.keywords.lower().replace(" ", "-")
        location_slug = self.config.location.lower().replace(" ", "-")
        
        # Smart search URL construction with experience filter
        exp_param = f"&experience={self.config.experience_years}" if self.config.experience_years is not None else ""
        if location_slug and location_slug != "remote":
            search_url = f"{self.base_url}/{keywords_slug}-jobs-in-{location_slug}?k={urllib.parse.quote(self.config.keywords)}&l={urllib.parse.quote(self.config.location)}{exp_param}"
        elif location_slug == "remote":
            search_url = f"{self.base_url}/{keywords_slug}-jobs?k={urllib.parse.quote(self.config.keywords)}&wfhType=0{exp_param}"
        else:
            search_url = f"{self.base_url}/{keywords_slug}-jobs?k={urllib.parse.quote(self.config.keywords)}{exp_param}"

        exp_log = f" with {self.config.experience_years} YOE" if self.config.experience_years is not None else ""
        await broadcaster.emit_log(f"Searching Naukri: '{self.config.keywords}' in '{self.config.location}'{exp_log}...", platform=self.platform_name.value)

        try:
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=35000)
            await self.human_delay(2.0, 4.0)
            try:
                await self.page.wait_for_selector(".srp-jobtuple-wrapper, .cust-job-tuple, article.jobTuple, div[data-job-id]", timeout=12000)
            except Exception:
                pass
        except Exception as e:
            await broadcaster.emit_log(f"Error accessing Naukri search: {e}", level=LogLevel.ERROR, platform=self.platform_name.value)
            return 0

        applied_count = 0
        current_page = 1

        while applied_count < self.config.max_applications:
            await self.check_pause_and_stop()
            await self.human_scroll(600)
            await self.human_delay(1.5, 2.5)

            job_tuples = await self.page.query_selector_all(".srp-jobtuple-wrapper, .cust-job-tuple, article.jobTuple, div[data-job-id]")
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

            for idx, tuple_elem in enumerate(job_tuples):
                if applied_count >= self.config.max_applications:
                    break

                await self.check_pause_and_stop()

                try:
                    title_elem = await tuple_elem.query_selector(".title, a.title")
                    company_elem = await tuple_elem.query_selector(".comp-name, a.comp-name")
                    
                    job_title = (await title_elem.inner_text()).strip() if title_elem else "Software Engineer"
                    company = (await company_elem.inner_text()).strip() if company_elem else "Tech Firm"
                    job_link = await title_elem.get_attribute("href") if title_elem else self.page.url

                    # 1. Quick check if already marked as 'Applied' directly on the card badge
                    applied_badge = await tuple_elem.query_selector(".applied, span:has-text('Applied'), .already-applied, .applied-tag")
                    if applied_badge and await applied_badge.is_visible():
                        await broadcaster.emit_log(f"Skipping already applied job on card: {job_title} at {company}", platform=self.platform_name.value)
                        continue

                    # 2. Check title relevance (skipping conflicting stacks like Java full stack when searching for React)
                    if not self.is_title_relevant(job_title):
                        await broadcaster.emit_log(
                            f"Skipping non-matching role: '{job_title}' at {company} (conflicts with target stack '{self.config.keywords}')",
                            platform=self.platform_name.value
                        )
                        continue

                    # 3. Check Excel deduplication
                    if excel_tracker.is_already_applied(job_link):
                        await broadcaster.emit_log(f"Skipping already recorded Naukri job: {job_title} at {company}", platform=self.platform_name.value)
                        continue

                    # Open job details in new tab
                    await broadcaster.emit_log(f"Opening Naukri job: {job_title} at {company}", level=LogLevel.ACTION, platform=self.platform_name.value)
                    
                    job_page = await self.context.new_page()
                    await job_page.goto(job_link, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(2)

                    apply_btn = await job_page.query_selector("#apply-button, button.apply-button, .apply-message, button:has-text('Apply'), a:has-text('Apply')")
                    if not apply_btn:
                        continue

                    btn_text = (await apply_btn.inner_text()).lower()

                    if "company site" in btn_text or "redirect" in btn_text or "website" in btn_text:
                        # Follow through and auto-fill external company application!
                        await broadcaster.emit_log(
                            f"🌐 Following external company portal for: {job_title} at {company}...",
                            level=LogLevel.ACTION,
                            platform=self.platform_name.value
                        )

                        ext_page = None
                        try:
                            async with self.context.expect_page(timeout=7000) as page_info:
                                await apply_btn.click()
                            ext_page = await page_info.value
                        except Exception:
                            ext_page = job_page

                        if ext_page:
                            await self.apply_external_portal(ext_page, job_title, company)

                        applied_count += 1
                        status = ApplicationStatus.DRY_RUN_COMPLETED if self.config.dry_run else ApplicationStatus.SUCCESS
                        self.record_job_result(job_title, company, job_link, status, "Successfully applied via External Company Portal")
                        
                        await broadcaster.emit_log(
                            f"✅ [{applied_count}/{self.config.max_applications}] Applied on External Portal: {job_title} at {company}!",
                            level=LogLevel.SUCCESS,
                            platform=self.platform_name.value
                        )

                    else:
                        # Quick Apply on Naukri
                        if not self.config.dry_run:
                            await apply_btn.click()
                            await asyncio.sleep(2)
                            # Handle interactive chatbot questionnaire if opened
                            await self.handle_naukri_chatbot(job_page, job_title, company)

                        applied_count += 1
                        status = ApplicationStatus.DRY_RUN_COMPLETED if self.config.dry_run else ApplicationStatus.SUCCESS
                        self.record_job_result(job_title, company, job_link, status, "Successfully applied via Naukri Quick Apply")
                        
                        await broadcaster.emit_log(
                            f"✅ [{applied_count}/{self.config.max_applications}] Applied on Naukri: {job_title} at {company}!",
                            level=LogLevel.SUCCESS,
                            platform=self.platform_name.value
                        )

                    # Cooldown
                    await asyncio.sleep(self.config.cooldown_seconds)

                except Exception as e:
                    logger.warning(f"Error applying on Naukri item #{idx}: {e}")
                finally:
                    # Cleanly close all opened popups/tabs, leaving only the main search page
                    await self.cleanup_extra_pages()

            # Pagination
            next_btn = await self.page.query_selector("a.styles_btn-secondary__2AsIS:has-text('Next'), a:has-text('Next')")
            if next_btn:
                current_page += 1
                await next_btn.click()
                await self.human_delay(3.0, 5.0)
            else:
                break

        return applied_count
