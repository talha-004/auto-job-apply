"""
Background Autonomous Scheduler Service.

Coordinates recurring automated job applications, profile freshness heartbeats,
and session validation using APScheduler under strict concurrency mutex locking
and daily application cap guardrails.
"""

import asyncio
from datetime import datetime, date
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from app.core.config import settings
from app.core.logger import logger, broadcaster
from app.models.job import (
    SearchConfig,
    PlatformEnum,
    LogLevel,
    BotState
)
from app.services.bot_manager import bot_manager
from app.services.resume_parser import resume_parser_service
from app.services.excel_tracker import excel_tracker


class ScheduledJobInfo(BaseModel):
    id: str
    name: str
    enabled: bool
    trigger_type: str
    schedule_expression: str
    next_run_time: Optional[str] = None
    last_run_time: Optional[str] = None
    last_run_status: Optional[str] = None


class BusinessHourGuard:
    """
    Enforces natural 9-to-5 business hour execution (Monday-Friday, 09:00 - 17:00).
    Protects user accounts from unnatural off-hours or weekend bot activity.
    """
    def __init__(self, start_hour: int = 9, end_hour: int = 17, enforce_weekdays: bool = True):
        self.start_hour = start_hour
        self.end_hour = end_hour
        self.enforce_weekdays = enforce_weekdays

    def is_business_hour(self, target_time: Optional[datetime] = None) -> bool:
        """Determines if the given time falls within active 9-to-5 business hours."""
        now = target_time or datetime.now()
        # Monday is 0 and Sunday is 6
        if self.enforce_weekdays and now.weekday() >= 5:
            return False
        return self.start_hour <= now.hour < self.end_hour


class SchedulerDailyStats(BaseModel):
    current_date: str
    applications_applied_today: int
    daily_cap: int
    cap_reached: bool
    business_hours_active: bool = True
    enforce_business_hours: bool = True


class SchedulerStatusResponse(BaseModel):
    is_running: bool
    jobs: List[ScheduledJobInfo]
    daily_stats: SchedulerDailyStats


class SchedulerConfigRequest(BaseModel):
    morning_hunt_enabled: Optional[bool] = None
    morning_hunt_hour: Optional[int] = Field(default=None, ge=0, le=23)
    morning_hunt_minute: Optional[int] = Field(default=None, ge=0, le=59)
    headline_refresh_enabled: Optional[bool] = None
    headline_refresh_interval_hours: Optional[int] = Field(default=None, ge=1, le=48)
    daily_application_cap: Optional[int] = Field(default=None, ge=1, le=200)
    enforce_business_hours: Optional[bool] = None
    business_start_hour: Optional[int] = Field(default=None, ge=0, le=23)
    business_end_hour: Optional[int] = Field(default=None, ge=0, le=23)


