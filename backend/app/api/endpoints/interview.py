"""
Interview Pipeline REST Endpoints.
Allows candidates to track interview rounds, status changes, and offers across applied jobs.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.services.interview_service import (
    interview_service,
    PostApplyStatus,
    ApplicationLifecycleRecord,
    InterviewRound,
)

router = APIRouter()


class StatusUpdateRequest(BaseModel):
    status: PostApplyStatus
    notes: Optional[str] = None


class ScheduleInterviewRequest(BaseModel):
    round_type: str = "Technical"
    scheduled_at: Optional[datetime] = None
    interviewer_name: Optional[str] = None
    meeting_link: Optional[str] = None
    notes: Optional[str] = None


class OfferRequest(BaseModel):
    salary_amount: str


@router.get("/metrics")
async def get_pipeline_metrics():
    """Get aggregate funnel counts across all post-application statuses."""
    return interview_service.get_pipeline_metrics()


@router.get("/{application_id}", response_model=ApplicationLifecycleRecord)
async def get_lifecycle_record(application_id: str):
    """Get interview and post-apply status for a specific application."""
    return interview_service.get_or_create(application_id)


@router.post("/{application_id}/status", response_model=ApplicationLifecycleRecord)
async def update_application_status(application_id: str, req: StatusUpdateRequest):
    """Update post-apply status (e.g. Viewed, Screening, Interview Scheduled, Rejected)."""
    return interview_service.update_status(application_id, req.status, notes=req.notes)


@router.post("/{application_id}/schedule", response_model=InterviewRound)
async def schedule_interview_round(application_id: str, req: ScheduleInterviewRequest):
    """Schedule a technical, recruiter, or final interview round."""
    return interview_service.schedule_interview(
        application_id=application_id,
        round_type=req.round_type,
        scheduled_at=req.scheduled_at,
        interviewer_name=req.interviewer_name,
        meeting_link=req.meeting_link,
        notes=req.notes,
    )


@router.post("/{application_id}/offer", response_model=ApplicationLifecycleRecord)
async def record_job_offer(application_id: str, req: OfferRequest):
    """Record an official job offer for the candidate."""
    return interview_service.record_offer(application_id, req.salary_amount)
