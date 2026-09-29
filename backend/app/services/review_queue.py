"""
Pre-Submit Review Queue Service.
Holds applications requiring human signoff (Assist/Supervised mode or unverified claims).
Allows users to review application diffs, edit answers, and approve or reject submissions.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.services.policy_engine import PolicyEvaluation


class ReviewItem(BaseModel):
    review_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    job_title: str
    company: str
    platform: str
    job_url: str
    match_score: float
    answers: List[Dict[str, Any]] = Field(default_factory=list)
    evaluation: Optional[PolicyEvaluation] = None
    status: str = "PENDING"  # PENDING, APPROVED, REJECTED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None


class ReviewQueueService:
    def __init__(self):
        self._queue: Dict[str, ReviewItem] = {}

    def enqueue(
        self,
        job_title: str,
        company: str,
        platform: str,
        job_url: str,
        match_score: float,
        answers: List[Dict[str, Any]],
        evaluation: Optional[PolicyEvaluation] = None,
    ) -> ReviewItem:
        item = ReviewItem(
            job_title=job_title,
            company=company,
            platform=platform,
            job_url=job_url,
            match_score=match_score,
            answers=answers,
            evaluation=evaluation,
            status="PENDING",
            created_at=datetime.utcnow(),
        )
        self._queue[item.review_id] = item
        return item

    def list_pending(self) -> List[ReviewItem]:
        return [item for item in self._queue.values() if item.status == "PENDING"]

    def get(self, review_id: str) -> Optional[ReviewItem]:
        return self._queue.get(review_id)

    def approve(self, review_id: str) -> bool:
        item = self.get(review_id)
        if item and item.status == "PENDING":
            item.status = "APPROVED"
            item.resolved_at = datetime.utcnow()
            return True
        return False

    def reject(self, review_id: str) -> bool:
        item = self.get(review_id)
        if item and item.status == "PENDING":
            item.status = "REJECTED"
            item.resolved_at = datetime.utcnow()
            return True
        return False

    def clear(self) -> None:
        self._queue.clear()


review_queue = ReviewQueueService()
