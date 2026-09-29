import pytest
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from app.services.scheduler import BusinessHourGuard, AutonomousSchedulerService, SchedulerConfigRequest


def test_business_hour_guard_logic():
    guard = BusinessHourGuard(start_hour=9, end_hour=17, enforce_weekdays=True)

    # 1. Tuesday at 11:30 AM (Weekday inside hours) -> True
    tuesday_workday = datetime(2026, 9, 29, 11, 30)  # Tuesday
    assert guard.is_business_hour(tuesday_workday) is True

    # 2. Wednesday at 8:45 AM (Weekday before start) -> False
    early_morning = datetime(2026, 9, 30, 8, 45)  # Wednesday
    assert guard.is_business_hour(early_morning) is False

    # 3. Thursday at 17:15 PM (Weekday after end) -> False
    evening = datetime(2026, 10, 1, 17, 15)  # Thursday
    assert guard.is_business_hour(evening) is False

    # 4. Saturday at 14:00 PM (Weekend inside daytime) -> False
    saturday_daytime = datetime(2026, 10, 3, 14, 0)  # Saturday
    assert guard.is_business_hour(saturday_daytime) is False

    # 5. Overridden weekend check
    no_weekend_guard = BusinessHourGuard(start_hour=9, end_hour=17, enforce_weekdays=False)
    assert no_weekend_guard.is_business_hour(saturday_daytime) is True


@pytest.mark.asyncio
async def test_scheduler_business_hours_skip_and_execution():
    scheduler = AutonomousSchedulerService()
    scheduler.enforce_business_hours = True

    # Mock time to be outside business hours (e.g. 3 AM)
    off_hours_time = datetime(2026, 9, 30, 3, 0)

    with patch("app.services.scheduler.datetime") as mock_dt, \
         patch("app.services.bot_manager.bot_manager.start", new_callable=AsyncMock) as mock_bot_start:
        mock_dt.now.return_value = off_hours_time
        mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

        await scheduler._execute_morning_job_hunt()

        # Bot start should NOT have been invoked
        assert not mock_bot_start.called
        history = scheduler._job_history.get("morning_job_hunt", {})
        assert history.get("last_run_status") == "SKIPPED_OUTSIDE_BUSINESS_HOURS"


def test_scheduler_config_update_and_status():
    scheduler = AutonomousSchedulerService()

    # Verify status report fields
    status = scheduler.get_status()
    assert hasattr(status.daily_stats, "business_hours_active")
    assert hasattr(status.daily_stats, "enforce_business_hours")

    # Update config dynamically
    req = SchedulerConfigRequest(
        enforce_business_hours=False,
        business_start_hour=8,
        business_end_hour=18
    )
    scheduler.update_config(req)

    assert scheduler.enforce_business_hours is False
    assert scheduler.business_hour_guard.start_hour == 8
    assert scheduler.business_hour_guard.end_hour == 18
