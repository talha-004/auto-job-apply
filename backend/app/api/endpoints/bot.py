from typing import Dict, Any, List
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from app.models.job import SearchConfig, BotStatusResponse, LogMessage
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

