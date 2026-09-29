import sys
import asyncio
import threading
from datetime import datetime
from typing import Optional, Dict, Any

from app.core.config import settings
from app.core.logger import broadcaster, logger
from app.models.job import (
    BotState,
    BotStatusResponse,
    SearchConfig,
    PlatformEnum,
    LogLevel,
    ResumeProfile,
    ApplicationStatus,
    ReasonCode
)
from app.platforms.naukri_helpers import detect_application_limit
from app.services.resume_parser import resume_parser_service
from app.platforms.linkedin import LinkedInPlatform
from app.platforms.naukri import NaukriPlatform
from app.platforms.indeed import IndeedPlatform
from app.platforms.dindin import DindinPlatform
from app.services.orchestrator import orchestrator

class BotManager:
    def __init__(self):
        self.state: BotState = BotState.IDLE
        self.current_platform: Optional[str] = None
        self.current_job: Optional[str] = None
        self.applied_count: int = 0
        self.success_count: int = 0
        self.failed_count: int = 0
        self.skipped_count: int = 0
        self.total_target: int = 0
        self.start_time: Optional[str] = None
        self.is_paused_for_captcha: bool = False
        self.captcha_message: Optional[str] = None

        self._worker_thread: Optional[threading.Thread] = None
        self._worker_loop: Optional[asyncio.AbstractEventLoop] = None
        self._pause_event: Optional[asyncio.Event] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._current_bot_instance = None
        self._state_lock = threading.Lock()

    def get_status(self) -> BotStatusResponse:
        with self._state_lock:
            return BotStatusResponse(
                state=self.state,
                current_platform=self.current_platform,
                current_job=self.current_job,
                applied_count=self.applied_count,
                success_count=self.success_count,
                failed_count=self.failed_count,
                skipped_count=self.skipped_count,
                total_target=self.total_target,
                is_paused_for_captcha=self.is_paused_for_captcha,
                captcha_message=self.captcha_message,
                start_time=self.start_time
            )

    async def start(self, config: SearchConfig) -> Dict[str, Any]:
        """Start the automated job application background task."""
        with self._state_lock:
            if self.state == BotState.RUNNING:
                return {"success": False, "message": "Bot is already running."}
            if self._worker_thread and self._worker_thread.is_alive():
                return {"success": False, "message": "Previous bot run is still stopping. Please wait a moment."}

            profile = resume_parser_service.load_profile()
            if not profile:
                return {
                    "success": False,
                    "message": "No candidate resume profile found. Please upload a resume before starting the bot."
                }

            # Reset state counters
            self.state = BotState.RUNNING
            self.current_platform = None
            self.current_job = None
            self.applied_count = 0
            self.success_count = 0
            self.failed_count = 0
            self.skipped_count = 0
            self.total_target = config.max_applications
            self.start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.is_paused_for_captcha = False
            self.captcha_message = None

            # Launch background worker thread with WindowsProactorEventLoopPolicy
            self._worker_thread = threading.Thread(
                target=self._worker_thread_entry,
                args=(config, profile),
                daemon=True
            )
            self._worker_thread.start()
        
        await broadcaster.emit_log(
            f"🚀 Bot started! Target: {config.max_applications} applications across {len(config.platforms)} platforms.",
            level=LogLevel.INFO
        )
        return {"success": True, "message": "Bot started successfully in background."}

    def _worker_thread_entry(self, config: SearchConfig, profile: ResumeProfile):
        """Worker thread entry point creating a Proactor event loop on Windows."""
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._worker_loop = loop
        self._pause_event = asyncio.Event()
        self._pause_event.set()
        self._stop_event = asyncio.Event()

        try:
            loop.run_until_complete(self._run_orchestrator(config, profile))
        except Exception as e:
            logger.error(f"Worker thread error: {e}")
        finally:
            with self._state_lock:
                self.state = BotState.IDLE
                self.current_platform = None
                self.current_job = None
            try:
                loop.close()
            except Exception:
                pass
            self._worker_loop = None

    async def pause(self, reason: Optional[str] = None) -> Dict[str, Any]:
        """Pause running bot."""
        with self._state_lock:
            if self.state != BotState.RUNNING:
                return {"success": False, "message": "Bot is not running."}

            self.state = BotState.PAUSED
            if self._worker_loop and self._worker_loop.is_running() and self._pause_event:
                self._worker_loop.call_soon_threadsafe(self._pause_event.clear)

            if reason:
                self.is_paused_for_captcha = True
                self.captcha_message = reason

        await broadcaster.emit_log(
            f"⏸️ Bot has been paused. {reason or ''}",
            level=LogLevel.WARNING,
            platform=self.current_platform
        )
        return {"success": True, "message": "Bot paused."}

    async def resume(self) -> Dict[str, Any]:
        """Resume paused bot."""
        with self._state_lock:
            if self.state != BotState.PAUSED:
                return {"success": False, "message": "Bot is not paused."}

            self.state = BotState.RUNNING
            self.is_paused_for_captcha = False
            self.captcha_message = None
            if self._worker_loop and self._worker_loop.is_running() and self._pause_event:
                self._worker_loop.call_soon_threadsafe(self._pause_event.set)

        await broadcaster.emit_log("▶️ Bot execution resumed by user.", level=LogLevel.INFO, platform=self.current_platform)
        return {"success": True, "message": "Bot resumed."}

    async def stop(self) -> Dict[str, Any]:
        """Stop and cancel running bot execution."""
        with self._state_lock:
            if self.state == BotState.IDLE or self.state == BotState.STOPPED:
                return {"success": False, "message": "Bot is already idle or stopped."}

            self.state = BotState.STOPPED
            if self._worker_loop and self._worker_loop.is_running():
                if self._stop_event:
                    self._worker_loop.call_soon_threadsafe(self._stop_event.set)
                if self._pause_event:
                    self._worker_loop.call_soon_threadsafe(self._pause_event.set)

        await broadcaster.emit_log("🛑 Bot execution stopped by user.", level=LogLevel.INFO, platform=self.current_platform)
        return {"success": True, "message": "Bot stopped."}

    async def update_naukri_headline(self, headline: str) -> Dict[str, Any]:
        """Update candidate resume headline on Naukri reusing stored cookies."""
        if self.state == BotState.RUNNING:
            return {"success": False, "message": "Bot is currently running. Please wait or stop the bot before updating your profile."}

        profile = resume_parser_service.load_profile() or ResumeProfile()
        config = SearchConfig(headless=False)
        bot_instance = NaukriPlatform(config=config, profile=profile)

        try:
            await bot_instance.init_browser()
            logged_in = await bot_instance.login()
            if not logged_in:
                return {"success": False, "message": "Could not authenticate to Naukri to update headline."}
            
            success = await bot_instance.update_profile_headline(headline)
            return {"success": success, "message": "Headline update succeeded." if success else "Headline update failed."}
        except Exception as e:
            logger.error(f"Error in update_naukri_headline: {e}")
            return {"success": False, "message": str(e)}
        finally:
            await bot_instance.close_browser()

    async def run_preflight_check(self, config: Optional[SearchConfig] = None) -> Dict[str, Any]:
        """Execute automated preflight verification on all critical bot prerequisites."""
        checks = {}
        has_errors = False
        has_warnings = False

        # 1. Candidate Profile & Resume File
        profile = resume_parser_service.load_profile()
        resume_exists = settings.RESUME_FILE_PATH.exists()

        if not profile and not resume_exists:
            checks["profile"] = {
                "status": "error",
                "message": "Candidate profile and resume PDF not found. Please upload a resume first."
            }
            has_errors = True
        elif not profile and resume_exists:
            checks["profile"] = {
                "status": "warning",
                "message": "Resume PDF found, but candidate_profile.json not parsed. Profile will parse on launch."
            }
            has_warnings = True
        else:
            skill_count = len(profile.skills) if profile.skills else 0
            if skill_count < 3:
                checks["profile"] = {
                    "status": "warning",
                    "message": f"Profile loaded ({profile.name or 'Candidate'}), but only {skill_count} skills detected. Match scoring accuracy may be reduced."
                }
                has_warnings = True
            else:
                checks["profile"] = {
                    "status": "ok",
                    "message": f"Profile ready: {profile.name or 'Candidate'} with {skill_count} detected skills."
                }

        # 2. Storage System & Excel Write Access
        try:
            excel_path = settings.EXCEL_FILE_PATH
            excel_dir = excel_path.parent
            excel_dir.mkdir(parents=True, exist_ok=True)
            test_file = excel_dir / ".write_test.tmp"
            test_file.write_text("ok", encoding="utf-8")
            test_file.unlink(missing_ok=True)
            checks["storage"] = {
                "status": "ok",
                "message": f"Persistence storage accessible at {excel_path.name}."
            }
        except Exception as e:
            checks["storage"] = {
                "status": "error",
                "message": f"Persistence storage not writable: {str(e)}"
            }
            has_errors = True

        # 3. LLM Configuration
        gemini_key = getattr(settings, "GEMINI_API_KEY", None)
        gemini_model = getattr(settings, "GEMINI_MODEL", "gemini-pro")
        if gemini_key:
            checks["llm"] = {
                "status": "ok",
                "message": f"Gemini LLM configured with model '{gemini_model}'."
            }
        elif settings.OLLAMA_BASE_URL:
            checks["llm"] = {
                "status": "ok",
                "message": f"Ollama local LLM configured at {settings.OLLAMA_BASE_URL}."
            }
        else:
            checks["llm"] = {
                "status": "warning",
                "message": "No LLM API key or Ollama endpoint configured. Chatbot questionnaires will fallback to profile answers."
            }
            has_warnings = True

        # 4. Platforms & Authentication
        platforms_to_check = config.platforms if (config and config.platforms) else [PlatformEnum.NAUKRI, PlatformEnum.LINKEDIN]
        cookie_dir = getattr(settings, "COOKIE_DIR", None) or getattr(settings, "COOKIES_DIR", settings.DATA_PATH / "cookies")
        platform_checks = {}
        for p in platforms_to_check:
            if p == PlatformEnum.NAUKRI:
                has_creds = bool((getattr(settings, "NAUKRI_USERNAME", None) or getattr(settings, "NAUKRI_EMAIL", None)) and settings.NAUKRI_PASSWORD)
                cookie_exists = (cookie_dir / "naukri_cookies.json").exists()
                if has_creds or cookie_exists:
                    platform_checks["naukri"] = {
                        "status": "ok",
                        "message": "Credentials or saved session cookies found."
                    }
                else:
                    platform_checks["naukri"] = {
                        "status": "warning",
                        "message": "No Naukri credentials or saved cookies found in .env."
                    }
                    has_warnings = True
            elif p == PlatformEnum.LINKEDIN:
                has_creds = bool((getattr(settings, "LINKEDIN_USERNAME", None) or getattr(settings, "LINKEDIN_EMAIL", None)) and settings.LINKEDIN_PASSWORD)
                cookie_exists = (cookie_dir / "linkedin_cookies.json").exists()
                if has_creds or cookie_exists:
                    platform_checks["linkedin"] = {
                        "status": "ok",
                        "message": "Credentials or saved session cookies found."
                    }
                else:
                    platform_checks["linkedin"] = {
                        "status": "warning",
                        "message": "No LinkedIn credentials or saved cookies found in .env."
                    }
                    has_warnings = True
            else:
                platform_checks[p.value] = {"status": "ok", "message": "Public platform ready."}

        checks["platforms"] = platform_checks

        overall_status = "FAILED" if has_errors else ("WARNINGS" if has_warnings else "PASSED")
        return {
            "overall": overall_status,
            "passed": not has_errors,
            "checks": checks
        }

    async def apply_now_manual_job(self, job_url: str) -> Dict[str, Any]:
        """Execute the exact same safety pipeline for a job in manual review queue:
        Revalidate profile -> Revalidate duplicate status -> Revalidate session ->
        Check platform limits -> Persist APPLYING -> Safely apply -> Verify result.
        """
        from app.services.excel_tracker import excel_tracker
        from app.platforms.base import VerificationResult
        import hashlib

        current_status = excel_tracker.get_processed_status(job_url)
        if current_status == ApplicationStatus.SUCCESS.value:
            return {"success": False, "message": "Job is already marked as SUCCESS/Applied."}

        profile = resume_parser_service.load_profile()
        if not profile:
            return {"success": False, "message": "No candidate profile found. Upload resume first."}

        config = SearchConfig(headless=False)
        bot_instance = NaukriPlatform(config=config, profile=profile)
        job_id = f"JOB-{hashlib.md5(job_url.encode('utf-8')).hexdigest()[:8]}"
        attempt_id = bot_instance.get_attempt_id(job_id)

        try:
            await bot_instance.init_browser()
            logged_in = await bot_instance.login()
            if not logged_in:
                return {"success": False, "message": "Authentication failed during manual apply attempt."}

            page = await bot_instance.context.new_page()
            await page.goto(job_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2)

            # Limit check
            limit_reason = await detect_application_limit(page)
            if limit_reason:
                excel_tracker.update_application_status(
                    job_url,
                    ApplicationStatus.FAILED,
                    notes=f"Application limit: {limit_reason}",
                    reason_code=ReasonCode.APPLICATION_LIMIT
                )
                return {"success": False, "message": f"Platform application limit reached: {limit_reason}"}

            # Locate Apply button
            apply_btn = await page.query_selector("#apply-button, button.apply-button, .apply-message, button:has-text('Apply'), a:has-text('Apply')")
            if not apply_btn:
                return {"success": False, "message": "Apply button not found on job page."}

            btn_text = (await apply_btn.inner_text()).lower()
            if "company site" in btn_text or "redirect" in btn_text or "website" in btn_text:
                excel_tracker.update_application_status(
                    job_url,
                    ApplicationStatus.SKIPPED,
                    notes="External apply button (Never apply on external ATS)",
                    reason_code=ReasonCode.EXTERNAL_APPLICATION
                )
                return {"success": False, "message": "External ATS redirect detected. Safety policy forbids automated external application."}

            # Persist APPLYING state before clicking apply
            excel_tracker.update_application_status(
                job_url,
                ApplicationStatus.APPLYING,
                notes=f"Manual Apply Attempt {attempt_id}: Executing safety pipeline"
            )

            # Click Apply
            clicked = await bot_instance.safe_click(apply_btn)
            if not clicked:
                excel_tracker.update_application_status(
                    job_url,
                    ApplicationStatus.FAILED,
                    notes="Could not safely click Apply button during manual attempt"
                )
                return {"success": False, "message": "Could not safely click Apply button."}

            await asyncio.sleep(2)
            await bot_instance.handle_naukri_chatbot(page, "Manual Apply Role", "Company")

            # Post-submission limit check
            limit_reason = await detect_application_limit(page)
            if limit_reason:
                excel_tracker.update_application_status(
                    job_url,
                    ApplicationStatus.FAILED,
                    notes=f"Application limit: {limit_reason}",
                    reason_code=ReasonCode.APPLICATION_LIMIT
                )
                return {"success": False, "message": f"Platform limit reached post-submission: {limit_reason}"}

            # Verify submission
            verify_res = await bot_instance.verify_application_result(page)
            if verify_res == VerificationResult.CONFIRMED_SUCCESS:
                excel_tracker.update_application_status(
                    job_url,
                    ApplicationStatus.SUCCESS,
                    notes="Successfully applied and verified via Manual Review pipeline"
                )
                return {"success": True, "message": "Application confirmed and successfully verified!"}
            elif verify_res == VerificationResult.CONFIRMED_FAILURE:
                excel_tracker.update_application_status(
                    job_url,
                    ApplicationStatus.FAILED,
                    notes="Application submission failed during manual execution",
                    reason_code=ReasonCode.PROFILE_INCOMPLETE
                )
                return {"success": False, "message": "Application submission failed post-verification."}
            else:
                excel_tracker.update_application_status(
                    job_url,
                    ApplicationStatus.MANUAL_REVIEW_NEEDED,
                    notes=f"Submission outcome unconfirmed after attempt {attempt_id}",
                    reason_code=ReasonCode.SUBMISSION_UNKNOWN
                )
                return {"success": False, "message": "Submission outcome unconfirmed. Remains in Manual Review."}
        except Exception as e:
            logger.error(f"Error executing manual apply pipeline: {e}")
            return {"success": False, "message": str(e)}
        finally:
            await bot_instance.close_browser()

    async def _run_orchestrator(self, config: SearchConfig, profile: ResumeProfile):
        """Delegate sequential execution and lifecycle transitions to ApplicationOrchestrator."""
        def progress_callback(stats: Dict[str, Any]):
            with self._state_lock:
                self.applied_count = stats.get("applied", self.applied_count)
                self.success_count = stats.get("success", self.success_count)
                self.failed_count = stats.get("failed", self.failed_count)
                self.skipped_count = stats.get("skipped", self.skipped_count)
                self.current_platform = stats.get("current_platform", self.current_platform)
                self.current_job = stats.get("current_job", self.current_job)

        try:
            await orchestrator.run_pipeline(
                config=config,
                profile=profile,
                pause_event=self._pause_event,
                stop_event=self._stop_event,
                progress_callback=progress_callback
            )
        except asyncio.CancelledError:
            await broadcaster.emit_log("Bot run cancelled.", level=LogLevel.INFO)
        except Exception as e:
            logger.error(f"Unhandled error in bot orchestrator: {e}")
            await broadcaster.emit_log(f"Critical error: {str(e)}", level=LogLevel.ERROR)
        finally:
            with self._state_lock:
                self.state = BotState.IDLE
                self.current_platform = None
                self.current_job = None

bot_manager = BotManager()
