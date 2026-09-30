from typing import Dict, Any, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.services.naukri_booster import naukri_booster_service

router = APIRouter()


class BoostRequest(BaseModel):
    headline_override: Optional[str] = Field(None, max_length=250)
    dry_run: bool = False


@router.post("/boost")
async def trigger_naukri_boost(payload: Optional[BoostRequest] = None) -> Dict[str, Any]:
    """Trigger an on-demand profile touch and freshness boost on Naukri."""
    override = payload.headline_override if payload else None
    dry_run = payload.dry_run if payload else False
    result = await naukri_booster_service.boost_profile(headline_override=override, dry_run=dry_run)
    return {
        "success": result.get("status") == "SUCCESS",
        "result": result
    }


@router.get("/boost-history")
async def get_naukri_boost_history() -> Dict[str, Any]:
    """Retrieve history of Naukri profile boosts and last boost time."""
    history = naukri_booster_service.get_boost_history()
    last_boost = naukri_booster_service.get_last_boost_time()
    should_boost = naukri_booster_service.should_boost_today()
    return {
        "history": history,
        "last_boost_time": last_boost,
        "should_boost_today": should_boost,
        "total_boosts": len(history)
    }
