from typing import Dict, Any
from fastapi import APIRouter
from app.core.config import settings
from app.core.llm import llm_client

router = APIRouter()

@router.get("/status")
async def get_system_status() -> Dict[str, Any]:
    """Check health of Ollama LLM, platform credential status, and environment readiness."""
    llm_health = await llm_client.check_health()
    
    credentials_status = {
        "LinkedIn": bool(settings.LINKEDIN_EMAIL and settings.LINKEDIN_PASSWORD),
        "Naukri": bool(settings.NAUKRI_EMAIL and settings.NAUKRI_PASSWORD),
        "Indeed": bool(settings.INDEED_EMAIL and settings.INDEED_PASSWORD),
        "Dindin": True
    }

    cookies_status = {
        "LinkedIn": (settings.COOKIES_DIR / "linkedin_cookies.json").exists(),
        "Naukri": (settings.COOKIES_DIR / "naukri_cookies.json").exists(),
        "Indeed": (settings.COOKIES_DIR / "indeed_cookies.json").exists(),
        "Dindin": (settings.COOKIES_DIR / "dindin_cookies.json").exists()
    }

    return {
        "llm": llm_health,
        "credentials_configured": credentials_status,
        "active_sessions": cookies_status,
        "defaults": {
            "max_applications": settings.DEFAULT_MAX_APPLICATIONS,
            "min_delay": settings.MIN_DELAY_SECONDS,
            "max_delay": settings.MAX_DELAY_SECONDS,
            "cooldown": settings.COOLDOWN_BETWEEN_JOBS_SECONDS,
            "headless": settings.HEADLESS,
            "dry_run": settings.DRY_RUN
        }
    }
