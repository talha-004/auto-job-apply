"""
Post-Application Lifecycle & Interview Pipeline Service.
Tracks applications through interview rounds, offers, rejections, and post-apply engagement.
"""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class PostApplyStatus(str, Enum):
    APPLIED = "Applied"
    VIEWED = "Viewed"
    SCREENING = "Screening"
    INTERVIEW_SCHEDULED = "Interview Scheduled"
    OFFER_RECEIVED = "Offer Received"
    REJECTED = "Rejected"
    GHOSTED = "Ghosted"


class InterviewRound(BaseModel):
    round_number: int = 1
    round_type: str = "Technical"  # Technical, Recruiter Screen, System Design, Behavioral, Final
    scheduled_at: Optional[datetime] = None
    interviewer_name: Optional[str] = None
    notes: Optional[str] = None
    meeting_link: Optional[str] = None
    completed: bool = False


class ApplicationLifecycleRecord(BaseModel):
    application_id: str
    current_status: PostApplyStatus = PostApplyStatus.APPLIED
    interviews: List[InterviewRound] = Field(default_factory=list)
    offer_salary: Optional[str] = None
    rejection_reason: Optional[str] = None
    last_updated: datetime = Field(default_factory=datetime.utcnow)


class InterviewPipelineService:
    def __init__(self):
        self._records: Dict[str, ApplicationLifecycleRecord] = {}

    def get_or_create(self, application_id: str) -> ApplicationLifecycleRecord:
        if application_id not in self._records:
            self._records[application_id] = ApplicationLifecycleRecord(application_id=application_id)
        return self._records[application_id]

    def update_status(self, application_id: str, new_status: PostApplyStatus, notes: Optional[str] = None) -> ApplicationLifecycleRecord:
        rec = self.get_or_create(application_id)
        rec.current_status = new_status
        rec.last_updated = datetime.utcnow()
        if notes and new_status == PostApplyStatus.REJECTED:
            rec.rejection_reason = notes
        return rec

    def schedule_interview(
        self,
        application_id: str,
        round_type: str = "Technical",
        scheduled_at: Optional[datetime] = None,
        interviewer_name: Optional[str] = None,
        meeting_link: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> InterviewRound:
        rec = self.get_or_create(application_id)
        round_num = len(rec.interviews) + 1
        interview = InterviewRound(
            round_number=round_num,
            round_type=round_type,
            scheduled_at=scheduled_at,
            interviewer_name=interviewer_name,
            meeting_link=meeting_link,
            notes=notes,
            completed=False
        )
        rec.interviews.append(interview)
        rec.current_status = PostApplyStatus.INTERVIEW_SCHEDULED
        rec.last_updated = datetime.utcnow()
        return interview

    def record_offer(self, application_id: str, salary_amount: str) -> ApplicationLifecycleRecord:
        rec = self.get_or_create(application_id)
        rec.current_status = PostApplyStatus.OFFER_RECEIVED
        rec.offer_salary = salary_amount
        rec.last_updated = datetime.utcnow()
        return rec

    def get_pipeline_metrics(self) -> Dict[str, int]:
        metrics = {status.value: 0 for status in PostApplyStatus}
        for rec in self._records.values():
            metrics[rec.current_status.value] += 1
        return metrics


interview_service = InterviewPipelineService()
