from fastapi import APIRouter
from app.api.endpoints import resume, bot, jobs, settings, screening, outreach, notifications, security, mobile_companion, analytics, review, interview

api_router = APIRouter()
api_router.include_router(resume.router, prefix="/resume", tags=["Resume"])
api_router.include_router(bot.router, prefix="/bot", tags=["Bot Control"])
api_router.include_router(jobs.router, prefix="/jobs", tags=["Job Applications"])
api_router.include_router(settings.router, prefix="/settings", tags=["System Settings"])
api_router.include_router(screening.router, prefix="/screening", tags=["AI Screening"])
api_router.include_router(outreach.router, prefix="/outreach", tags=["Recruiter Outreach"])
api_router.include_router(notifications.router, prefix="/notifications", tags=["Notifications & Alerts"])
api_router.include_router(security.router, prefix="/security", tags=["Security & Reliability"])
api_router.include_router(mobile_companion.router, prefix="/mobile", tags=["Mobile Companion"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics & Funnel"])
api_router.include_router(review.router, prefix="/review", tags=["Review Queue & Policy"])
api_router.include_router(interview.router, prefix="/interview", tags=["Interview Pipeline"])



