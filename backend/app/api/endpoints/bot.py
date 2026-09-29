from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.models.job import SearchConfig, BotStatusResponse, LogMessage, DiscoveryConfig, DiscoveredJob
from app.services.bot_manager import bot_manager
from app.core.logger import broadcaster

router = APIRouter()

class HeadlineUpdateRequest(BaseModel):
    headline: str = Field(..., min_length=5, max_length=250)

@router.get("/status", response_model=BotStatusResponse)
async def get_bot_status() -> BotStatusResponse:
    """Get current state, progress counters, and active platform."""
    return bot_manager.get_status()

@router.post("/start")
async def start_bot(config: SearchConfig) -> Dict[str, Any]:
    """Start automated job application runner with given configuration."""
    res = await bot_manager.start(config)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@router.post("/pause")
async def pause_bot() -> Dict[str, Any]:
    """Pause bot execution."""
    res = await bot_manager.pause()
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@router.post("/resume")
async def resume_bot() -> Dict[str, Any]:
    """Resume bot execution."""
    res = await bot_manager.resume()
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@router.post("/stop")
async def stop_bot() -> Dict[str, Any]:
    """Stop bot execution."""
    res = await bot_manager.stop()
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@router.post("/naukri/update-headline")
async def update_naukri_headline(payload: HeadlineUpdateRequest) -> Dict[str, Any]:
    """Update Naukri profile resume headline reusing authenticated cookie storage."""
    headline = payload.headline.strip()
    if not headline or len(headline) < 5 or len(headline) > 250:
        raise HTTPException(status_code=422, detail="Headline must contain between 5 and 250 non-whitespace characters.")
    
    res = await bot_manager.update_naukri_headline(headline)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("message"))
    return res

@router.get("/logs", response_model=List[LogMessage])
async def get_logs(limit: int = 100) -> List[LogMessage]:
    """Retrieve recent log feed items."""
    return broadcaster.get_recent_logs(limit=limit)

@router.get("/preflight")
async def get_preflight_check() -> Dict[str, Any]:
    """Run preflight validation on system prerequisites."""
    return await bot_manager.run_preflight_check()

@router.post("/preflight")
async def run_preflight_with_config(config: SearchConfig) -> Dict[str, Any]:
    """Run preflight validation against specific run configuration."""
    return await bot_manager.run_preflight_check(config)

@router.post("/discover")
async def discover_jobs_endpoint(config: Optional[DiscoveryConfig] = None) -> Dict[str, Any]:
    """Rapidly discover jobs across multiple platforms via fast HTTP endpoints."""
    from app.services.discovery.discovery_manager import discovery_manager
    from app.services.discovery.search_optimizer import search_optimizer
    cfg = config or DiscoveryConfig()
    jobs = await discovery_manager.discover_jobs(cfg)
    latest_telemetry = search_optimizer.get_recent_telemetry(limit=1)
    return {
        "success": True,
        "count": len(jobs),
        "telemetry": latest_telemetry[0].model_dump() if latest_telemetry else None,
        "jobs": [j.model_dump() for j in jobs]
    }


@router.get("/search/expand")
async def preview_search_expansion(
    keywords: str = "Python Developer",
    location: str = "Remote",
    is_remote: bool = True
):
    """Previews high-yield query expansions, boolean expressions, and platform URLs."""
    from app.services.discovery.search_optimizer import search_optimizer
    expansions = search_optimizer.expand_queries(keywords)
    boolean_query = search_optimizer.build_boolean_search(keywords)
    urls = {
        "linkedin": search_optimizer.build_platform_search_url("linkedin", keywords, location, is_remote),
        "indeed": search_optimizer.build_platform_search_url("indeed", keywords, location, is_remote),
        "naukri": search_optimizer.build_platform_search_url("naukri", keywords, location, is_remote)
    }
    return {
        "base_query": keywords,
        "expanded_queries": expansions,
        "boolean_expression": boolean_query,
        "platform_urls": urls
    }


@router.get("/search/telemetry")
async def get_search_telemetry(limit: int = 10):
    """Retrieves recent search yield and relevancy filtering telemetry."""
    from app.services.discovery.search_optimizer import search_optimizer
    return search_optimizer.get_recent_telemetry(limit=limit)



# --- Autonomous Scheduler Endpoints ---

from app.services.scheduler import (
    scheduler_service,
    SchedulerStatusResponse,
    SchedulerConfigRequest
)


class ToggleJobRequest(BaseModel):
    enabled: bool


@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status():
    """Retrieve active background jobs, next execution times, and daily quotas."""
    return scheduler_service.get_status()


@router.post("/scheduler/start")
async def start_scheduler():
    """Start autonomous background scheduler."""
    scheduler_service.start()
    return {"success": True, "message": "Background autonomous scheduler started."}


@router.post("/scheduler/stop")
async def stop_scheduler():
    """Stop autonomous background scheduler."""
    scheduler_service.shutdown()
    return {"success": True, "message": "Background autonomous scheduler stopped."}


@router.post("/scheduler/config", response_model=SchedulerStatusResponse)
async def update_scheduler_config(config: SchedulerConfigRequest):
    """Update morning cron schedule, headline refresh interval, and daily cap."""
    scheduler_service.update_config(config)
    return scheduler_service.get_status()


@router.post("/scheduler/trigger/{job_id}")
async def trigger_scheduler_job(job_id: str):
    """Manually trigger an immediate run of a scheduled job."""
    triggered = await scheduler_service.trigger_job_now(job_id)
    if not triggered:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return {"success": True, "message": f"Job '{job_id}' triggered successfully."}


@router.post("/scheduler/toggle/{job_id}")
async def toggle_scheduler_job(job_id: str, payload: ToggleJobRequest):
    """Pause or resume a specific scheduled job."""
    toggled = scheduler_service.toggle_job(job_id, payload.enabled)
    if not toggled:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    action = "resumed" if payload.enabled else "paused"
    return {"success": True, "message": f"Job '{job_id}' {action}."}


