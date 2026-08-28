import asyncio
import urllib.parse
from typing import Optional
from app.core.config import settings
from app.core.logger import broadcaster, logger
from app.models.job import PlatformEnum, ApplicationStatus, LogLevel
from app.platforms.base import BasePlatform
from app.services.excel_tracker import excel_tracker

class LinkedInPlatform(BasePlatform):
    def __init__(self, *args, **kwargs):
        super().__init__(PlatformEnum.LINKEDIN, *args, **kwargs)
        self.base_url = "https://www.linkedin.com"

    async def is_logged_in(self) -> bool:
        """Check if current page session is logged in to LinkedIn."""
        try:
            await self.page.goto(f"{self.base_url}/feed/", wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)
            # Check for feed identity element or search bar
            if "feed" in self.page.url or await self.page.query_selector(".global-nav__me"):
                return True
        except Exception:
            pass
        return False

    async def login(self) -> bool:
        """Log into LinkedIn using environment credentials or interactive prompt."""
        await broadcaster.emit_log("Authenticating on LinkedIn...", platform=self.platform_name.value)
        
        # Check if saved cookies are already valid
        if await self.is_logged_in():
            await broadcaster.emit_log("Reused valid LinkedIn session from cookies.", level=LogLevel.SUCCESS, platform=self.platform_name.value)
            return True

        email = settings.LINKEDIN_EMAIL
        password = settings.LINKEDIN_PASSWORD

        if not email or not password:
            await broadcaster.emit_log(
                "No LINKEDIN_EMAIL / LINKEDIN_PASSWORD found in .env. Checking for manual login...",
                level=LogLevel.WARNING,
                platform=self.platform_name.value
            )
            return False

        try:
            await self.page.goto(f"{self.base_url}/login", wait_until="domcontentloaded", timeout=30000)
            await self.human_delay(1.5, 3.0)

            # Check for username input
            username_input = await self.page.query_selector("#username")
            password_input = await self.page.query_selector("#password")

            if username_input and password_input:
                await self.human_type(username_input, email)
                await self.human_delay(0.5, 1.2)
                await self.human_type(password_input, password)
                await self.human_delay(0.8, 1.5)

                submit_btn = await self.page.query_selector("button[type='submit']")
                if submit_btn:
                    await submit_btn.click()

            await self.page.wait_for_load_state("domcontentloaded")
            await asyncio.sleep(3)

            # Check for 2FA / Verification Challenge
            if await self.check_for_captcha() or "checkpoint" in self.page.url:
                await broadcaster.emit_log(
                    "🔐 LinkedIn 2FA / Security Pin detected! Please solve or approve on your device, then resume bot.",
                    level=LogLevel.WARNING,
                    platform=self.platform_name.value
                )
                self.pause_event.clear()
                await self.check_pause_and_stop()

            if await self.is_logged_in():
                await self._save_cookies()
                await broadcaster.emit_log("Successfully logged in to LinkedIn!", level=LogLevel.SUCCESS, platform=self.platform_name.value)
                return True
            else:
                await broadcaster.emit_log("LinkedIn login could not be verified.", level=LogLevel.ERROR, platform=self.platform_name.value)
                return False

        except Exception as e:
            await broadcaster.emit_log(f"LinkedIn login failed: {e}", level=LogLevel.ERROR, platform=self.platform_name.value)
            return False

    async def search_and_apply(self) -> int:
        """Search for jobs with 'Easy Apply' filter and apply automatically."""
        keywords_encoded = urllib.parse.quote(self.config.keywords)
        location_encoded = urllib.parse.quote(self.config.location)
        
        # f_AL=true filters for LinkedIn Easy Apply
        search_url = f"{self.base_url}/jobs/search/?keywords={keywords_encoded}&location={location_encoded}&f_AL=true&sortBy=DD"
        
        await broadcaster.emit_log(f"Searching LinkedIn: '{self.config.keywords}' in '{self.config.location}' (Easy Apply enabled)...", platform=self.platform_name.value)
        
        try:
            await self.page.goto(search_url, wait_until="domcontentloaded", timeout=40000)
            await self.human_delay(2.0, 4.0)
        except Exception as e:
            await broadcaster.emit_log(f"Failed to navigate to LinkedIn search: {e}", level=LogLevel.ERROR, platform=self.platform_name.value)
            return 0

        applied_count = 0
        current_page = 1

        while applied_count < self.config.max_applications:
            await self.check_pause_and_stop()
            
            # Scroll down search list to lazy load job cards
            await self.human_scroll(500)
            await self.human_delay(1.0, 2.0)

            job_cards = await self.page.query_selector_all(".job-card-container, .jobs-search-results__list-item, li[data-occludable-job-id]")
            
            if not job_cards:
                await broadcaster.emit_log("No more job listings found on current LinkedIn page.", platform=self.platform_name.value)
                break

            await broadcaster.emit_log(f"Found {len(job_cards)} job cards on page {current_page}.", platform=self.platform_name.value)

            for idx, card in enumerate(job_cards):
                if applied_count >= self.config.max_applications:
                    break
                
                await self.check_pause_and_stop()

                try:
                    # Click job card
                    await card.scroll_into_view_if_needed()
                    await card.click()
                    await self.human_delay(1.5, 3.0)

                    # Extract job info
                    title_elem = await self.page.query_selector(".job-details-jobs-unified-top-card__job-title, .jobs-unified-top-card__job-title, h1")
                    company_elem = await self.page.query_selector(".job-details-jobs-unified-top-card__company-name, .jobs-unified-top-card__company-name")
                    
                    job_title = (await title_elem.inner_text()).strip() if title_elem else "Software Engineer"
                    company = (await company_elem.inner_text()).strip() if company_elem else "Company"
                    current_url = self.page.url

                    # Check duplicate
                    if excel_tracker.is_already_applied(current_url):
                        await broadcaster.emit_log(f"Skipping duplicate job: {job_title} at {company}", level=LogLevel.INFO, platform=self.platform_name.value)
                        continue

                    # Look for Easy Apply button
                    easy_apply_btn = await self.page.query_selector("button.jobs-apply-button, button[data-job-id]")
                    if not easy_apply_btn or "easy" not in (await easy_apply_btn.inner_text()).lower():
                        await broadcaster.emit_log(f"Job '{job_title}' does not have standard Easy Apply. Skipping.", platform=self.platform_name.value)
                        continue

                    await broadcaster.emit_log(f"Attempting application for: {job_title} at {company}", level=LogLevel.ACTION, platform=self.platform_name.value)
                    
                    await easy_apply_btn.click()
                    await self.human_delay(1.5, 2.5)

                    # Modal multi-step flow
                    success = await self._handle_easy_apply_modal(job_title, company, current_url)
                    
                    if success:
                        applied_count += 1
                        status = ApplicationStatus.DRY_RUN_COMPLETED if self.config.dry_run else ApplicationStatus.SUCCESS
                        self.record_job_result(job_title, company, current_url, status, "Successfully applied via LinkedIn Easy Apply")
                        await broadcaster.emit_log(
                            f"✅ [{applied_count}/{self.config.max_applications}] Successfully applied to {job_title} at {company}!",
                            level=LogLevel.SUCCESS,
                            platform=self.platform_name.value
                        )
                    else:
                        self.record_job_result(job_title, company, current_url, ApplicationStatus.MANUAL_REVIEW_NEEDED, "Multi-step complex form or external redirect")

                    # Cooldown jitter between applications
                    await broadcaster.emit_log(f"Cooling down for {self.config.cooldown_seconds}s before next application...", platform=self.platform_name.value)
                    await asyncio.sleep(self.config.cooldown_seconds)

                except Exception as e:
                    logger.warning(f"Error processing LinkedIn job card #{idx}: {e}")
                    continue

            # Try navigating to next page
            next_btn = await self.page.query_selector(f"button[aria-label='Page {current_page + 1}']")
            if next_btn:
                current_page += 1
                await next_btn.click()
                await self.human_delay(3.0, 5.0)
            else:
                break

        return applied_count

    async def _handle_easy_apply_modal(self, job_title: str, company: str, job_url: str) -> bool:
        """Traverse through multi-page LinkedIn Easy Apply wizard modal."""
        max_steps = 8
        for step in range(max_steps):
            await self.check_pause_and_stop()
            await self.check_for_captcha()

            modal = await self.page.query_selector(".jobs-easy-apply-modal, div[role='dialog']")
            if not modal:
                return False

            # Fill form fields on current step using LLM
            await self.fill_form_with_llm(job_title, company, modal)
            await self.human_delay(1.0, 2.0)

            # Check buttons in modal footer: "Next", "Review", "Submit application"
            submit_btn = await modal.query_selector("button[aria-label='Submit application'], button:has-text('Submit application')")
            if submit_btn:
                if self.config.dry_run:
                    await broadcaster.emit_log(f"DRY RUN: Form filled successfully for {job_title}. Not submitting.", level=LogLevel.INFO, platform=self.platform_name.value)
                else:
                    await submit_btn.click()
                    await self.human_delay(2.0, 3.5)
                
                # Close any confirmation modal
                close_btn = await self.page.query_selector("button[aria-label='Dismiss']")
                if close_btn:
                    await close_btn.click()
                return True

            review_btn = await modal.query_selector("button[aria-label='Review your application'], button:has-text('Review')")
            if review_btn:
                await review_btn.click()
                await self.human_delay(1.5, 2.5)
                continue

            next_btn = await modal.query_selector("button[aria-label='Continue to next step'], button:has-text('Next')")
            if next_btn:
                await next_btn.click()
                await self.human_delay(1.5, 2.5)
                continue

            # If no forward button, check if error exists or exit
            break

        # If we couldn't complete the modal, dismiss it cleanly
        dismiss_btn = await self.page.query_selector("button[aria-label='Dismiss'], button.artdeco-modal__dismiss")
        if dismiss_btn:
            await dismiss_btn.click()
            await asyncio.sleep(0.5)
            discard_btn = await self.page.query_selector("button[data-control-name='discard_application_confirm_btn'], button:has-text('Discard')")
            if discard_btn:
                await discard_btn.click()

        return False