class AutonomousSchedulerService:
    """Enterprise-grade background task orchestrator for recurring autonomous job applications."""

    def __init__(self):
        self.scheduler: Optional[AsyncIOScheduler] = None
        self._mutex_lock = asyncio.Lock()
        self.daily_cap = settings.SCHEDULER_DAILY_CAP
        self._last_stats_date: str = date.today().isoformat()
        self._applied_today_count: int = 0
        self._job_history: Dict[str, Dict[str, Any]] = {}

        # Default configuration
        self.morning_hour = settings.SCHEDULER_MORNING_HOUR
        self.morning_minute = settings.SCHEDULER_MORNING_MINUTE
        self.refresh_hours = settings.SCHEDULER_HEADLINE_REFRESH_HOURS
        self.enforce_business_hours = settings.SCHEDULER_ENFORCE_BUSINESS_HOURS
        self.business_hour_guard = BusinessHourGuard(
            start_hour=settings.SCHEDULER_BUSINESS_START_HOUR,
            end_hour=settings.SCHEDULER_BUSINESS_END_HOUR,
            enforce_weekdays=True
        )

    def _get_scheduler(self) -> AsyncIOScheduler:
        """Lazy initializer for AsyncIOScheduler bound to active event loop."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if self.scheduler is None or (self.scheduler._eventloop and self.scheduler._eventloop.is_closed()):
            self.scheduler = AsyncIOScheduler(event_loop=current_loop)
        elif current_loop and self.scheduler._eventloop and self.scheduler._eventloop != current_loop:
            try:
                if self.scheduler.running:
                    self.scheduler.shutdown(wait=False)
            except Exception:
                pass
            self.scheduler = AsyncIOScheduler(event_loop=current_loop)

        return self.scheduler


    def _sync_daily_counter(self):
        """Reset or compute daily application counter."""
        today_str = date.today().isoformat()
        if today_str != self._last_stats_date:
            self._last_stats_date = today_str
            self._applied_today_count = 0

        # Query tracker for verified applications submitted today
        try:
            today_records = [
                rec for rec in excel_tracker.records.values()
                if getattr(rec, "applied_date", "") == today_str
                and getattr(rec, "status", None) in ["Applied", "Success"]
            ]
            self._applied_today_count = max(self._applied_today_count, len(today_records))
        except Exception:
            pass

    def record_application_submitted(self):
        """Increment count of applications submitted today."""
        self._sync_daily_counter()
        self._applied_today_count += 1

    def is_daily_cap_reached(self) -> bool:
        """Check if daily quota is exhausted."""
        self._sync_daily_counter()
        return self._applied_today_count >= self.daily_cap

    def start(self):
        """Initialize and start background jobs if not running."""
        sched = self._get_scheduler()
        if sched.running:
            return

        # 1. Morning Job Hunt (Daily Cron)
        morning_trigger = CronTrigger(hour=self.morning_hour, minute=self.morning_minute)
        sched.add_job(
            self._execute_morning_job_hunt,
            trigger=morning_trigger,
            id="morning_job_hunt",
            name="Daily Morning Job Hunt",
            replace_existing=True
        )

        # 2. Headline / Profile Freshness Heartbeat (Interval)
        refresh_trigger = IntervalTrigger(hours=self.refresh_hours)
        sched.add_job(
            self._execute_headline_refresh,
            trigger=refresh_trigger,
            id="naukri_headline_refresh",
            name="Naukri Headline Freshness Heartbeat",
            replace_existing=True
        )

        # 3. Session Health Check (Interval every 1 hour)
        health_trigger = IntervalTrigger(hours=1)
        sched.add_job(
            self._execute_session_health_check,
            trigger=health_trigger,
            id="session_health_check",
            name="Platform Session Health Check",
            replace_existing=True
        )

        sched.start()
        logger.info(
            f"AutonomousScheduler started (Morning Hunt: {self.morning_hour:02d}:{self.morning_minute:02d}, "
            f"Headline Refresh: every {self.refresh_hours}h, Daily Cap: {self.daily_cap})"
        )

    def shutdown(self):
        """Shut down background scheduler."""
        if self.scheduler:
            try:
                loop = getattr(self.scheduler, "_eventloop", None)
                if self.scheduler.running and not (loop and loop.is_closed()):
                    self.scheduler.shutdown(wait=False)
            except Exception:
                pass
            finally:
                self.scheduler = None
            logger.info("AutonomousScheduler shut down.")

    async def _execute_morning_job_hunt(self):
        """Trigger autonomous morning job hunt under mutex locking."""
        job_id = "morning_job_hunt"
        now_str = datetime.now().isoformat()
        self._sync_daily_counter()

        # Enforce daily quota
        if self.is_daily_cap_reached():
            msg = f"Daily application cap reached ({self._applied_today_count}/{self.daily_cap}). Skipping scheduled run."
            logger.warning(f"[Scheduler] {msg}")
            await broadcaster.emit_log(f"⏸️ [Scheduler] {msg}", level=LogLevel.WARNING)
            self._record_run_result(job_id, now_str, "SKIPPED_CAP_REACHED")
            return

        # Mutex locking check
        if self._mutex_lock.locked() or bot_manager.state == BotState.RUNNING:
            msg = "Previous job run is still active. Skipping scheduled trigger to avoid overlap."
            logger.warning(f"[Scheduler] {msg}")
            await broadcaster.emit_log(f"⚠️ [Scheduler] {msg}", level=LogLevel.WARNING)
            self._record_run_result(job_id, now_str, "SKIPPED_CONCURRENCY_LOCK")
            return

        # Enforce 9-to-5 business hours safety guard
        if self.enforce_business_hours and not self.business_hour_guard.is_business_hour():
            msg = (
                f"Outside of 9-to-5 business hours ({datetime.now().strftime('%A %H:%M')}). "
                f"Application cycle safely paused until business hours ({self.business_hour_guard.start_hour:02d}:00 - {self.business_hour_guard.end_hour:02d}:00)."
            )
            logger.info(f"[Scheduler] {msg}")
            await broadcaster.emit_log(f"⏸️ [Scheduler] {msg}", level=LogLevel.INFO)
            self._record_run_result(job_id, now_str, "SKIPPED_OUTSIDE_BUSINESS_HOURS")
            return

        async with self._mutex_lock:
            try:
                await broadcaster.emit_log(
                    f"⏰ [Scheduler] Triggering autonomous Morning Job Hunt (Applied today: {self._applied_today_count}/{self.daily_cap})",
                    level=LogLevel.INFO
                )
                
                profile = resume_parser_service.load_profile()
                if not profile:
                    logger.error("[Scheduler] Candidate profile missing. Cannot run morning job hunt.")
                    self._record_run_result(job_id, now_str, "FAILED_MISSING_PROFILE")
                    return

                remaining_cap = max(1, self.daily_cap - self._applied_today_count)
                config = SearchConfig(
                    keywords="Software Engineer",
                    location="Remote",
                    platforms=[PlatformEnum.NAUKRI, PlatformEnum.LINKEDIN, PlatformEnum.INDEED],
                    max_applications=min(remaining_cap, settings.DEFAULT_MAX_APPLICATIONS),
                    headless=settings.HEADLESS,
                    dry_run=settings.DRY_RUN
                )

                # Delegate to BotManager background thread
                res = await bot_manager.start(config)
                if res.get("success"):
                    self._record_run_result(job_id, now_str, "SUCCESS")
                else:
                    self._record_run_result(job_id, now_str, f"FAILED: {res.get('message')}")
            except Exception as e:
                logger.error(f"[Scheduler] Error executing morning job hunt: {e}")
                self._record_run_result(job_id, now_str, f"ERROR: {str(e)}")

    async def _execute_headline_refresh(self):
        """Simulate profile heartbeat to keep candidate at the top of recruiter active lists."""
        job_id = "naukri_headline_refresh"
        now_str = datetime.now().isoformat()
        try:
            from app.services.naukri_booster import naukri_booster_service
            logger.info("[Scheduler] Executing daily Naukri profile booster...")
            boost_res = await naukri_booster_service.boost_profile(dry_run=False)
            status_str = boost_res.get("status", "SUCCESS")
            self._record_run_result(job_id, now_str, status_str)
        except Exception as e:
            logger.error(f"[Scheduler] Headline refresh failed: {e}")
            self._record_run_result(job_id, now_str, f"ERROR: {str(e)}")

    async def _execute_session_health_check(self):
        """Periodic check for saved cookie health."""
        job_id = "session_health_check"
        now_str = datetime.now().isoformat()
        try:
            for platform in [PlatformEnum.NAUKRI, PlatformEnum.LINKEDIN, PlatformEnum.INDEED]:
                cookie_file = settings.COOKIES_DIR / f"{platform.value.lower()}_cookies.json"
                if not cookie_file.exists():
                    logger.debug(f"[Scheduler] No cookies found for {platform.value}")
            self._record_run_result(job_id, now_str, "SUCCESS")
        except Exception as e:
            self._record_run_result(job_id, now_str, f"ERROR: {str(e)}")

    def _record_run_result(self, job_id: str, run_time: str, status: str):
        """Track execution history."""
        self._job_history[job_id] = {
            "last_run_time": run_time,
            "last_run_status": status
        }

    async def trigger_job_now(self, job_id: str) -> bool:
        """Manually trigger an immediate run of a scheduled job."""
        if job_id == "morning_job_hunt":
            asyncio.create_task(self._execute_morning_job_hunt())
            return True
        elif job_id == "naukri_headline_refresh":
            asyncio.create_task(self._execute_headline_refresh())
            return True
        elif job_id == "session_health_check":
            asyncio.create_task(self._execute_session_health_check())
            return True
        return False

    def toggle_job(self, job_id: str, enabled: bool) -> bool:
        """Pause or resume a job in the scheduler."""
        sched = self._get_scheduler()
        job = sched.get_job(job_id)
        if not job:
            return False
        if enabled:
            job.resume()
        else:
            job.pause()
        return True

    def update_config(self, req: SchedulerConfigRequest):
        """Update scheduler settings and modify active cron triggers."""
        sched = self._get_scheduler()

        if req.daily_application_cap is not None:
            self.daily_cap = req.daily_application_cap

        # Update morning job hunt
        if req.morning_hunt_hour is not None or req.morning_hunt_minute is not None:
            if req.morning_hunt_hour is not None:
                self.morning_hour = req.morning_hunt_hour
            if req.morning_hunt_minute is not None:
                self.morning_minute = req.morning_hunt_minute

            job = sched.get_job("morning_job_hunt")
            if job:
                job.reschedule(trigger=CronTrigger(hour=self.morning_hour, minute=self.morning_minute))

        if req.morning_hunt_enabled is not None:
            self.toggle_job("morning_job_hunt", req.morning_hunt_enabled)

        # Update headline refresh
        if req.headline_refresh_interval_hours is not None:
            self.refresh_hours = req.headline_refresh_interval_hours
            job = sched.get_job("naukri_headline_refresh")
            if job:
                job.reschedule(trigger=IntervalTrigger(hours=self.refresh_hours))

        if req.headline_refresh_enabled is not None:
            self.toggle_job("naukri_headline_refresh", req.headline_refresh_enabled)

        # Update business hours enforcement
        if req.enforce_business_hours is not None:
            self.enforce_business_hours = req.enforce_business_hours
        if req.business_start_hour is not None:
            self.business_hour_guard.start_hour = req.business_start_hour
        if req.business_end_hour is not None:
            self.business_hour_guard.end_hour = req.business_end_hour

    def get_status(self) -> SchedulerStatusResponse:
        """Return comprehensive scheduler health and job status."""
        self._sync_daily_counter()
        sched = self._get_scheduler()
        is_running = sched.running if sched else False

        job_models: List[ScheduledJobInfo] = []
        if sched:
            for job in sched.get_jobs():
                history = self._job_history.get(job.id, {})
                next_run = job.next_run_time.isoformat() if job.next_run_time else None
                trigger_str = str(job.trigger)
                job_models.append(ScheduledJobInfo(
                    id=job.id,
                    name=job.name,
                    enabled=job.next_run_time is not None,
                    trigger_type=type(job.trigger).__name__,
                    schedule_expression=trigger_str,
                    next_run_time=next_run,
                    last_run_time=history.get("last_run_time"),
                    last_run_status=history.get("last_run_status")
                ))

        stats = SchedulerDailyStats(
            current_date=self._last_stats_date,
            applications_applied_today=self._applied_today_count,
            daily_cap=self.daily_cap,
            cap_reached=self.is_daily_cap_reached(),
            business_hours_active=self.business_hour_guard.is_business_hour(),
            enforce_business_hours=self.enforce_business_hours
        )

        return SchedulerStatusResponse(
            is_running=is_running,
            jobs=job_models,
            daily_stats=stats
        )


scheduler_service = AutonomousSchedulerService()
