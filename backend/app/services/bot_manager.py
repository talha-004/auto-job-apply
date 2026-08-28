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
    ResumeProfile
)
from app.services.resume_parser import resume_parser_service
from app.platforms.linkedin import LinkedInPlatform
from app.platforms.naukri import NaukriPlatform
from app.platforms.indeed import IndeedPlatform
from app.platforms.dindin import DindinPlatform

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

    def get_status(self) -> BotStatusResponse:
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
        if self.state == BotState.RUNNING:
            return {"success": False, "message": "Bot is already running."}

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
            try:
                loop.close()
            except Exception:
                pass
            self._worker_loop = None

    async def pause(self, reason: Optional[str] = None) -> Dict[str, Any]:
        """Pause running bot."""
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
        if self.state == BotState.IDLE or self.state == BotState.STOPPED:
            return {"success": False, "message": "Bot is already idle or stopped."}

        self.state = BotState.STOPPED
        if self._worker_loop and self._worker_loop.is_running():
            if self._stop_event:
                self._worker_loop.call_soon_threadsafe(self._stop_event.set)
            if self._pause_event:
                self._worker_loop.call_soon_threadsafe(self._pause_event.set)

        await broadcaster.emit_log("🛑 Bot stopped by user.", level=LogLevel.WARNING)
        self.state = BotState.IDLE
        return {"success": True, "message": "Bot stopped."}

    async def _run_orchestrator(self, config: SearchConfig, profile: ResumeProfile):
        """Sequential platform runner managing Playwright lifecycle."""
        platform_classes = {
            PlatformEnum.LINKEDIN: LinkedInPlatform,
            PlatformEnum.NAUKRI: NaukriPlatform,
            PlatformEnum.INDEED: IndeedPlatform,
            PlatformEnum.DINDIN: DindinPlatform,
        }

        try:
            for platform_enum in config.platforms:
                if self._stop_event.is_set() or self.state == BotState.STOPPED:
                    break

                self.current_platform = platform_enum.value
                bot_cls = platform_classes.get(platform_enum)
                if not bot_cls:
                    continue

                await broadcaster.emit_log(f"Starting automation on platform: {platform_enum.value}", level=LogLevel.INFO, platform=platform_enum.value)

                bot_instance = bot_cls(
                    config=config,
                    profile=profile,
                    pause_event=self._pause_event,
                    stop_event=self._stop_event
                )
                self._current_bot_instance = bot_instance

                try:
                    await bot_instance.init_browser()
                    logged_in = await bot_instance.login()

                    if logged_in or platform_enum in [PlatformEnum.DINDIN, PlatformEnum.INDEED]:
                        applied_on_platform = await bot_instance.search_and_apply()
                        self.applied_count += applied_on_platform
                        self.success_count += applied_on_platform
                    else:
                        await broadcaster.emit_log(f"Skipping {platform_enum.value} search due to unverified authentication.", level=LogLevel.WARNING, platform=platform_enum.value)

                except asyncio.CancelledError:
                    await broadcaster.emit_log(f"Cancelled execution on {platform_enum.value}.", level=LogLevel.WARNING, platform=platform_enum.value)
                    break
                except Exception as e:
                    import traceback
                    tb_str = traceback.format_exc()
                    logger.error(f"Error executing platform {platform_enum.value}: {repr(e)}\n{tb_str}")
                    err_detail = str(e) if str(e).strip() else repr(e)
                    await broadcaster.emit_log(f"Platform error on {platform_enum.value}: {err_detail}", level=LogLevel.ERROR, platform=platform_enum.value)
                finally:
                    await bot_instance.close_browser()
                    self._current_bot_instance = None

            await broadcaster.emit_log(
                f"🎉 Application run completed! Total applied: {self.applied_count}/{self.total_target}",
                level=LogLevel.SUCCESS
            )
        except asyncio.CancelledError:
            await broadcaster.emit_log("Bot run cancelled.", level=LogLevel.INFO)
        except Exception as e:
            logger.error(f"Unhandled error in bot orchestrator: {e}")
            await broadcaster.emit_log(f"Critical error: {str(e)}", level=LogLevel.ERROR)
        finally:
            self.state = BotState.IDLE
            self.current_platform = None
            self.current_job = None

bot_manager = BotManager()
