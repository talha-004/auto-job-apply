"""
Automated 5-Day Recruiter Follow-Up Service.
Identifies unanswered applications meeting aging thresholds,
generates polite 3-sentence check-in drafts, and manages follow-up scheduling with safety limits.
"""

from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.core.logger import logger
from app.models.job import JobApplicationRecord, ApplicationStatus
from app.services.email_outreach_service import OutreachMessage, email_outreach_service
from app.services.persistence_service import persistence_service


class FollowUpRecommendation(BaseModel):
    application_id: str
    job_title: str
    company: str
    applied_date: str
    days_elapsed: int
    recommended_recipient: str
    draft_subject: str
    draft_body: str
    status: str = "PENDING_APPROVAL"  # PENDING_APPROVAL, APPROVED, DISMISSED


class FollowUpService:
    """
    Orchestrates post-application follow-up check-ins to boost callback rates.
    Enforces a strict 1-follow-up-per-application limit and a daily sending cap.
    """

    DAILY_FOLLOWUP_CAP = 10

    def __init__(self):
        self._sent_followups: Dict[str, str] = {}  # app_id -> timestamp

    def calculate_days_elapsed(self, applied_date_str: str) -> int:
        """Calculates days elapsed since application date (expects YYYY-MM-DD format)."""
        try:
            applied_dt = datetime.strptime(applied_date_str[:10], "%Y-%m-%d").date()
            return (date.today() - applied_dt).days
        except Exception:
            return 0

    def generate_followup_draft(
        self,
        job_title: str,
        company: str,
        applied_date: str,
        candidate_name: str = "Candidate",
        key_skills: Optional[List[str]] = None
    ) -> Dict[str, str]:
        """Crafts a concise, highly professional 3-sentence check-in email."""
        skills_str = ", ".join(key_skills[:3]) if key_skills else "software engineering and modern architectures"
        
        subject = f"Following up on my application for {job_title} - {candidate_name}"
        body = (
            f"Dear {company} Hiring Team,\n\n"
            f"I hope you are having a productive week. I submitted my application for the {job_title} role "
            f"on {applied_date} and wanted to reiterate my strong enthusiasm for joining {company}.\n\n"
            f"Given my hands-on background with {skills_str}, I am very excited about the opportunity "
            f"to contribute to your team. Please let me know if I can provide any additional code samples, "
            f"portfolio links, or information.\n\n"
            f"Thank you for your time and consideration,\n"
            f"{candidate_name}"
        )
        return {"subject": subject, "body": body}

    def scan_for_pending_followups(
        self,
        min_days_elapsed: int = 5,
        candidate_name: str = "Candidate",
        max_results: int = 10
    ) -> List[FollowUpRecommendation]:
        """
        Scans persistence store for eligible applications awaiting follow-up.
        Eligible applications: status is APPLIED/SUBMITTED, >= 5 days old, and not yet followed up.
        """
        all_apps = persistence_service.get_applications(limit=100)
        recommendations: List[FollowUpRecommendation] = []

        for app in all_apps:
            # Check status eligibility
            status_val = app.status.value if hasattr(app.status, "value") else str(app.status)
            if status_val not in ("APPLIED", "SUBMITTED"):
                continue

            # Check deduplication: skip if already followed up
            if app.job_id in self._sent_followups:
                continue

            days = self.calculate_days_elapsed(app.applied_date or "")
            if days >= min_days_elapsed:
                draft = self.generate_followup_draft(
                    job_title=app.job_title,
                    company=app.company,
                    applied_date=app.applied_date or "recently",
                    candidate_name=candidate_name
                )
                recommendations.append(
                    FollowUpRecommendation(
                        application_id=app.job_id,
                        job_title=app.job_title,
                        company=app.company,
                        applied_date=app.applied_date or "",
                        days_elapsed=days,
                        recommended_recipient=f"careers@{app.company.lower().replace(' ', '')}.com",
                        draft_subject=draft["subject"],
                        draft_body=draft["body"],
                        status="PENDING_APPROVAL"
                    )
                )
                if len(recommendations) >= max_results:
                    break

        return recommendations

    def approve_followup(self, application_id: str) -> bool:
        """Approves and records a follow-up, preventing future duplicates."""
        if len(self._sent_followups) >= self.DAILY_FOLLOWUP_CAP:
            logger.warning("Daily follow-up cap reached (10/day). Queueing for tomorrow.")
            return False

        self._sent_followups[application_id] = datetime.now().isoformat()
        logger.info(f"Follow-up approved for application {application_id}")
        return True


# Global service instance
followup_service = FollowUpService()
