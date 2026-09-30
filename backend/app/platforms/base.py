import asyncio
import json
import random
from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
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
    JobLifecycleStatus,
    ReasonCode,
    LogLevel,
    PlatformEnum,
    QAVault
)
from app.services.excel_tracker import excel_tracker
from app.platforms.naukri_helpers import normalize_token
from app.platforms.adapter_interface import ApplicationAdapter, AdapterApplicationResult
from app.platforms.stealth_driver import HumanBiometricsDriver, PlatformCoolDownException, stealth_driver

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0"
]

class VerificationResult(str, Enum):
    CONFIRMED_SUCCESS = "CONFIRMED_SUCCESS"
    CONFIRMED_FAILURE = "CONFIRMED_FAILURE"
    UNKNOWN = "UNKNOWN"

class PersistenceError(Exception):
    """Raised when job discovery/application record cannot be persisted."""
    pass


class PersistentBrowserBridge:
    """Compatibility bridge providing Browser-like interface over persistent BrowserContext."""

    def __init__(self, context: BrowserContext):
        self._context = context
        self._connected = True

    def is_connected(self) -> bool:
        if not self._connected or not self._context:
            return False
        try:
            connection = getattr(self._context, "_connection", None)
            if connection:
                return not getattr(connection, "is_closed", False)
            return True
        except Exception:
            return False

    async def close(self):
        self._connected = False
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
            self._context = None


