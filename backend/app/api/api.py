from fastapi import APIRouter
from app.api.endpoints import resume, bot, jobs, settings

api_router = APIRouter()
api_router.include_router(resume.router, prefix="/resume", tags=["Resume"])
api_router.include_router(bot.router, prefix="/bot", tags=["Bot Control"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Job Applications"])
api_router.include_router(settings.router, prefix="/settings", tags=["System Settings"])
