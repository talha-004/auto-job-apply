import pytest
import asyncio
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from app.main import app
from app.models.job import BotState, SearchConfig, ResumeProfile, QAVault
from app.services.scheduler import (
    scheduler_service,
    SchedulerConfigRequest,
    AutonomousSchedulerService
)
from app.core.config import settings


@pytest.fixture(autouse=True)
async def clean_scheduler():
    """Ensure scheduler is freshly initialized and shut down after tests."""
    yield
    scheduler_service.shutdown()
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_scheduler_lifecycle():
    """Verify scheduler starts and stops cleanly."""
    scheduler_service.start()
    assert scheduler_service.scheduler is not None
    assert scheduler_service.scheduler.running is True

    status = scheduler_service.get_status()
    assert status.is_running is True
    job_ids = [j.id for j in status.jobs]
    assert "morning_job_hunt" in job_ids
    assert "naukri_headline_refresh" in job_ids
    assert "session_health_check" in job_ids

    scheduler_service.shutdown()
    await asyncio.sleep(0.01)
    assert scheduler_service.scheduler is None


@pytest.mark.asyncio
async def test_daily_cap_enforcement():
    """Verify scheduler detects and enforces daily application limits."""
    service = AutonomousSchedulerService()
    service.daily_cap = 3

    assert service.is_daily_cap_reached() is False

    service.record_application_submitted()
    service.record_application_submitted()
    assert service.is_daily_cap_reached() is False

    service.record_application_submitted()
    assert service.is_daily_cap_reached() is True

    # Test that job hunt skips when cap is reached
    service.start()
    await service._execute_morning_job_hunt()
    status = service.get_status()
    hunt_job = next(j for j in status.jobs if j.id == "morning_job_hunt")
    assert hunt_job.last_run_status == "SKIPPED_CAP_REACHED"
    service.shutdown()
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_scheduler_mutex_concurrency_locking():
    """Verify job hunt aborts if a previous run is currently active."""
    service = AutonomousSchedulerService()
    service.start()

    # Simulate bot_manager currently running
    with patch("app.services.bot_manager.bot_manager.state", BotState.RUNNING):
        await service._execute_morning_job_hunt()
        status = service.get_status()
        hunt_job = next(j for j in status.jobs if j.id == "morning_job_hunt")
        assert hunt_job.last_run_status == "SKIPPED_CONCURRENCY_LOCK"

    service.shutdown()
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_scheduler_toggle_and_config():
    """Verify dynamic reconfiguration of cron schedules and job toggling."""
    service = AutonomousSchedulerService()
    service.start()

    # Toggle job off (pause)
    toggled = service.toggle_job("morning_job_hunt", enabled=False)
    assert toggled is True
    status = service.get_status()
    hunt_job = next(j for j in status.jobs if j.id == "morning_job_hunt")
    assert hunt_job.enabled is False

    # Toggle job on (resume)
    toggled = service.toggle_job("morning_job_hunt", enabled=True)
    assert toggled is True
    status = service.get_status()
    hunt_job = next(j for j in status.jobs if j.id == "morning_job_hunt")
    assert hunt_job.enabled is True

    # Update config
    service.update_config(SchedulerConfigRequest(
        morning_hunt_hour=10,
        morning_hunt_minute=30,
        headline_refresh_interval_hours=8,
        daily_application_cap=50
    ))
    assert service.morning_hour == 10
    assert service.morning_minute == 30
    assert service.refresh_hours == 8
    assert service.daily_cap == 50

    service.shutdown()
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_scheduler_rest_api_endpoints():
    """Verify FastAPI endpoints for controlling the autonomous scheduler."""
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Start scheduler
        res_start = await ac.post("/api/bot/scheduler/start")
        assert res_start.status_code == 200
        assert res_start.json()["success"] is True

        # 2. Get status
        res_status = await ac.get("/api/bot/scheduler/status")
        assert res_status.status_code == 200
        status_data = res_status.json()
        assert status_data["is_running"] is True
        assert len(status_data["jobs"]) == 3

        # 3. Update config
        res_cfg = await ac.post("/api/bot/scheduler/config", json={
            "morning_hunt_hour": 8,
            "morning_hunt_minute": 15,
            "daily_application_cap": 30
        })
        assert res_cfg.status_code == 200
        cfg_data = res_cfg.json()
        assert cfg_data["daily_stats"]["daily_cap"] == 30

        # 4. Toggle job
        res_toggle = await ac.post("/api/bot/scheduler/toggle/morning_job_hunt", json={"enabled": False})
        assert res_toggle.status_code == 200

        # 5. Trigger job now
        res_trig = await ac.post("/api/bot/scheduler/trigger/session_health_check")
        assert res_trig.status_code == 200

        # 6. Stop scheduler
        res_stop = await ac.post("/api/bot/scheduler/stop")
        assert res_stop.status_code == 200
        assert res_stop.json()["success"] is True

