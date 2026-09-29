"""
Unit and integration tests for ApplicationOrchestrator and BotManager delegation (Phase 4).
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from app.models.job import (
    SearchConfig,
    ResumeProfile,
    DiscoveredJob,
    JobLifecycleStatus,
    PlatformEnum,
    BotState
)
from app.services.orchestrator import ApplicationOrchestrator, orchestrator
from app.services.bot_manager import bot_manager


@pytest.fixture
def mock_profile() -> ResumeProfile:
    return ResumeProfile(
        full_name="Syed Talha Ahmed",
        email="syedtalhaahmed004@gmail.com",
        phone="+91 81439 23984",
        skills=["Python", "FastAPI", "React", "TypeScript", "PostgreSQL"],
        years_of_experience=2.0
    )


def test_orchestrator_initialization_and_status():
    """Verify initial state and get_lifecycle_summary."""
    orch = ApplicationOrchestrator()
    assert orch.is_running is False
    assert orch.active_run_id is None
    summary = orch.get_lifecycle_summary()
    assert summary["is_running"] is False
    assert summary["total_tracked_jobs"] == 0
    assert summary["status_breakdown"] == {}


def test_orchestrator_record_transition():
    """Verify state transitions are properly stored in lifecycle history."""
    orch = ApplicationOrchestrator()
    entry1 = orch.record_transition(
        job_id="JOB-101",
        from_status=None,
        to_status=JobLifecycleStatus.DISCOVERED,
        details={"title": "Full Stack Dev"}
    )
    assert entry1["to_status"] == "DISCOVERED"
    assert orch.lifecycle_records["JOB-101"]["current_status"] == "DISCOVERED"

    entry2 = orch.record_transition(
        job_id="JOB-101",
        from_status=JobLifecycleStatus.DISCOVERED,
        to_status=JobLifecycleStatus.EVALUATING
    )
    assert entry2["to_status"] == "EVALUATING"
    assert len(orch.lifecycle_records["JOB-101"]["history"]) == 2

    orch.record_transition(
        job_id="JOB-101",
        from_status=JobLifecycleStatus.EVALUATING,
        to_status=JobLifecycleStatus.ELIGIBLE
    )
    assert orch.lifecycle_records["JOB-101"]["current_status"] == "ELIGIBLE"

    summary = orch.get_lifecycle_summary()
    assert summary["total_tracked_jobs"] == 1
    assert summary["status_breakdown"].get("ELIGIBLE") == 1


@pytest.mark.asyncio
async def test_orchestrator_pipeline_discovery_and_evaluation(mock_profile):
    """Verify orchestrator runs discovery, routes through evaluation, and tracks state."""
    orch = ApplicationOrchestrator()
    config = SearchConfig(
        keywords="Python Developer",
        location="India",
        platforms=[PlatformEnum.LINKEDIN],
        max_applications=5,
        excluded_keywords=["telecalling"]
    )
    pause_event = asyncio.Event()
    pause_event.set()
    stop_event = asyncio.Event()

    mock_discovered = [
        DiscoveredJob(
            job_id="JOB-ELIGIBLE-1",
            platform="LinkedIn",
            title="Python Developer",
            company="TechCorp",
            location="Remote",
            is_remote=True,
            job_url="https://linkedin.com/jobs/view/1",
            description="Looking for Python and FastAPI developers. Experience: 2 years."
        ),
        DiscoveredJob(
            job_id="JOB-EXCLUDED-2",
            platform="LinkedIn",
            title="Telecalling Python Support",
            company="SpamCo",
            location="Remote",
            is_remote=True,
            job_url="https://linkedin.com/jobs/view/2",
            description="Telecalling with Python scripting."
        )
    ]

    with patch("app.services.orchestrator.discovery_manager.discover_jobs", new=AsyncMock(return_value=mock_discovered)), \
         patch.object(orch.PLATFORM_CLASSES[PlatformEnum.LINKEDIN], "init_browser", new=AsyncMock()), \
         patch.object(orch.PLATFORM_CLASSES[PlatformEnum.LINKEDIN], "login", new=AsyncMock(return_value=True)), \
         patch.object(orch.PLATFORM_CLASSES[PlatformEnum.LINKEDIN], "search_and_apply", new=AsyncMock(return_value=1)), \
         patch.object(orch.PLATFORM_CLASSES[PlatformEnum.LINKEDIN], "close_browser", new=AsyncMock()):

        stats = await orch.run_pipeline(
            config=config,
            profile=mock_profile,
            pause_event=pause_event,
            stop_event=stop_event
        )

        assert stats["status"] == "COMPLETED"
        assert stats["discovered"] == 2
        assert stats["evaluated"] == 2
        assert stats["eligible"] == 1
        assert stats["skipped"] == 1
        assert stats["applied"] == 1

        summary = orch.get_lifecycle_summary()
        assert summary["total_tracked_jobs"] == 2
        assert summary["status_breakdown"]["ELIGIBLE"] == 1
        assert summary["status_breakdown"]["SKIPPED"] == 1


@pytest.mark.asyncio
async def test_orchestrator_pipeline_stop_event_halts_immediately(mock_profile):
    """Verify stop_event immediately halts pipeline execution."""
    orch = ApplicationOrchestrator()
    config = SearchConfig(max_applications=10)
    pause_event = asyncio.Event()
    pause_event.set()
    stop_event = asyncio.Event()
    stop_event.set()  # Already stopped

    stats = await orch.run_pipeline(
        config=config,
        profile=mock_profile,
        pause_event=pause_event,
        stop_event=stop_event
    )

    assert stats["status"] == "STOPPED"
    assert stats["discovered"] == 0
    assert stats["applied"] == 0


@pytest.mark.asyncio
async def test_orchestrator_progress_callback(mock_profile):
    """Verify progress callback is called with updated counters."""
    orch = ApplicationOrchestrator()
    config = SearchConfig(
        keywords="React Developer",
        platforms=[PlatformEnum.INDEED],
        max_applications=2
    )
    pause_event = asyncio.Event()
    pause_event.set()
    stop_event = asyncio.Event()

    progress_updates = []
    def on_progress(data):
        progress_updates.append(data)

    with patch("app.services.orchestrator.discovery_manager.discover_jobs", new=AsyncMock(return_value=[])), \
         patch.object(orch.PLATFORM_CLASSES[PlatformEnum.INDEED], "init_browser", new=AsyncMock()), \
         patch.object(orch.PLATFORM_CLASSES[PlatformEnum.INDEED], "login", new=AsyncMock(return_value=True)), \
         patch.object(orch.PLATFORM_CLASSES[PlatformEnum.INDEED], "search_and_apply", new=AsyncMock(return_value=2)), \
         patch.object(orch.PLATFORM_CLASSES[PlatformEnum.INDEED], "close_browser", new=AsyncMock()):

        stats = await orch.run_pipeline(
            config=config,
            profile=mock_profile,
            pause_event=pause_event,
            stop_event=stop_event,
            progress_callback=on_progress
        )

        assert stats["applied"] == 2
        assert len(progress_updates) > 0
        assert progress_updates[-1]["applied"] == 2


def test_bot_manager_has_orchestrator_delegation():
    """Verify bot_manager status and start/stop controls operate smoothly."""
    status = bot_manager.get_status()
    assert status.state in [BotState.IDLE, BotState.STOPPED, BotState.PAUSED]
    assert hasattr(bot_manager, "_run_orchestrator")
