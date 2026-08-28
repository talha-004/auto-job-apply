import asyncio
import urllib.parse
from app.core.config import settings
from app.core.logger import broadcaster, logger
from app.models.job import PlatformEnum, ApplicationStatus, LogLevel
from app.platforms.base import BasePlatform
from app.services.excel_tracker import excel_tracker

class IndeedPlatform(BasePlatform):
    def __init__(self, *args, **kwargs):
        super().__init__(PlatformEnum.INDEED, *args, **kwargs)
        self.base_url = "https://www.indeed.com"

    async def is_logged_in(self) -> bool:
        """Verify Indeed session."""
        try:
            await self.page.goto(f"{self.base_url}", wait_until="domcontentloaded", timeout=25000)
            await asyncio.sleep(2)
            if await self.page.query_selector("[data-gnav-element-name='UserMenu'], [aria-label='User Profile']"):
                return True
        except Exception:
            pass
        return False

    async def login(self) -> bool:
        """Log into Indeed or reuse saved session cookies."""
        await broadcaster.emit_log("Authenticating on Indeed...", platform=self.platform_name.value)
        
        if await self.is_logged_in():
            await broadcaster.emit_log("Reused valid Indeed session from cookies.", level=LogLevel.SUCCESS, platform=self.platform_name.value)
            return True

        email = settings.INDEED_EMAIL
        password = settings.INDEED_PASSWORD

        if not email or not password:
            await broadcaster.emit_log("No INDEED_EMAIL / INDEED_PASSWORD found in .env.", level=LogLevel.WARNING, platform=self.platform_name.value)
            return False

        try:
            await self.page.goto(f"{self.base_url}/account/login", wait_until="domcontentloaded", timeout=30000)
            await self.human_delay(1.5, 2.5)

            email_input = await self.page.query_selector("input[type='email'], #ifl-InputFormField-3")
            if email_input:
                await self.human_type(email_input, email)
                await self.human_delay(0.5, 1.0)
                submit_btn = await self.page.query_selector("button[type='submit']")
                if submit_btn:
                    await submit_btn.click()
                    await asyncio.sleep(2)

            pwd_input = await self.page.query_selector("input[type='password'], #ifl-InputFormField-15")
            if pwd_input:
                await self.human_type(pwd_input, password)
                await self.human_delay(0.5, 1.0)
                submit_btn = await self.page.query_selector("button[type='submit']")
                if submit_btn:
                    await submit_btn.click()

            await asyncio.sleep(3)

            # Check for Cloudflare / CAPTCHA on Indeed
            if await self.check_for_captcha():
                await broadcaster.emit_log("Indeed Cloudflare challenge detected! Please solve in browser.", level=LogLevel.WARNING, platform=self.platform_name.value)
                self.pause_event.clear()
                await self.check_pause_and_stop()

            if await self.is_logged_in():
                await self._save_cookies()
                await broadcaster.emit_log("Successfully logged in to Indeed!", level=LogLevel.SUCCESS, platform=self.platform_name.value)
                return True
            else:
                await broadcaster.emit_log("Indeed login state unverified, proceeding with search...", level=LogLevel.INFO, platform=self.platform_name.value)
                return True

        except Exception as e:
            await broadcaster.emit_log(f"Indeed login error: {e}", level=LogLevel.ERROR, platform=self.platform_name.value)
            return False

    async def search_and_apply(self) -> int:
        """Search Indeed jobs with 'Easily Apply' filter and automate submissions."""
        keywords_encoded = urllib.parse.quote(self.config.keywords)
        location_encoded = urllib.parse.quote(self.config.location)
        search_url = f"{self.base_url}/jobs?q={keywords_encoded}&l={location_encoded}&sort=date"

        await broadcaster.emit_log(f"Searching Indeed: '{self.config.keywords}' in '{self.config.location}'...", platform=self.platform_name.value)

        try:
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=35000)
            await self.human_delay(2.0, 3.5)
        except Exception as e:
            await broadcaster.emit_log(f"Error loading Indeed search: {e}", level=LogLevel.ERROR, platform=self.platform_name.value)
            return 0

        applied_count = 0

        while applied_count < self.config.max_applications:
            await self.check_pause_and_stop()
            await self.human_scroll(500)
            await self.human_delay(1.0, 2.0)

            cards = await self.page.query_selector_all(".job_seen_beacon, .jobsearch-ResultsList > li, div[data-jk]")
            if not cards:
                await broadcaster.emit_log("No more Indeed job cards found.", platform=self.platform_name.value)
                break

            for idx, card in enumerate(cards):
                if applied_count >= self.config.max_applications:
                    break

                await self.check_pause_and_stop()

                try:
                    title_elem = await card.query_selector("h2.jobTitle span, a[data-jk] span")
                    company_elem = await card.query_selector("span[data-testid='company-name'], .companyName")
                    
                    job_title = (await title_elem.inner_text()).strip() if title_elem else "Software Engineer"
                    company = (await company_elem.inner_text()).strip() if company_elem else "Tech Co"

                    jk_id = await card.get_attribute("data-jk")
                    job_link = f"{self.base_url}/viewjob?jk={jk_id}" if jk_id else self.page.url

                    if excel_tracker.is_already_applied(job_link):
                        await broadcaster.emit_log(f"Skipping already applied Indeed job: {job_title} at {company}", platform=self.platform_name.value)
                        continue

                    # Click to view job pane
                    await card.click()
                    await self.human_delay(1.5, 2.5)

                    # Look for Indeed Apply button
                    apply_btn = await self.page.query_selector("#indeedApplyButton, button:has-text('Apply now')")
                    if not apply_btn:
                        await broadcaster.emit_log(f"Indeed job '{job_title}' redirects externally. Logging for review.", platform=self.platform_name.value)
                        self.record_job_result(job_title, company, job_link, ApplicationStatus.MANUAL_REVIEW_NEEDED, "Requires external company portal")
                        continue

                    await broadcaster.emit_log(f"Applying to Indeed job: {job_title} at {company}", level=LogLevel.ACTION, platform=self.platform_name.value)
                    
                    if not self.config.dry_run:
                        await apply_btn.click()
                        await asyncio.sleep(2)
                        await self._handle_indeed_modal(job_title, company)

                    applied_count += 1
                    status = ApplicationStatus.DRY_RUN_COMPLETED if self.config.dry_run else ApplicationStatus.SUCCESS
                    self.record_job_result(job_title, company, job_link, status, "Applied via Indeed Apply")
                    
                    await broadcaster.emit_log(
                        f"✅ [{applied_count}/{self.config.max_applications}] Applied on Indeed: {job_title} at {company}!",
                        level=LogLevel.SUCCESS,
                        platform=self.platform_name.value
                    )

                    await asyncio.sleep(self.config.cooldown_seconds)

                except Exception as e:
                    logger.warning(f"Error applying on Indeed card #{idx}: {e}")
                    continue

            # Check next page button
            next_btn = await self.page.query_selector("a[data-testid='pagination-page-next'], a[aria-label='Next Page']")
            if next_btn:
                await next_btn.click()
                await self.human_delay(3.0, 5.0)
            else:
                break

        return applied_count

    async def _handle_indeed_modal(self, job_title: str, company: str):
        """Walk through Indeed's multi-step modal or iframe."""
        for _ in range(6):
            await self.check_pause_and_stop()
            # Scan for iframe or container
            iframe_elem = await self.page.query_selector("iframe[title*='Job Application'], iframe[src*='indeedapply']")
            frame = await iframe_elem.content_frame() if iframe_elem else self.page

            # Fill questions
            fields = await self.scan_form_fields()
            if fields:
                await self.fill_form_with_llm(job_title, company)

            # Look for Continue / Submit button
            submit_btn = await frame.query_selector("button:has-text('Submit your application'), button:has-text('Submit')")
            if submit_btn:
                await submit_btn.click()
                await asyncio.sleep(2)
                return True

            continue_btn = await frame.query_selector("button:has-text('Continue'), button:has-text('Next')")
            if continue_btn:
                await continue_btn.click()
                await asyncio.sleep(2)
            else:
                break
        return False
