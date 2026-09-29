"""
Central Application Orchestration Engine.
Coordinates the end-to-end lifecycle:
DISCOVERED -> EVALUATING -> ELIGIBLE -> PREPARING -> APPLYING -> SUBMITTED / FAILED / MANUAL_REVIEW / SKIPPED
"""

import sys
import json
import asyncio
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple, Callable

from app.core.config import settings
from app.core.circuit_breaker import circuit_breaker
from app.core.logger import broadcaster, logger
from app.models.job import (
    SearchConfig,
    ResumeProfile,
    DiscoveredJob,
    JobEvaluationResult,
    JobLifecycleStatus,
    ApplicationStatus,
    PlatformEnum,
    LogLevel,
    JobApplicationRecord
)
from app.services.discovery.discovery_manager import discovery_manager
from app.services.job_evaluator import job_evaluator
from app.services.excel_tracker import excel_tracker
from app.platforms.linkedin import LinkedInPlatform
from app.platforms.naukri import NaukriPlatform
from app.platforms.indeed import IndeedPlatform
from app.platforms.dindin import DindinPlatform


class ApplicationOrchestrator:
    """
    Central stateful workflow coordinator driving candidate job applications.
    Manages state machine transitions, pre-apply evaluation gating,
    and reliable application execution across multi-platform adapters.
    """

    PLATFORM_CLASSES = {
        PlatformEnum.LINKEDIN: LinkedInPlatform,
        PlatformEnum.NAUKRI: NaukriPlatform,
        PlatformEnum.INDEED: IndeedPlatform,
        PlatformEnum.DINDIN: DindinPlatform,
    }

    CHECKPOINT_FILE = settings.CHECKPOINTS_DIR / "orchestrator_checkpoint.json"

    def __init__(self):
        self.active_run_id: Optional[str] = None
        self.is_running: bool = False
        self.lifecycle_records: Dict[str, Dict[str, Any]] = {}
        self.current_platform: Optional[str] = None
        self.current_job: Optional[str] = None

    def save_checkpoint(
        self,
        stats: Dict[str, Any],
        eligible_jobs: List[Tuple[DiscoveredJob, JobEvaluationResult]],
        config: SearchConfig
    ):
        """Save atomic crash recovery checkpoint to disk."""
        try:
            data = {
                "run_id": self.active_run_id,
                "timestamp": datetime.now().isoformat(),
                "stats": stats,
                "config": config.model_dump(),
                "lifecycle_records": self.lifecycle_records,
                "eligible_jobs": [
                    {
                        "discovered_job": ej[0].model_dump(),
                        "eval_result": ej[1].model_dump()
                    }
                    for ej in eligible_jobs
                ]
            }
            temp_file = settings.CHECKPOINTS_DIR / "orchestrator_checkpoint.json.tmp"
            temp_file.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            temp_file.replace(self.CHECKPOINT_FILE)
            logger.debug(f"[Orchestrator] Crash checkpoint saved for run {self.active_run_id}.")
        except Exception as e:
            logger.warning(f"[Orchestrator] Failed to save crash checkpoint: {e}")

    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        """Load pending crash recovery checkpoint if present."""
        if not self.CHECKPOINT_FILE.exists():
            return None
        try:
            content = self.CHECKPOINT_FILE.read_text(encoding="utf-8")
            return json.loads(content)
        except Exception as e:
            logger.warning(f"[Orchestrator] Failed to parse checkpoint: {e}")
            return None

    def clear_checkpoint(self):
        """Delete checkpoint upon successful pipeline completion."""
        if self.CHECKPOINT_FILE.exists():
            try:
                self.CHECKPOINT_FILE.unlink()
                logger.info("[Orchestrator] Active crash recovery checkpoint cleared.")
            except Exception as e:
                logger.warning(f"[Orchestrator] Could not remove checkpoint: {e}")

    def record_transition(
        self,
        job_id: str,
        from_status: Optional[JobLifecycleStatus],
        to_status: JobLifecycleStatus,
        details: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Record an explicit state transition in the lifecycle history."""
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = {
            "timestamp": now_str,
            "from_status": from_status.value if from_status else None,
            "to_status": to_status.value,
            "details": details or {}
        }
        if job_id not in self.lifecycle_records:
            self.lifecycle_records[job_id] = {
                "job_id": job_id,
                "current_status": to_status.value,
                "history": [entry],
                "created_at": now_str
            }
        else:
            self.lifecycle_records[job_id]["current_status"] = to_status.value
            self.lifecycle_records[job_id]["history"].append(entry)

        return entry

    async def run_pipeline(
        self,
        config: SearchConfig,
        profile: ResumeProfile,
        pause_event: asyncio.Event,
        stop_event: asyncio.Event,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> Dict[str, Any]:
        """
        Execute the master application workflow:
        1. Fast HTTP Multi-Board Discovery
        2. Intelligence & Evaluation Gating (Match / Risk / Contact / Disqualification)
        3. Application Dispatch (Browser / ATS Adapters)
        4. Verification, Tracking, & Summary
        """
        self.active_run_id = f"RUN-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        self.is_running = True
        self.lifecycle_records.clear()

        stats = {
            "run_id": self.active_run_id,
            "target": config.max_applications,
            "discovered": 0,
            "evaluated": 0,
            "eligible": 0,
            "skipped": 0,
            "applied": 0,
            "success": 0,
            "failed": 0,
            "manual_review": 0,
            "status": "RUNNING"
        }

        def emit_stats_update():
            if progress_callback:
                progress_callback({
                    "applied": stats["applied"],
                    "success": stats["success"],
                    "failed": stats["failed"],
                    "skipped": stats["skipped"],
                    "current_platform": self.current_platform,
                    "current_job": self.current_job
                })

        try:
            await broadcaster.emit_log(
                f"🚀 [Orchestrator {self.active_run_id}] Commencing application pipeline. Target: {config.max_applications} apps.",
                level=LogLevel.INFO
            )

            # -------------------------------------------------------------
            # STAGE 1: HYBRID JOB DISCOVERY
            # -------------------------------------------------------------
            if stop_event.is_set():
                stats["status"] = "STOPPED"
                return stats

            await broadcaster.emit_log(
                f"🔍 [Stage 1: Discovery] Querying multi-board sources for keywords: '{config.keywords}', location: '{config.location}'...",
                level=LogLevel.INFO
            )

            discovered_jobs: List[DiscoveredJob] = []
            try:
                discovered_jobs = await discovery_manager.discover_jobs(
                    keywords=config.keywords,
                    location=config.location,
                    platforms=[p.value.lower() for p in config.platforms if p != PlatformEnum.DINDIN],
                    results_wanted=min(50, config.max_applications * 2)
                )
            except Exception as disc_err:
                logger.warning(f"Fast discovery encountered non-fatal error: {disc_err}. Will rely on platform crawlers.")

            stats["discovered"] = len(discovered_jobs)
            for dj in discovered_jobs:
                self.record_transition(
                    job_id=dj.job_id,
                    from_status=None,
                    to_status=JobLifecycleStatus.DISCOVERED,
                    details={"title": dj.title, "company": dj.company, "platform": dj.platform}
                )

            await broadcaster.emit_log(
                f"🔎 [Stage 1: Discovery] Completed. {len(discovered_jobs)} deduplicated jobs found across providers.",
                level=LogLevel.INFO
            )

            # -------------------------------------------------------------
            # STAGE 2: INTELLIGENCE & EVALUATION GATING
            # -------------------------------------------------------------
            if stop_event.is_set():
                stats["status"] = "STOPPED"
                return stats

            await broadcaster.emit_log(
                "🧠 [Stage 2: Evaluation] Running deterministic 60/20/10/10 scoring & hard disqualification filters...",
                level=LogLevel.INFO
            )

            eligible_jobs: List[Tuple[DiscoveredJob, JobEvaluationResult]] = []
            for d_job in discovered_jobs:
                if stop_event.is_set():
                    break

                self.record_transition(
                    job_id=d_job.job_id,
                    from_status=JobLifecycleStatus.DISCOVERED,
                    to_status=JobLifecycleStatus.EVALUATING
                )

                eval_res = job_evaluator.evaluate_job(d_job, profile, config)
                stats["evaluated"] += 1

                if eval_res.is_eligible and eval_res.suggested_action in ("APPLY", "MANUAL_REVIEW"):
                    if eval_res.suggested_action == "MANUAL_REVIEW":
                        stats["manual_review"] += 1
                        self.record_transition(
                            job_id=d_job.job_id,
                            from_status=JobLifecycleStatus.EVALUATING,
                            to_status=JobLifecycleStatus.MANUAL_REVIEW,
                            details={"reasons": eval_res.disqualification_reasons, "priority": eval_res.priority_score}
                        )
                    else:
                        stats["eligible"] += 1
                        self.record_transition(
                            job_id=d_job.job_id,
                            from_status=JobLifecycleStatus.EVALUATING,
                            to_status=JobLifecycleStatus.ELIGIBLE,
                            details={"match_score": eval_res.match_score, "priority_score": eval_res.priority_score}
                        )
                        eligible_jobs.append((d_job, eval_res))
                else:
                    stats["skipped"] += 1
                    self.record_transition(
                        job_id=d_job.job_id,
                        from_status=JobLifecycleStatus.EVALUATING,
                        to_status=JobLifecycleStatus.SKIPPED,
                        details={"reasons": eval_res.disqualification_reasons}
                    )

            # Rank eligible jobs by priority and match score
            eligible_jobs.sort(
                key=lambda item: (item[1].priority_score, item[1].match_score),
                reverse=True
            )

            await broadcaster.emit_log(
                f"📊 [Stage 2: Evaluation] {stats['eligible']} eligible, {stats['skipped']} skipped, {stats['manual_review']} manual review.",
                level=LogLevel.INFO
            )
            emit_stats_update()
            # Save checkpoint after evaluation phase
            self.save_checkpoint(stats, eligible_jobs, config)

            # -------------------------------------------------------------
            # STAGE 3: APPLICATION DISPATCH (BROWSER RUNNERS)
            # -------------------------------------------------------------
            for platform_enum in config.platforms:
                if stop_event.is_set():
                    break
                if stats["applied"] >= config.max_applications:
                    await broadcaster.emit_log(
                        f"🎯 Target quota of {config.max_applications} reached. Halting pipeline.",
                        level=LogLevel.SUCCESS
                    )
                    break

                platform_name = platform_enum.value.lower()
                # 🛡️ Circuit Breaker Guard
                if not circuit_breaker.can_execute(platform_name):
                    cb_status = circuit_breaker.get_all_status().get(platform_name, {})
                    cooldown = cb_status.get("cooldown_remaining_sec", 60.0)
                    await broadcaster.emit_log(
                        f"⚡ Circuit breaker for {platform_enum.value} is OPEN. Skipping to protect account/IP. "
                        f"Cooldown remaining: {cooldown}s.",
                        level=LogLevel.WARNING,
                        platform=platform_enum.value
                    )
                    continue

                self.current_platform = platform_enum.value
                bot_cls = self.PLATFORM_CLASSES.get(platform_enum)
                if not bot_cls:
                    continue

                await broadcaster.emit_log(
                    f"🌐 [Stage 3: Dispatch] Launching {platform_enum.value} automation session...",
                    level=LogLevel.INFO,
                    platform=platform_enum.value
                )

                bot_instance = bot_cls(
                    config=config,
                    profile=profile,
                    pause_event=pause_event,
                    stop_event=stop_event
                )

                try:
                    await bot_instance.init_browser()

                    # Check pause state before login
                    if not pause_event.is_set():
                        await pause_event.wait()
                    if stop_event.is_set():
                        break

                    logged_in = await bot_instance.login()

                    if logged_in or platform_enum in [PlatformEnum.DINDIN, PlatformEnum.INDEED]:
                        remaining_quota = config.max_applications - stats["applied"]
                        platform_config = config.model_copy(update={"max_applications": remaining_quota})
                        bot_instance.config = platform_config

                        applied_on_platform = await bot_instance.search_and_apply()
                        stats["applied"] += applied_on_platform
                        stats["success"] += applied_on_platform
                        # Record success to circuit breaker
                        circuit_breaker.record_success(platform_name)
                        emit_stats_update()
                    else:
                        await broadcaster.emit_log(
                            f"Skipping {platform_enum.value} search due to unverified authentication.",
                            level=LogLevel.WARNING,
                            platform=platform_enum.value
                        )

                except asyncio.CancelledError:
                    await broadcaster.emit_log(
                        f"Cancelled automation on {platform_enum.value}.",
                        level=LogLevel.WARNING,
                        platform=platform_enum.value
                    )
                    break
                except Exception as e:
                    tb_str = traceback.format_exc()
                    logger.error(f"Error on {platform_enum.value}: {e}\n{tb_str}")
                    stats["failed"] += 1
                    # Record failure to circuit breaker
                    tripped = circuit_breaker.record_failure(platform_name, e)
                    if tripped:
                        await broadcaster.emit_log(
                            f"🚨 Circuit breaker TRIPPED for {platform_enum.value} after consecutive failures. Cooling down.",
                            level=LogLevel.ERROR,
                            platform=platform_enum.value
                        )
                    emit_stats_update()
                    await broadcaster.emit_log(
                        f"Platform execution error on {platform_enum.value}: {str(e)}",
                        level=LogLevel.ERROR,
                        platform=platform_enum.value
                    )
                finally:
                    await bot_instance.close_browser()
                    # Persist state after each platform execution
                    self.save_checkpoint(stats, eligible_jobs, config)

            stats["status"] = "COMPLETED" if not stop_event.is_set() else "STOPPED"
            if stats["status"] == "COMPLETED":
                self.clear_checkpoint()
            await broadcaster.emit_log(
                f"🏁 [Pipeline Complete] Total Applied: {stats['applied']}/{config.max_applications} "
                f"(Success: {stats['success']}, Failed: {stats['failed']}, Skipped: {stats['skipped']}).",
                level=LogLevel.SUCCESS
            )
            emit_stats_update()
            return stats

        except asyncio.CancelledError:
            stats["status"] = "CANCELLED"
            await broadcaster.emit_log("Pipeline run cancelled by user.", level=LogLevel.INFO)
            return stats
        except Exception as e:
            stats["status"] = "ERROR"
            stats["error"] = str(e)
            logger.error(f"Fatal unhandled pipeline error: {e}")
            await broadcaster.emit_log(f"Fatal pipeline error: {str(e)}", level=LogLevel.ERROR)
            return stats
        finally:
            self.is_running = False
            self.current_platform = None
            self.current_job = None
            emit_stats_update()

    def get_lifecycle_summary(self) -> Dict[str, Any]:
        """Return the current active lifecycle status and job breakdown."""
        counts: Dict[str, int] = {}
        for record in self.lifecycle_records.values():
            st = record.get("current_status", "UNKNOWN")
            counts[st] = counts.get(st, 0) + 1

        return {
            "run_id": self.active_run_id,
            "is_running": self.is_running,
            "total_tracked_jobs": len(self.lifecycle_records),
            "status_breakdown": counts
        }


orchestrator = ApplicationOrchestrator()
