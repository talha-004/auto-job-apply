"""
Platform Rate Limiter & Velocity Guardrail Service.
Enforces per-platform daily application quotas and human-like jitter delays
to protect candidate accounts against anti-bot heuristics and velocity flags.
"""

import random
from datetime import date, datetime
from typing import Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field

from app.core.logger import logger


DEFAULT_DAILY_LIMITS = {
    "linkedin": 25,
    "naukri": 35,
    "indeed": 30,
    "glassdoor": 20,
    "wellfound": 20,
    "default": 20
}

DEFAULT_MIN_INTERVAL_SECONDS = {
    "linkedin": 60,
    "naukri": 45,
    "indeed": 45,
    "default": 45
}


class PlatformLimitStatus(BaseModel):
    platform: str
    allowed: bool
    current_count: int
    daily_limit: int
    remaining: int
    reason: Optional[str] = None


class PlatformLimiter:
    """
    Tracks and enforces daily application limits and intervals across job boards.
    """

    def __init__(
        self,
        custom_limits: Optional[Dict[str, int]] = None,
        custom_intervals: Optional[Dict[str, int]] = None
    ):
        self.limits: Dict[str, int] = {**DEFAULT_DAILY_LIMITS, **(custom_limits or {})}
        self.min_intervals: Dict[str, int] = {**DEFAULT_MIN_INTERVAL_SECONDS, **(custom_intervals or {})}
        self.counts: Dict[str, int] = {}
        self.last_apply_time: Dict[str, datetime] = {}
        self.active_date: date = date.today()

    def _rollover_if_needed(self) -> None:
        today = date.today()
        if today != self.active_date:
            logger.info(f"PlatformLimiter rollover from {self.active_date} to {today}. Resetting daily counters.")
            self.counts.clear()
            self.last_apply_time.clear()
            self.active_date = today

    def get_limit(self, platform: str) -> int:
        norm = platform.strip().lower()
        return self.limits.get(norm, self.limits["default"])

    def get_min_interval(self, platform: str) -> int:
        norm = platform.strip().lower()
        return self.min_intervals.get(norm, self.min_intervals["default"])

    def check_limit(self, platform: str) -> PlatformLimitStatus:
        self._rollover_if_needed()
        norm = platform.strip().lower()
        limit = self.get_limit(norm)
        current = self.counts.get(norm, 0)
        remaining = max(0, limit - current)

        if current >= limit:
            return PlatformLimitStatus(
                platform=norm,
                allowed=False,
                current_count=current,
                daily_limit=limit,
                remaining=0,
                reason=f"Daily quota of {limit} applications reached for platform '{norm}'."
            )

        return PlatformLimitStatus(
            platform=norm,
            allowed=True,
            current_count=current,
            daily_limit=limit,
            remaining=remaining
        )

    def record_application(self, platform: str) -> None:
        self._rollover_if_needed()
        norm = platform.strip().lower()
        self.counts[norm] = self.counts.get(norm, 0) + 1
        self.last_apply_time[norm] = datetime.now()
        logger.info(
            f"Recorded application on '{norm}'. Count today: {self.counts[norm]}/{self.get_limit(norm)}"
        )

    def calculate_jitter_delay(self, platform: str) -> float:
        """
        Calculates a randomized human-like delay (in seconds) between actions.
        Adds uniform jitter (10-30s) on top of minimum platform interval.
        """
        base_interval = float(self.get_min_interval(platform))
        jitter = random.uniform(10.0, 30.0)
        return round(base_interval + jitter, 2)

    def get_status_overview(self) -> Dict[str, Any]:
        self._rollover_if_needed()
        overview = {}
        for plat, limit in self.limits.items():
            if plat == "default":
                continue
            cnt = self.counts.get(plat, 0)
            overview[plat] = {
                "used": cnt,
                "limit": limit,
                "remaining": max(0, limit - cnt),
                "capped": cnt >= limit
            }
        return {
            "date": str(self.active_date),
            "platforms": overview,
            "total_submitted_today": sum(self.counts.values())
        }

    def reset(self) -> None:
        self.counts.clear()
        self.last_apply_time.clear()
        self.active_date = date.today()


platform_limiter = PlatformLimiter()
