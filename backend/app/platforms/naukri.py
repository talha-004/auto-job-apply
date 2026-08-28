import asyncio
import urllib.parse
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

    async def search_and_apply(self) -> int:
        """Search jobs on Naukri and apply automatically."""
        keywords_slug = self.config.keywords.lower().replace(" ", "-")
        location_slug = self.config.location.lower().replace(" ", "-")
        
        if location_slug:
            search_url = f"{self.base_url}/{keywords_slug}-jobs-in-{location_slug}?k={urllib.parse.quote(self.config.keywords)}&l={urllib.parse.quote(self.config.location)}"
        else:
            search_url = f"{self.base_url}/{keywords_slug}-jobs?k={urllib.parse.quote(self.config.keywords)}"

        await broadcaster.emit_log(f"Searching Naukri: '{self.config.keywords}' in '{self.config.location}'...", platform=self.platform_name.value)

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

                    if excel_tracker.is_already_applied(job_link):
                        await broadcaster.emit_log(f"Skipping already applied Naukri job: {job_title} at {company}", platform=self.platform_name.value)
                        continue

                    # Open job details in new tab or navigate
                    await broadcaster.emit_log(f"Opening Naukri job: {job_title} at {company}", level=LogLevel.ACTION, platform=self.platform_name.value)
                    
                    job_page = await self.context.new_page()
                    await job_page.goto(job_link, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(2)

                    apply_btn = await job_page.query_selector("#apply-button, button.apply-button, .apply-message, button:has-text('Apply')")
                    if not apply_btn:
                        await job_page.close()
                        continue

                    btn_text = (await apply_btn.inner_text()).lower()
                    if "company site" in btn_text or "redirect" in btn_text:
                        await broadcaster.emit_log(f"Job redirects to external company portal. Logging for manual review.", platform=self.platform_name.value)
                        self.record_job_result(job_title, company, job_link, ApplicationStatus.MANUAL_REVIEW_NEEDED, "External company site application")
                        await job_page.close()
                        continue

                    # Quick Apply on Naukri
                    if not self.config.dry_run:
                        await apply_btn.click()
                        await asyncio.sleep(2)

                        # Handle chatbot questionnaire if opens
                        chat_modal = await job_page.query_selector(".chatbot_Drawer, .apply-drawer")
                        if chat_modal:
                            await self.fill_form_with_llm(job_title, company, chat_modal)
                            submit_chat = await chat_modal.query_selector("button:has-text('Submit'), button:has-text('Apply')")
                            if submit_chat:
                                await submit_chat.click()

                    applied_count += 1
                    status = ApplicationStatus.DRY_RUN_COMPLETED if self.config.dry_run else ApplicationStatus.SUCCESS
                    self.record_job_result(job_title, company, job_link, status, "Successfully applied via Naukri Quick Apply")
                    
                    await broadcaster.emit_log(
                        f"✅ [{applied_count}/{self.config.max_applications}] Applied on Naukri: {job_title} at {company}!",
                        level=LogLevel.SUCCESS,
                        platform=self.platform_name.value
                    )
                    await job_page.close()

                    # Cooldown
                    await asyncio.sleep(self.config.cooldown_seconds)

                except Exception as e:
                    logger.warning(f"Error applying on Naukri item #{idx}: {e}")
                    continue

            # Pagination
            next_btn = await self.page.query_selector("a.styles_btn-secondary__2AsIS:has-text('Next'), a:has-text('Next')")
            if next_btn:
                current_page += 1
                await next_btn.click()
                await self.human_delay(3.0, 5.0)
            else:
                break

        return applied_count
