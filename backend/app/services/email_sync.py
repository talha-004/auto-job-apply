"""
Inbound Email & Interview Intelligence Synchronization Service.
Scans incoming recruiter messages via IMAP or simulation, classifies intent
(Interviews, Coding Assessments, Rejections, Offers), sanitizes against prompt injection,
and automatically transitions application lifecycle statuses in InterviewPipelineService.
"""

import re
import imaplib
import email
from email.header import decode_header
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logger import logger
from app.core.prompt_guard import prompt_guard
from app.services.inbox_monitor import RecruiterEmailIntent, EmailClassificationResult, inbox_monitor_service
from app.services.interview_service import interview_pipeline_service, PostApplyStatus, InterviewRound


class ClassifiedEmailRecord(BaseModel):
    id: str
    sender: str
    subject: str
    intent: RecruiterEmailIntent
    confidence: float
    company_detected: Optional[str] = None
    action_link: Optional[str] = None
    suggested_action: Optional[str] = None
    matched_application_id: Optional[str] = None
    status_updated: bool = False
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class EmailSyncService:
    """
    Manages mailbox polling, prompt-guard sanitization, recruiter intent extraction,
    and automatic lifecycle updates.
    """

    def __init__(self):
        self.history: List[ClassifiedEmailRecord] = []

    def sanitize_email_content(self, body_text: str) -> str:
        """Strips injection payloads and wraps email body safely."""
        return prompt_guard.sanitize(body_text)

    def extract_interview_datetime(self, text: str) -> Optional[str]:
        """Heuristically extracts proposed date/time mentions from email body."""
        patterns = [
            r"(?:on\s+)?((?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)[,\s]+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm))?)",
            r"(?:on\s+)?(\d{1,2}[/-]\d{1,2}[/-]\d{2,4}(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm))?)",
            r"(tomorrow\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
            r"(\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\s*(?:est|pst|cst|utc|ist|gmt)\b)"
        ]
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def find_matching_application_id(self, company_name: Optional[str], sender: str) -> Optional[str]:
        """Finds application ID in InterviewPipelineService matching company or sender domain."""
        if not company_name and not sender:
            return None

        norm_company = company_name.lower().strip() if company_name else ""
        norm_sender = sender.lower()

        for app_id, rec in interview_pipeline_service.records.items():
            app_company = rec.company.lower().strip()
            if norm_company and (norm_company in app_company or app_company in norm_company):
                return app_id
            # Domain check (e.g. recruiter@google.com -> Google)
            domain = norm_sender.split("@")[-1].split(".")[0] if "@" in norm_sender else ""
            if len(domain) > 2 and domain in app_company:
                return app_id

        return None

    async def ingest_and_process_email(
        self,
        sender: str,
        subject: str,
        body: str
    ) -> ClassifiedEmailRecord:
        """Processes a single email: sanitizes, classifies, and updates matching application."""
        clean_body = self.sanitize_email_content(body)
        classification = await inbox_monitor_service.classify_email_content(sender, subject, clean_body)

        # Detect company from subject or sender if missing
        company = classification.company
        if not company:
            # Try to match "at [Company]" or from "[Company]"
            match = re.search(r"(?:at|with|from)\s+([A-Z][A-Za-z0-9\s&]+?)(?:\s+for|\s+regarding|\s+-|$)", subject)
            if match:
                company = match.group(1).strip()

        matched_app_id = self.find_matching_application_id(company, sender)
        status_updated = False

        if matched_app_id:
            if classification.intent == RecruiterEmailIntent.INTERVIEW_INVITATION:
                interview_time = self.extract_interview_datetime(clean_body)
                notes = f"Auto-detected interview invitation from {sender}."
                if interview_time:
                    notes += f" Mentioned time: {interview_time}."
                if classification.action_link:
                    notes += f" Schedule link: {classification.action_link}"

                interview_pipeline_service.schedule_interview(
                    application_id=matched_app_id,
                    round_type="Recruiter Screen",
                    scheduled_at=datetime.now(),
                    meeting_link=classification.action_link,
                    notes=notes
                )
                status_updated = True
                logger.info(f"[EmailSync] Auto-scheduled interview for application {matched_app_id} ({company})")

            elif classification.intent == RecruiterEmailIntent.REJECTION:
                interview_pipeline_service.update_status(
                    application_id=matched_app_id,
                    new_status=PostApplyStatus.REJECTED,
                    notes=f"Auto-detected rejection email from {sender}."
                )
                status_updated = True
                logger.info(f"[EmailSync] Auto-marked application {matched_app_id} as REJECTED ({company})")

            elif classification.intent == RecruiterEmailIntent.ONLINE_ASSESSMENT:
                interview_pipeline_service.schedule_interview(
                    application_id=matched_app_id,
                    round_type="Technical",
                    scheduled_at=datetime.now(),
                    meeting_link=classification.action_link,
                    notes=f"Coding Assessment received: {classification.action_link or 'Check email'}"
                )
                status_updated = True
                logger.info(f"[EmailSync] Auto-recorded technical assessment for application {matched_app_id}")

        record = ClassifiedEmailRecord(
            id=f"email_{len(self.history) + 1}",
            sender=sender,
            subject=subject,
            intent=classification.intent,
            confidence=classification.confidence,
            company_detected=company,
            action_link=classification.action_link,
            suggested_action=classification.suggested_action,
            matched_application_id=matched_app_id,
            status_updated=status_updated
        )
        self.history.append(record)
        return record

    async def sync_mailbox(self, max_emails: int = 15) -> List[ClassifiedEmailRecord]:
        """Polls live IMAP if configured, returning processed records."""
        if not settings.INBOX_MONITOR_ENABLED or not settings.IMAP_HOST or not settings.IMAP_USER:
            logger.info("[EmailSync] IMAP is not live-configured; returning cached sync records.")
            return self.history[-max_emails:]

        # If configured, scan live
        raw_results = await inbox_monitor_service.scan_inbox(max_emails=max_emails)
        return self.history[-len(raw_results):]


email_sync_service = EmailSyncService()
