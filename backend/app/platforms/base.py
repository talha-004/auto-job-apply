import asyncio
import json
import random
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, ElementHandle
try:
    from playwright_stealth import stealth_async
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False

from app.core.config import settings
from app.core.llm import llm_client
from app.core.logger import broadcaster, logger
from app.models.job import (
    ResumeProfile,
    SearchConfig,
    JobApplicationRecord,
    ApplicationStatus,
    LogLevel,
    PlatformEnum
)
from app.services.excel_tracker import excel_tracker

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"
]

class BasePlatform(ABC):
    def __init__(
        self,
        platform_name: PlatformEnum,
        config: SearchConfig,
        profile: ResumeProfile,
        resume_file_path: Optional[Path] = None,
        pause_event: Optional[asyncio.Event] = None,
        stop_event: Optional[asyncio.Event] = None
    ):
        self.platform_name = platform_name
        self.config = config
        self.profile = profile
        self.resume_file_path = resume_file_path or settings.RESUME_FILE_PATH
        self.pause_event = pause_event or asyncio.Event()
        self.stop_event = stop_event or asyncio.Event()
        
        if not self.pause_event.is_set():
            self.pause_event.set() # Default is running (unpaused)

        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.cookie_file = settings.COOKIES_DIR / f"{self.platform_name.value.lower()}_cookies.json"

    async def init_browser(self) -> Page:
        """Launch stealth Playwright browser with persistent context or saved cookies."""
        self.playwright = await async_playwright().start()
        
        user_agent = random.choice(USER_AGENTS)
        viewport_width = random.choice([1366, 1440, 1920])
        viewport_height = random.choice([768, 900, 1080])

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--disable-gpu",
            "--window-size=1920,1080"
        ]

        self.browser = await self.playwright.chromium.launch(
            headless=self.config.headless,
            args=launch_args,
            slow_mo=50
        )

        context_options = {
            "viewport": {"width": viewport_width, "height": viewport_height},
            "user_agent": user_agent,
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "has_touch": False,
            "is_mobile": False,
            "device_scale_factor": 1,
            "accept_downloads": True
        }

        if settings.PROXY_URL:
            context_options["proxy"] = {"server": settings.PROXY_URL}
            logger.info(f"Configured proxy for {self.platform_name.value}: {settings.PROXY_URL}")

        self.context = await self.browser.new_context(**context_options)

        # Load saved session cookies if available
        await self._load_cookies()

        self.page = await self.context.new_page()

        if HAS_STEALTH:
            try:
                await stealth_async(self.page)
            except Exception as e:
                logger.warning(f"Stealth injection warning: {e}")

        # Extra evasion scripts
        await self.page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
        """)

        return self.page

    async def close_browser(self):
        """Save cookies and cleanly shut down browser instances."""
        try:
            if self.context:
                await self._save_cookies()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.warning(f"Error during browser teardown: {e}")

    async def _save_cookies(self):
        """Persist session cookies to local storage for automatic login reuse."""
        try:
            if self.context:
                cookies = await self.context.cookies()
                with open(self.cookie_file, "w", encoding="utf-8") as f:
                    json.dump(cookies, f, indent=2)
                logger.info(f"Saved session cookies to {self.cookie_file}")
        except Exception as e:
            logger.warning(f"Could not save cookies: {e}")

    async def _load_cookies(self):
        """Load session cookies into browser context."""
        if self.cookie_file.exists():
            try:
                with open(self.cookie_file, "r", encoding="utf-8") as f:
                    cookies = json.load(f)
                    if cookies:
                        await self.context.add_cookies(cookies)
                        logger.info(f"Loaded {len(cookies)} saved cookies for {self.platform_name.value}")
            except Exception as e:
                logger.warning(f"Could not load cookies for {self.platform_name.value}: {e}")

    async def check_pause_and_stop(self):
        """Check if user requested pause or stop."""
        if self.stop_event.is_set():
            raise asyncio.CancelledError("Bot run cancelled by user.")
        
        if not self.pause_event.is_set():
            await broadcaster.emit_log(
                f"Bot is PAUSED on {self.platform_name.value}. Waiting for user to resume...",
                level=LogLevel.WARNING,
                platform=self.platform_name.value
            )
            await self.pause_event.wait()
            await broadcaster.emit_log(
                f"Bot RESUMED execution on {self.platform_name.value}.",
                level=LogLevel.INFO,
                platform=self.platform_name.value
            )

    async def human_delay(self, min_sec: Optional[float] = None, max_sec: Optional[float] = None):
        """Simulate natural human hesitation between actions."""
        await self.check_pause_and_stop()
        low = min_sec or settings.MIN_DELAY_SECONDS
        high = max_sec or settings.MAX_DELAY_SECONDS
        delay = random.uniform(low, high)
        await asyncio.sleep(delay)

    async def human_type(self, element: ElementHandle, text: str):
        """Type characters with randomized human keystroke intervals."""
        await element.click()
        await element.fill("") # clear first
        for char in text:
            await self.check_pause_and_stop()
            await element.type(char, delay=random.uniform(30, 80))

    async def human_scroll(self, distance: int = 400):
        """Simulate realistic human page scrolling."""
        if self.page:
            steps = random.randint(3, 6)
            step_dist = distance / steps
            for _ in range(steps):
                await self.page.mouse.wheel(0, step_dist)
                await asyncio.sleep(random.uniform(0.08, 0.2))

    async def check_for_captcha(self) -> bool:
        """Detect common CAPTCHA patterns (Cloudflare, reCAPTCHA, hCaptcha, Arkose)."""
        if not self.page:
            return False

        captcha_indicators = [
            "iframe[src*='recaptcha']",
            "iframe[src*='hcaptcha']",
            "iframe[src*='arkoselabs']",
            "div.g-recaptcha",
            "#challenge-running",
            "div[class*='captcha']",
            "div[id*='captcha']",
            "text='Security Check'",
            "text='Let's do a quick security check'",
            "text='Verify you are human'"
        ]

        for selector in captcha_indicators:
            try:
                elem = await self.page.query_selector(selector)
                if elem and await elem.is_visible():
                    await broadcaster.emit_log(
                        f"⚠️ CAPTCHA / Security challenge detected on {self.platform_name.value}! Pausing bot for manual user resolution...",
                        level=LogLevel.WARNING,
                        platform=self.platform_name.value
                    )
                    # Pause the state machine
                    self.pause_event.clear()
                    await self.check_pause_and_stop()
                    return True
            except Exception:
                continue
        return False

    async def cleanup_extra_pages(self):
        """Cleanly close any opened popups/tabs, keeping only the main navigation page."""
        if not self.context:
            return
        for p in list(self.context.pages):
            if p != self.page and not p.is_closed():
                try:
                    await p.close()
                except Exception:
                    pass

    def is_title_relevant(self, job_title: str) -> bool:
        """Check if job title matches search keywords and filters out conflicting stacks."""
        if not self.config.keywords:
            return True

        keywords_lower = self.config.keywords.lower()
        title_lower = job_title.lower()

        # Check for explicitly conflicting tech stacks if not requested by user
        conflicts = [
            ("java full stack", ["react", "frontend", "node", "python"]),
            ("core java", ["react", "frontend", "javascript"]),
            ("java developer", ["react", "frontend", "frontend developer", "ui developer"]),
            ("dotnet", ["react", "frontend", "python"]),
            (".net", ["react", "frontend", "python"]),
            ("php developer", ["react", "python", "node"]),
            ("angular developer", ["react", "reactjs"]),
            ("flutter developer", ["react", "reactjs"]),
            ("salesforce", ["react", "frontend", "full stack"]),
            ("qa automation", ["developer", "software engineer", "frontend", "full stack"]),
        ]

        for conflicting_phrase, intended_targets in conflicts:
            if conflicting_phrase in title_lower and not any(conflicting_phrase in k for k in keywords_lower.split(",")):
                if any(target in keywords_lower for target in intended_targets):
                    logger.info(f"Skipping conflicting job title: '{job_title}' (conflicts with target keywords '{self.config.keywords}')")
                    return False

        return True

    async def scan_form_fields(
        self,
        target_page: Optional[Page] = None,
        container: Optional[ElementHandle] = None
    ) -> List[Dict[str, Any]]:
        """
        Scan all interactive form elements inside container (or target page)
        and construct structured metadata for LLM mapping.
        """
        page = target_page or self.page
        if not page:
            return []

        js_scanner = """
        (rootElem) => {
            const scope = rootElem || document;
            const fields = [];
            const inputs = scope.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), select, textarea');
            
            inputs.forEach((el, index) => {
                let labelText = '';
                if (el.id) {
                    const labelElem = document.querySelector(`label[for="${el.id}"]`);
                    if (labelElem) labelText = labelElem.innerText.trim();
                }
                if (!labelText) {
                    const parentLabel = el.closest('label');
                    if (parentLabel) labelText = parentLabel.innerText.trim();
                }
                if (!labelText && el.getAttribute('aria-label')) {
                    labelText = el.getAttribute('aria-label');
                }
                if (!labelText && el.placeholder) {
                    labelText = el.placeholder;
                }
                if (!labelText && el.name) {
                    labelText = el.name;
                }

                let options = [];
                if (el.tagName.toLowerCase() === 'select') {
                    options = Array.from(el.querySelectorAll('option')).map(o => o.innerText.trim() || o.value);
                }

                fields.push({
                    index: index,
                    id: el.id || el.name || `field_${index}`,
                    name: el.name || '',
                    type: el.type || el.tagName.toLowerCase(),
                    tag: el.tagName.toLowerCase(),
                    label: labelText,
                    placeholder: el.placeholder || '',
                    required: el.required || el.getAttribute('aria-required') === 'true',
                    options: options,
                    current_value: el.value || ''
                });
            });
            return fields;
        }
        """
        try:
            if container:
                detected = await container.evaluate(js_scanner)
            else:
                detected = await page.evaluate(js_scanner)
            return detected or []
        except Exception as e:
            logger.warning(f"Error scanning form fields: {e}")
            return []

    async def fill_form_with_llm(
        self,
        job_title: str,
        company: str,
        target_page: Optional[Page] = None,
        container: Optional[ElementHandle] = None
    ) -> bool:
        """Scan form fields, request LLM mapping, and fill inputs accurately."""
        page = target_page or self.page
        if not page:
            return False

        fields = await self.scan_form_fields(target_page=page, container=container)
        if not fields:
            return True

        job_context = {"title": job_title, "company": company}
        profile_dict = self.profile.model_dump()

        mapping = await llm_client.map_form_fields(profile_dict, fields, job_context)
        logger.info(f"LLM field mapping for {job_title}: {mapping}")

        scope = container or page
        for field in fields:
            await self.check_pause_and_stop()
            field_id = field.get("id")
            field_name = field.get("name")
            field_type = field.get("type", "text").lower()
            field_tag = field.get("tag", "input").lower()

            target_val = mapping.get(field_id) or mapping.get(field_name)
            if target_val is None:
                continue

            try:
                selector = f"#{field_id}" if field_id and not field_id.startswith("field_") else f"[name='{field_name}']"
                elem = await scope.query_selector(selector)
                if not elem or not await elem.is_visible():
                    continue

                if field_type == "file":
                    if self.resume_file_path and self.resume_file_path.exists():
                        await elem.set_input_files(str(self.resume_file_path))
                        await broadcaster.emit_log(f"📎 Attached resume file: {self.resume_file_path.name}", platform=self.platform_name.value)
                elif field_type in ["checkbox"]:
                    should_check = bool(target_val)
                    is_checked = await elem.is_checked()
                    if should_check != is_checked:
                        await elem.click()
                elif field_type in ["radio"]:
                    await elem.click()
                elif field_tag == "select":
                    try:
                        await elem.select_option(label=str(target_val))
                    except Exception:
                        await elem.select_option(value=str(target_val))
                else: # text, email, tel, number, textarea
                    await self.human_type(elem, str(target_val))
                
                await asyncio.sleep(0.2)
            except Exception as e:
                logger.warning(f"Could not fill field {field_id}: {e}")

        return True

    def record_job_result(
        self,
        job_title: str,
        company: str,
        job_url: str,
        status: ApplicationStatus,
        notes: str = ""
    ) -> JobApplicationRecord:
        """Construct and write record to Excel and emit status log."""
        record = JobApplicationRecord(
            platform=self.platform_name.value,
            job_title=job_title or "Job Position",
            company=company or "Company",
            job_url=job_url or "",
            status=status,
            notes=notes
        )
        excel_tracker.log_application(record)
        return record

    @abstractmethod
    async def login(self) -> bool:
        """Authenticate on the platform."""
        pass

    @abstractmethod
    async def search_and_apply(self) -> int:
        """Search jobs and apply up to configured max applications."""
        pass