class BasePlatform(ApplicationAdapter, ABC):
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
        self.user_data_dir = settings.BROWSER_USER_DATA_DIR / self.platform_name.value.lower()
        self.is_persistent_context: bool = False
        self.run_id: str = getattr(config, "run_id", None) or f"RUN-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.attempt_counters: Dict[str, int] = {}
        self.stealth_driver = HumanBiometricsDriver()

    async def human_type(self, selector_or_element, text: str, typo_chance: float = 0.03):
        """Type with organic human cadence and realistic typo simulation."""
        if not self.page:
            raise RuntimeError("Browser page not initialized.")
        await self.stealth_driver.human_type(self.page, selector_or_element, text, typo_chance=typo_chance)

    async def human_click(self, target, click_type: str = "left"):
        """Move cursor with cubic Bezier curve, pause, and click."""
        if not self.page:
            raise RuntimeError("Browser page not initialized.")
        await self.stealth_driver.human_click(self.page, target, click_type=click_type)

    async def check_challenge_cooldown(self):
        """Detect anti-bot and rate-limiting triggers, raising PlatformCoolDownException if detected."""
        if self.page:
            await self.stealth_driver.detect_and_handle_challenges(self.page, platform=self.platform_name.value)

    def resolve_resume_for_job(self, job_title: str, job_description: str = "") -> Path:
        """Dynamically routes the best-matching resume variant if available, falling back to base resume."""
        try:
            from app.services.multi_resume_router import multi_resume_router
            routing = multi_resume_router.route_best_resume(job_title, job_description)
            routed_path = Path(routing["file_path"])
            if routed_path.exists():
                return routed_path
        except Exception as e:
            logger.debug(f"[BasePlatform] Dynamic resume routing fallback: {e}")
        return self.resume_file_path

    async def init_browser(self) -> Page:
        """Launch stealth Playwright browser with persistent context or saved cookies."""
        self.playwright = await async_playwright().start()
        
        user_agent = random.choice(USER_AGENTS)
        viewport_width = random.choice([1366, 1440, 1920])
        viewport_height = random.choice([768, 900, 1080])

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-infobars",
            "--no-first-run",
            "--window-position=0,0",
            "--window-size=1920,1080",
            "--disable-notifications",
            "--deny-permission-prompts"
        ]

        logger.info(
            "Launching browser: headless=%s, browser=playwright-chromium",
            self.config.headless
        )

        context_options = {
            "viewport": {"width": viewport_width, "height": viewport_height},
            "user_agent": user_agent,
            "locale": "en-US",
            "timezone_id": "America/New_York",
            "has_touch": False,
            "is_mobile": False,
            "device_scale_factor": 1,
            "accept_downloads": True,
            "permissions": []
        }

        if settings.PROXY_URL:
            context_options["proxy"] = {"server": settings.PROXY_URL}
            logger.info(f"Configured proxy for {self.platform_name.value}: {settings.PROXY_URL}")

        # 1. Attempt persistent context if enabled (maintains cookies, storage, IndexedDB across sessions)
        if settings.USE_PERSISTENT_CONTEXT:
            self.user_data_dir.mkdir(exist_ok=True, parents=True)
            try:
                logger.info(
                    "Launching persistent context: dir=%s, headless=%s",
                    self.user_data_dir,
                    self.config.headless
                )
                self.context = await self.playwright.chromium.launch_persistent_context(
                    user_data_dir=str(self.user_data_dir),
                    headless=self.config.headless,
                    args=launch_args,
                    slow_mo=50,
                    **context_options
                )
                self.is_persistent_context = True
                self.browser = PersistentBrowserBridge(self.context)
                self.page = self.context.pages[0] if self.context.pages else await self.context.new_page()
                # Extra safety: also inject any existing standalone cookie backup
                await self._load_cookies()
            except Exception as e:
                logger.warning(
                    f"Persistent context launch failed for {self.platform_name.value} "
                    f"(profile locked or unavailable): {e}. Falling back to standard browser session."
                )
                self.is_persistent_context = False
                self.context = None

        # 2. Standard browser launch fallback if persistent context is disabled or failed
        if not self.context:
            try:
                self.browser = await self.playwright.chromium.launch(
                    headless=self.config.headless,
                    args=launch_args,
                    slow_mo=50,
                )
            except Exception:
                logger.exception(
                    "Failed to launch Playwright Chromium | headless=%s",
                    self.config.headless,
                )
                raise

            self.context = await self.browser.new_context(**context_options)
            await self._load_cookies()
            self.page = await self.context.new_page()

        mode_text = "headless mode" if self.config.headless else "visible mode"
        context_type = "persistent profile" if self.is_persistent_context else "standard session"
        await broadcaster.emit_log(
            f"🌐 Browser launched in {mode_text} ({context_type})",
            level=LogLevel.INFO,
            platform=self.platform_name.value
        )

        if not self.config.headless:
            try:
                await self.page.bring_to_front()
            except Exception:
                pass

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
        if self.context:
            try:
                await self._save_cookies()
            except Exception as e:
                logger.debug(f"Cookie save skipped/failed during teardown: {e}")
        if self.page:
            try:
                if not self.page.is_closed():
                    await self.page.close()
            except Exception:
                pass
            finally:
                self.page = None

        if self.is_persistent_context and self.context:
            try:
                if self.browser:
                    await self.browser.close()
                else:
                    await self.context.close()
            except Exception as e:
                logger.debug(f"Persistent context close error: {e}")
            finally:
                self.context = None
                self.browser = None
                self.is_persistent_context = False
        elif self.browser:
            try:
                await self.browser.close()
            except Exception as e:
                logger.debug(f"Browser close error during teardown: {e}")
            finally:
                self.browser = None
                self.context = None

        if self.playwright:
            try:
                await self.playwright.stop()
            except Exception as e:
                logger.debug(f"Playwright stop error during teardown: {e}")
            finally:
                self.playwright = None

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
                    if cookies and self.context:
                        await self.context.add_cookies(cookies)
                        logger.info(f"Loaded {len(cookies)} saved cookies for {self.platform_name.value}")
            except Exception as e:
                logger.warning(f"Could not load cookies for {self.platform_name.value}: {e}")

    def get_saved_cookies(self) -> List[Dict[str, Any]]:
        """Return list of saved cookies from disk."""
        if not self.cookie_file.exists():
            return []
        try:
            with open(self.cookie_file, "r", encoding="utf-8") as f:
                return json.load(f) or []
        except Exception:
            return []

    async def is_session_valid(self) -> bool:
        """
        Validate whether the current browser context or saved cookie file contains
        an active, non-expired authentication session for this platform.
        """
        cookies = []
        if self.context:
            try:
                cookies = await self.context.cookies()
            except Exception:
                pass

        if not cookies:
            cookies = self.get_saved_cookies()

        if not cookies:
            return False

        now_ts = datetime.now().timestamp()
        platform_lower = self.platform_name.value.lower()

        # Platform-specific auth indicator cookies
        auth_keys = {
            "naukri": ["naukri_auth", "acctype", "user", "nauk_auth", "profileid"],
            "linkedin": ["li_at", "li_a", "jsessionid", "bcookie", "bscookie"],
            "indeed": ["csrf", "surf", "ctk", "optimizelyenduserid"],
        }
        target_keys = auth_keys.get(platform_lower, ["auth", "token", "session", "user"])

        for cookie in cookies:
            cookie_name = cookie.get("name", "").lower()
            expires = cookie.get("expires", -1)

            # Check if expired
            if expires and expires > 0 and expires < now_ts:
                continue

            # Check if matches auth indicators
            if any(k in cookie_name for k in target_keys):
                return True

        return False

    def clear_saved_session(self, clear_profile_dir: bool = False):
        """Remove saved cookie file and optionally clear persistent profile cache."""
        if self.cookie_file.exists():
            try:
                self.cookie_file.unlink()
                logger.info(f"Cleared cookie file {self.cookie_file}")
            except Exception as e:
                logger.warning(f"Failed to delete cookie file: {e}")

        if clear_profile_dir and self.user_data_dir.exists():
            try:
                import shutil
                shutil.rmtree(self.user_data_dir, ignore_errors=True)
                logger.info(f"Cleared persistent profile directory {self.user_data_dir}")
            except Exception as e:
                logger.warning(f"Failed to clear user data dir: {e}")


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
            if self.stop_event.is_set():
                raise asyncio.CancelledError("Bot run cancelled by user.")
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

    async def dismiss_notification_prompts(self, target_page: Optional[Page] = None) -> bool:
        """Dismiss in-page notification banners or prompt overlays (e.g. 'Later', 'Not now', 'Block')."""
        page = target_page or self.page
        if not page:
            return False
        dismiss_selectors = [
            "button:has-text('Later')",
            "button:has-text('Maybe Later')",
            "button:has-text('Not now')",
            "button:has-text('Block')",
            "button:has-text('Remind me later')",
            "span:has-text('Later')",
            ".crossIcon",
            "[aria-label='Close notification']",
            ".notification-banner .close",
            ".push-notification-close"
        ]
        for sel in dismiss_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await btn.click()
                    await asyncio.sleep(0.3)
                    return True
            except Exception:
                pass
        return False

    async def human_scroll(self, distance: int = 400):
        """Simulate realistic human page scrolling."""
        if self.page:
            await self.dismiss_notification_prompts(self.page)
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
        try:
            pages = list(self.context.pages)
        except Exception:
            return
        for p in pages:
            try:
                if p != self.page and not p.is_closed():
                    await p.close()
            except Exception:
                pass

    def is_title_relevant(self, job_title: str) -> bool:
        """
        Check if job title matches candidate's actual qualifications and target stack.
        Filters out conflicting tech stacks (where candidate has 0 skills) and extreme seniority mismatches.
        """
        title_lower = job_title.lower()
        keywords_lower = (self.config.keywords or "").lower()

        # 1. Seniority Check: Filter executive / senior leadership roles for junior/mid candidates
        try:
            candidate_exp = float(getattr(self.profile, "years_of_experience", 2.0) or 2.0) if self.profile else 2.0
        except (ValueError, TypeError):
            candidate_exp = 2.0
        if candidate_exp <= 4.0:
            executive_markers = [
                "cto", "chief technology officer", "chief technical officer",
                "vice president", "vp -", "vp /", "vp,", "vp-", "vp:",
                "director of", "director -", "head of engineering", "head of technology",
                "principal architect", "enterprise architect"
            ]
            for marker in executive_markers:
                if marker in title_lower and marker not in keywords_lower:
                    logger.info(f"Skipping executive/leadership role for candidate with {candidate_exp} YOE: '{job_title}'")
                    return False

        # 2. Extract normalized candidate skills for cross-referencing
        candidate_skills = set()
        if self.profile and self.profile.skills:
            candidate_skills = {normalize_token(s) for s in self.profile.skills if s}
            if self.profile.work_experience:
                for exp in self.profile.work_experience:
                    for w in exp.title.lower().split():
                        candidate_skills.add(normalize_token(w))

        # 3. Define conflicting tech stack families
        # If title matches a family's patterns, candidate MUST have at least one skill in that family
        # (unless the user explicitly searched for that family in keywords)
        tech_families = [
            (
                "dotnet",
                [".net", "dotnet", "dot net", "asp.net", "c#", "csharp", "vb.net"],
                ["dotnet", ".net", "dot net", "aspnet", "c#", "csharp", "vbnet"]
            ),
            (
                "java",
                ["java full stack", "core java", "java developer", "spring boot", "springboot", "j2ee", "java/j2ee", "java backend", "java software"],
                ["java", "spring", "springboot", "spring boot", "hibernate", "j2ee"]
            ),
            (
                "angular",
                ["angular developer", "angularjs developer", "angular js developer", "angular/"],
                ["angular", "angularjs", "angular.js"]
            ),
            (
                "php",
                ["php developer", "laravel developer", "wordpress developer", "symfony developer", "codeigniter"],
                ["php", "laravel", "wordpress", "symfony", "codeigniter"]
            ),
            (
                "flutter",
                ["flutter developer", "dart developer", "flutter/"],
                ["flutter", "dart"]
            ),
            (
                "salesforce",
                ["salesforce", "sfdc", "apex developer"],
                ["salesforce", "sfdc", "apex"]
            ),
            (
                "aiml",
                ["ai ml", "ai/ml", "machine learning engineer", "data scientist", "deep learning", "nlp engineer", "computer vision"],
                ["machine learning", "deep learning", "nlp", "computer vision", "data science", "tensorflow", "pytorch", "ai ml"]
            ),
            (
                "qa_testing",
                ["qa automation", "automation test engineer", "qa engineer", "quality assurance engineer", "selenium", "tester", "manual testing"],
                ["qa automation", "selenium", "cypress", "automation testing", "manual testing", "qa"]
            ),
        ]

        for family_name, title_patterns, skill_tokens in tech_families:
            title_matches = any(p in title_lower for p in title_patterns)
            if title_matches:
                # If user explicitly searched for this family in keywords, allow it
                user_requested = any(p in keywords_lower for p in title_patterns)
                if user_requested:
                    continue

                # Check if candidate has ANY skill in this family
                cand_has_skill = any(normalize_token(st) in candidate_skills for st in skill_tokens)
                if not cand_has_skill:
                    logger.info(f"Skipping non-matching tech stack role: '{job_title}' (candidate has no {family_name} experience in resume)")
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

    async def upload_resume_copy(self, page: Page) -> bool:
        """Explicitly find and attach candidate resume PDF copy to the page or form."""
        if not self.resume_file_path or not self.resume_file_path.exists():
            return False

        try:
            # 1. Search all file input elements on page (visible or hidden)
            file_inputs = await page.query_selector_all("input[type='file']")
            if file_inputs:
                for file_input in file_inputs:
                    try:
                        await file_input.set_input_files(str(self.resume_file_path))
                        await broadcaster.emit_log(
                            f"📄 Attached resume copy: {self.resume_file_path.name}",
                            level=LogLevel.SUCCESS,
                            platform=self.platform_name.value
                        )
                        return True
                    except Exception:
                        continue

            # 2. Check all iframe frames for file inputs
            for frame in page.frames:
                try:
                    frame_inputs = await frame.query_selector_all("input[type='file']")
                    for f_in in frame_inputs:
                        await f_in.set_input_files(str(self.resume_file_path))
                        await broadcaster.emit_log(
                            f"📄 Attached resume copy inside frame: {self.resume_file_path.name}",
                            level=LogLevel.SUCCESS,
                            platform=self.platform_name.value
                        )
                        return True
                except Exception:
                    continue

            # 3. Check for custom dropzones or upload buttons that open file choosers
            upload_triggers = [
                "button:has-text('Upload Resume')",
                "button:has-text('Attach Resume')",
                "button:has-text('Upload CV')",
                "a:has-text('Upload Resume')",
                "div[class*='resume-upload']",
                "div[class*='dropzone']",
                "div[data-automation-id*='file-upload']"
            ]
            for trigger in upload_triggers:
                try:
                    btn = await page.query_selector(trigger)
                    if btn and await btn.is_visible():
                        async with page.expect_file_chooser(timeout=3000) as fc_info:
                            await btn.click()
                        file_chooser = await fc_info.value
                        await file_chooser.set_files(str(self.resume_file_path))
                        await broadcaster.emit_log(
                            f"📄 Attached resume copy via file chooser: {self.resume_file_path.name}",
                            level=LogLevel.SUCCESS,
                            platform=self.platform_name.value
                        )
                        return True
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Error uploading resume copy: {e}")
        return False

    async def fill_form_with_llm(
        self,
        job_title: str,
        company: str,
        target_page: Optional[Page] = None,
        container: Optional[ElementHandle] = None
    ) -> bool:
        """Scan form fields, request LLM mapping with heuristic fallback, and fill inputs accurately."""
        page = target_page or self.page
        if not page:
            return False

        fields = await self.scan_form_fields(target_page=page, container=container)
        if not fields:
            return True

        job_context = {"title": job_title, "company": company}
        profile_dict = self.profile.model_dump()

        # Step 1: Request LLM field mapping
        mapping = {}
        try:
            raw_map = await llm_client.map_form_fields(profile_dict, fields, job_context)
            if isinstance(raw_map, dict):
                mapping = raw_map
            logger.info(f"LLM field mapping for {job_title}: {mapping}")
        except Exception as e:
            logger.warning(f"LLM mapping error (using heuristic fallback): {e}")

        # Step 2: Instant smart heuristic fallback for any missed fields
        for field in fields:
            f_id = field.get("id")
            f_name = field.get("name")
            combined = f"{field.get('label', '')} {f_name} {field.get('placeholder', '')}".lower()

            if f_id not in mapping and f_name not in mapping:
                if any(w in combined for w in ["first name", "firstname", "given name", "first_name"]):
                    val = self.profile.full_name.split()[0] if self.profile.full_name else ""
                    mapping[f_id] = val
                elif any(w in combined for w in ["last name", "lastname", "surname", "family name", "last_name"]):
                    parts = self.profile.full_name.split() if self.profile.full_name else []
                    mapping[f_id] = parts[-1] if len(parts) > 1 else ""
                elif any(w in combined for w in ["full name", "your name", "candidate name", "name"]):
                    mapping[f_id] = self.profile.full_name
                elif any(w in combined for w in ["email", "e-mail"]):
                    mapping[f_id] = self.profile.email
                elif any(w in combined for w in ["phone", "mobile", "contact", "cell", "tel"]):
                    mapping[f_id] = self.profile.phone
                elif "linkedin" in combined:
                    mapping[f_id] = self.profile.linkedin_url or ""
                elif "github" in combined:
                    mapping[f_id] = self.profile.github_url or ""
                elif any(w in combined for w in ["portfolio", "website", "site", "url"]):
                    mapping[f_id] = self.profile.portfolio_url or ""
                elif any(w in combined for w in ["location", "city", "address"]):
                    mapping[f_id] = self.profile.location or ""
                elif any(w in combined for w in ["experience", "years of exp", "total exp"]):
                    mapping[f_id] = str(self.profile.years_of_experience)
                elif any(w in combined for w in ["notice", "notice period"]):
                    mapping[f_id] = "Immediate"
                elif any(w in combined for w in ["current ctc", "present ctc", "current salary", "fixed ctc"]):
                    mapping[f_id] = str(self.profile.custom_answers.get("current_ctc_lpa", "Negotiable"))
                elif any(w in combined for w in ["expected ctc", "expected salary"]):
                    mapping[f_id] = str(self.profile.custom_answers.get("expected_ctc_lpa", "Negotiable"))
                elif any(w in combined for w in ["current company", "current employer", "organization", "present company"]):
                    mapping[f_id] = self.profile.work_experience[0].company if self.profile.work_experience else ""
                elif any(w in combined for w in ["designation", "current role", "current title", "job title"]):
                    mapping[f_id] = self.profile.work_experience[0].title if self.profile.work_experience else ""
                elif any(w in combined for w in ["qualification", "highest degree", "education", "degree"]):
                    mapping[f_id] = self.profile.education[0].degree if self.profile.education else ""
                elif any(w in combined for w in ["key skills", "primary skill", "technical skill"]):
                    mapping[f_id] = ", ".join(self.profile.skills[:5]) if self.profile.skills else ""

        # Step 3: Populate each field using direct DOM handles
        for field in fields:
            await self.check_pause_and_stop()
            field_idx = field.get("index", 0)
            field_id = field.get("id")
            field_name = field.get("name")
            field_type = field.get("type", "text").lower()
            field_tag = field.get("tag", "input").lower()

            target_val = mapping.get(field_id) or mapping.get(field_name)

            elem_handle = None
            try:
                # Retrieve exact element via DOM index scoped to container if provided
                if container:
                    elem_handle = await container.evaluate_handle(
                        """(root, idx) => {
                            const scope = root || document;
                            const inputs = scope.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), select, textarea');
                            return inputs[idx] || null;
                        }""",
                        field_idx
                    )
                else:
                    elem_handle = await page.evaluate_handle(
                        """(idx) => {
                            const inputs = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), select, textarea');
                            return inputs[idx] || null;
                        }""",
                        field_idx
                    )

                elem = elem_handle.as_element() if elem_handle else None
                if not elem:
                    continue

                if field_type == "file":
                    # File upload works on hidden inputs as well!
                    if self.resume_file_path and self.resume_file_path.exists():
                        await elem.set_input_files(str(self.resume_file_path))
                        await broadcaster.emit_log(f"📎 Attached resume file: {self.resume_file_path.name}", platform=self.platform_name.value)
                    continue

                if not await elem.is_visible():
                    continue

                if target_val is None or target_val == "":
                    continue

                if field_type in ["checkbox"]:
                    should_check = bool(target_val)
                    is_checked = await elem.is_checked()
                    if should_check != is_checked:
                        await elem.click(timeout=3000)
                elif field_type in ["radio"]:
                    await elem.click(timeout=3000)
                elif field_tag == "select":
                    try:
                        await elem.select_option(label=str(target_val), timeout=3000)
                    except Exception:
                        try:
                            await elem.select_option(value=str(target_val), timeout=3000)
                        except Exception:
                            try:
                                opt_val = await elem.evaluate(
                                    """(sel, val) => {
                                        const target = (val || '').toLowerCase();
                                        for (const opt of sel.options) {
                                            if (opt.text.toLowerCase().includes(target) || opt.value.toLowerCase().includes(target)) {
                                                return opt.value;
                                            }
                                        }
                                        return null;
                                    }""",
                                    str(target_val)
                                )
                                if opt_val is not None:
                                    await elem.select_option(value=opt_val, timeout=3000)
                            except Exception:
                                pass
                else: # text, email, tel, number, textarea
                    try:
                        await elem.click(timeout=3000)
                        await elem.fill(str(target_val), timeout=3000)
                    except Exception:
                        await self.human_type(elem, str(target_val))
                
                await asyncio.sleep(0.15)
            except Exception as e:
                logger.warning(f"Could not fill field {field_id}: {e}")
            finally:
                if elem_handle:
                    try:
                        await elem_handle.dispose()
                    except Exception:
                        pass

        return True

    async def apply_external_portal(self, page: Page, job_title: str, company: str) -> bool:
        """
        Universally traverse, scan, auto-fill and submit an external company portal application
        (Workday, Greenhouse, Lever, SmartRecruiters, Taleo, Ashby, Jobvite, direct forms).
        """
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=15000)
            await asyncio.sleep(3)
            
            # Step 1: Check for introductory "Apply" / "Apply Now" buttons
            apply_triggers = [
                "button:has-text('Apply for this job')",
                "a:has-text('Apply for this job')",
                "button:has-text('Apply Now')",
                "a:has-text('Apply Now')",
                "button:has-text('Apply with Resume')",
                "button:has-text('Apply')",
                "#apply-button",
                ".apply-button",
                "a[href*='apply']"
            ]
            for trigger in apply_triggers:
                try:
                    btn = await page.query_selector(trigger)
                    if btn and await btn.is_visible():
                        await broadcaster.emit_log(f"Opening external application form on {company}...", platform=self.platform_name.value)
                        await btn.click()
                        await asyncio.sleep(2)
                        break
                except Exception:
                    continue

            # Scroll page down to trigger lazy-loaded sections
            try:
                await page.mouse.wheel(0, 500)
                await asyncio.sleep(1)
            except Exception:
                pass

            max_steps = 3
            current_step = 0

            while current_step < max_steps:
                current_step += 1
                await self.check_pause_and_stop()

                # Check for CAPTCHA on external page
                for indicator in ["iframe[src*='recaptcha']", "iframe[src*='hcaptcha']", "div.g-recaptcha", "#challenge-running"]:
                    try:
                        captcha_el = await page.query_selector(indicator)
                        if captcha_el and await captcha_el.is_visible():
                            await broadcaster.emit_log("⚠️ CAPTCHA detected on external site! Pausing for manual user resolution...", level=LogLevel.WARNING, platform=self.platform_name.value)
                            if self.pause_event:
                                self.pause_event.clear()
                            await self.check_pause_and_stop()
                    except Exception:
                        pass

                # Explicitly upload resume copy if upload zones / file inputs exist
                await self.upload_resume_copy(page)

                # Scan and fill all fields on current step
                fields = await self.scan_form_fields(target_page=page)
                if fields:
                    await broadcaster.emit_log(f"🤖 Auto-filling {len(fields)} form fields with local AI for {company}...", platform=self.platform_name.value)
                    await self.fill_form_with_llm(job_title, company, target_page=page)

                # Check for "Next" / "Continue" vs final "Submit"
                next_btn = await page.query_selector(
                    "button:has-text('Next'), button:has-text('Continue'), button:has-text('Save and Continue'), button:has-text('Save & Continue'), input[value='Next'], input[value='Continue'], button[data-automation-id*='next']"
                )
                submit_btn = await page.query_selector(
                    "button[type='submit'], button:has-text('Submit Application'), button:has-text('Submit'), button:has-text('Submit your application'), input[type='submit'], button:has-text('Send Application'), button:has-text('Apply'), button[data-automation-id*='submit']"
                )

                if next_btn and await next_btn.is_visible() and (not submit_btn or not await submit_btn.is_visible()):
                    await broadcaster.emit_log(f"Proceeding to next step on {company} application...", platform=self.platform_name.value)
                    if not self.config.dry_run:
                        clicked = await self.safe_click(next_btn, timeout=4000)
                        if not clicked:
                            await next_btn.click(timeout=3000)
                        await asyncio.sleep(3)
                        continue

                # If final submit is available
                if submit_btn and await submit_btn.is_visible():
                    if not self.config.dry_run:
                        await broadcaster.emit_log(f"Submitting final application to {company}...", level=LogLevel.ACTION, platform=self.platform_name.value)
                        clicked = await self.safe_click(submit_btn, timeout=5000)
                        if not clicked:
                            await submit_btn.click(timeout=4000)
                        await asyncio.sleep(3)
                    return True

                if fields:
                    return True
                break

            return True
        except Exception as e:
            logger.error(f"Error traversing external portal: {e}")
            return False

    async def check_external_requires_login(self, page: Page) -> Tuple[bool, str]:
        """
        Check if an external company application portal requires user login / registration
        before allowing form submission.
        """
        try:
            # 1. Check for password input fields
            password_input = await page.query_selector("input[type='password']")
            if password_input and await password_input.is_visible():
                return (True, "Company site requires login (password field detected)")

            # 2. Check for explicit login / sign-in buttons or links
            login_selectors = [
                "button:has-text('Sign In to Apply')",
                "a:has-text('Sign In to Apply')",
                "button:has-text('Log in to apply')",
                "a:has-text('Log in to apply')",
                "button:has-text('Log in with')",
                "button:has-text('Sign in with')",
                "a[data-automation-id='signInLink']",
                "button[data-automation-id='signInSubmitButton']",
                "div[data-automation-id='signInContainer']",
                "#workday-login",
                ".login-container",
                ".login-form",
                "form#login-form",
                "form[action*='login']",
                "form[action*='signin']"
            ]
            for sel in login_selectors:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    return (True, "Company site requires login / account creation")

            # 3. Check text content for login requirement cues
            page_text = (await page.inner_text("body")).lower()
            login_phrases = [
                "please sign in to apply",
                "sign in to apply for this job",
                "you must be logged in to apply",
                "log in or create an account to apply",
                "sign in with your account to apply",
                "create an account to apply",
                "login required to apply"
            ]
            for phrase in login_phrases:
                if phrase in page_text:
                    return (True, "Company site requires login / account creation")

            return (False, "")
        except Exception as e:
            logger.debug(f"Error checking login requirement on external portal: {e}")
            return (False, "")

    async def safe_click(self, element: Optional[ElementHandle], timeout: int = 5000) -> bool:
        """
        Safely scrolls element into view, confirms visibility and enabled state, and clicks.
        Returns True if click succeeded; returns False on timeout, detachment, or interception.
        """
        if not element:
            return False
        try:
            await element.scroll_into_view_if_needed(timeout=timeout)
            await element.wait_for_element_state("visible", timeout=timeout)
            await element.wait_for_element_state("enabled", timeout=timeout)
        except Exception as e:
            logger.debug(f"safe_click state verification failed: {e}")
            return False

        try:
            await element.click(timeout=timeout)
            return True
        except Exception as e:
            logger.debug(f"safe_click standard click failed ({e}); attempting resilient JS click fallback")
            try:
                await element.evaluate("(el) => { el.scrollIntoView({block: 'center'}); el.click(); }")
                return True
            except Exception as e2:
                logger.debug(f"safe_click resilient fallback failed: {e2}")
                return False

    async def initialize_session(self) -> bool:
        """Verify session credentials, cookie validity, profile availability, and search connectivity."""
        return await self.is_logged_in()

    def get_attempt_id(self, job_id: str) -> str:
        """Generate unique application attempt ID for traceability."""
        seq = self.attempt_counters.get(job_id, 0) + 1
        self.attempt_counters[job_id] = seq
        clean_id = job_id.replace("JOB-", "") if job_id else "unknown"
        return f"ATTEMPT-{clean_id}-{seq:02d}"

    async def with_retry(self, coro_func, max_retries: int = 3, base_delay: float = 1.0, op_name: str = "operation"):
        """Bounded exponential retry helper for idempotent actions (DOM wait, network goto)."""
        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                return await coro_func()
            except Exception as e:
                last_exc = e
                if attempt == max_retries:
                    logger.warning(f"{op_name} failed after {max_retries} attempts: {e}")
                    raise
                jitter = random.uniform(-0.2, 0.2)
                delay = (base_delay * (2 ** (attempt - 1))) + jitter
                await asyncio.sleep(max(0.2, delay))
        raise last_exc

    async def verify_application_result(self, target_page: Optional[Page] = None) -> VerificationResult:
        """Inspect page for confirmed application submission or failure signals."""
        return VerificationResult.UNKNOWN

    def record_job_result(
        self,
        job_title: str,
        company: str,
        job_url: str,
        status: ApplicationStatus,
        notes: str = "",
        hr_email: Optional[str] = None,
        recruiter_name: Optional[str] = None,
        match_score: Optional[int] = None,
        contacts: Optional[List[Any]] = None,
        skip_reason: Optional[str] = None,
        suggested_outreach: Optional[str] = None,
        application_type: str = "quick_apply",
        job_id: Optional[str] = None,
        application_attempt_id: Optional[str] = None,
        job_quality_score: Optional[int] = None,
        priority_score: Optional[int] = None,
        priority_reasons: Optional[List[str]] = None,
        risk_flags: Optional[List[str]] = None,
        risk_evidence: Optional[Dict[str, str]] = None,
        reason_code: Optional[ReasonCode | str] = None,
        status_reason: Optional[str] = None,
        lifecycle_status: Optional[JobLifecycleStatus] = None
    ) -> JobApplicationRecord:
        """Construct and write record to Excel and emit status log. Raises PersistenceError if write fails."""
        if lifecycle_status is None:
            status_val = status.value if isinstance(status, ApplicationStatus) else str(status)
            if "Manual" in status_val:
                lifecycle_status = JobLifecycleStatus.MANUAL_REVIEW
            elif "Success" in status_val or "Applied" in status_val:
                lifecycle_status = JobLifecycleStatus.SUCCESS
            elif "Failed" in status_val:
                lifecycle_status = JobLifecycleStatus.FAILED
            elif "Skipped" in status_val:
                lifecycle_status = JobLifecycleStatus.SKIPPED
            elif "Duplicate" in status_val:
                lifecycle_status = JobLifecycleStatus.POSSIBLE_DUPLICATE
            elif "Discovered" in status_val:
                lifecycle_status = JobLifecycleStatus.DISCOVERED
            elif "Progress" in status_val:
                lifecycle_status = JobLifecycleStatus.APPLYING
            else:
                lifecycle_status = JobLifecycleStatus.ANALYZED

        record = JobApplicationRecord(
            job_id=job_id,
            run_id=self.run_id,
            application_attempt_id=application_attempt_id,
            platform=self.platform_name.value,
            job_title=job_title or "Job Position",
            company=company or "Company",
            job_url=job_url or "",
            status=status,
            lifecycle_status=lifecycle_status,
            application_type=application_type,
            notes=notes,
            hr_email=hr_email,
            recruiter_name=recruiter_name,
            match_score=match_score,
            contacts=[c.model_dump() if hasattr(c, "model_dump") else c for c in (contacts or [])],
            skip_reason=skip_reason or status_reason,
            suggested_outreach=suggested_outreach,
            job_quality_score=job_quality_score,
            priority_score=priority_score,
            priority_reasons=priority_reasons or [],
            risk_flags=risk_flags or [],
            risk_evidence=risk_evidence or {},
            reason_code=str(reason_code.value if isinstance(reason_code, ReasonCode) else reason_code) if reason_code else None,
            status_reason=status_reason or skip_reason,
            lifecycle_history=[{
                "status": str(status.value if isinstance(status, ApplicationStatus) else status),
                "lifecycle_status": str(lifecycle_status.value if isinstance(lifecycle_status, JobLifecycleStatus) else (lifecycle_status or "")),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "reason_code": str(reason_code.value if isinstance(reason_code, ReasonCode) else reason_code) if reason_code else "",
                "notes": notes
            }]
        )
        saved = excel_tracker.log_application(record)
        if not saved:
            raise PersistenceError(f"Failed to persist application record for '{job_title}' at '{company}' to Excel tracker.")
        return record

    @abstractmethod
    async def login(self) -> bool:
        """Authenticate on the platform."""
        pass

    @abstractmethod
    async def search_and_apply(self) -> int:
        """Search jobs and apply up to configured max applications."""
        pass

    def detect(self, url: str, page_content: Optional[str] = None) -> bool:
        """Default platform URL detection."""
        return self.platform_name.value.lower() in url.lower()

    async def authenticate(self) -> bool:
        """Adapter bridge to login."""
        return await self.login()

    async def extract_form(self, page: Any) -> Dict[str, Any]:
        """Extract interactive form fields from page."""
        fields = []
        try:
            inputs = await page.query_selector_all("input, select, textarea")
            for inp in inputs:
                name = await inp.get_attribute("name") or await inp.get_attribute("id") or ""
                if name:
                    fields.append(name)
        except Exception:
            pass
        return {"fields": fields}

    async def fill_form(
        self,
        page: Any,
        profile: ResumeProfile,
        qa_vault: Optional[QAVault] = None
    ) -> Dict[str, Any]:
        """Base fill_form implementation."""
        return {"status": "filled"}

    async def submit(self, page: Any) -> bool:
        """Attempt safe click on submit buttons."""
        submit_selectors = [
            "button[type='submit']",
            "button:has-text('Submit')",
            "button:has-text('Apply')",
            "button:has-text('Submit Application')"
        ]
        for sel in submit_selectors:
            try:
                btn = await page.query_selector(sel)
                if btn and await btn.is_visible():
                    await self.safe_click(btn, op_name="Submit Application")
                    return True
            except Exception:
                continue
        return False

    async def verify_submission(self, page: Any) -> Tuple[bool, str]:
        """Bridge to verify_application_result."""
        res = await self.verify_application_result(page)
        if res == VerificationResult.CONFIRMED_SUCCESS:
            return True, "Application verified as submitted."
        elif res == VerificationResult.CONFIRMED_FAILURE:
            return False, "Application failed or rejected."
        return False, "Submission status unverified or pending."

    async def apply(
        self,
        job_url: str,
        profile: ResumeProfile,
        qa_vault: Optional[QAVault] = None
    ) -> AdapterApplicationResult:
        """Base adapter application pipeline bridge."""
        return AdapterApplicationResult(
            success=False,
            status=ApplicationStatus.FAILED,
            job_url=job_url,
            message="BasePlatform does not implement standalone URL apply directly."
        )

