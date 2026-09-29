"""
Recruiter Response Monitoring & Email Classification Engine.
Classifies inbound recruiter emails into interview invitations, online assessments, and rejections.
"""

import re
import imaplib
import email
from email.header import decode_header
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logger import logger
from app.core.llm import llm_client
from app.services.notification_service import notification_service, NotificationEventType


class RecruiterEmailIntent(str, Enum):
    INTERVIEW_INVITATION = "INTERVIEW_INVITATION"
    ONLINE_ASSESSMENT = "ONLINE_ASSESSMENT"
    APPLICATION_RECEIVED = "APPLICATION_RECEIVED"
    REJECTION = "REJECTION"
    GENERAL_INQUIRY = "GENERAL_INQUIRY"
    UNKNOWN = "UNKNOWN"


class EmailClassificationResult(BaseModel):
    intent: RecruiterEmailIntent
    confidence: float = 0.8
    company: Optional[str] = None
    job_title: Optional[str] = None
    action_link: Optional[str] = None
    suggested_action: Optional[str] = None
    summary: str = ""


class InboxMonitorService:
    """IMAP client and intent classifier for recruiter communications."""

    def __init__(self):
        self.enabled = settings.INBOX_MONITOR_ENABLED
        self.host = settings.IMAP_HOST
        self.port = settings.IMAP_PORT
        self.user = settings.IMAP_USER
        self.password = settings.IMAP_PASSWORD
        self.use_ssl = settings.IMAP_USE_SSL

    async def classify_email_content(
        self,
        sender: str,
        subject: str,
        body_text: str
    ) -> EmailClassificationResult:
        """Analyze email text to determine recruiter intent and extract actionable links."""
        full_text = f"Subject: {subject}\nSender: {sender}\n\n{body_text}".lower()

        # 1. Fast Pattern Matching
        meeting_links = re.findall(
            r"https?://(?:calendly\.com|zoom\.us|meet\.google\.com|teams\.microsoft\.com)/[^\s<>'\"]+",
            body_text,
            re.IGNORECASE
        )
        assessment_links = re.findall(
            r"https?://(?:hackerrank\.com|codility\.com|glider\.ai|testgorilla\.com|coderbyte\.com)/[^\s<>'\"]+",
            body_text,
            re.IGNORECASE
        )

        # Rejection detection
        rejection_keywords = [
            "unfortunately", "not moving forward", "other candidates",
            "decided not to proceed", "wish you the best", "regret to inform",
            "not selected", "pursuing other candidates"
        ]
        is_rejection = any(kw in full_text for kw in rejection_keywords)

        # Assessment detection
        assessment_keywords = [
            "online assessment", "coding challenge", "hackerrank",
            "technical assessment", "complete the test", "assessment link",
            "take-home assignment", "online test"
        ]
        is_assessment = any(kw in full_text for kw in assessment_keywords) or len(assessment_links) > 0

        # Interview invite detection
        interview_keywords = [
            "interview", "schedule a call", "speak with you", "discuss your application",
            "chat with the team", "availability for a call", "phone screen",
            "shortlisted for an interview", "invitation to interview", "calendly"
        ]
        is_interview = (any(kw in full_text for kw in interview_keywords) and not is_rejection) or len(meeting_links) > 0

        # Application received / confirmation
        confirmation_keywords = [
            "thank you for applying", "we received your application",
            "application received", "successfully submitted", "we have received your resume"
        ]
        is_confirmation = any(kw in full_text for kw in confirmation_keywords)

        # Deterministic match
        if is_interview:
            link = meeting_links[0] if meeting_links else None
            return EmailClassificationResult(
                intent=RecruiterEmailIntent.INTERVIEW_INVITATION,
                confidence=0.95,
                action_link=link,
                suggested_action="Select an interview time slot" if link else "Reply with your availability",
                summary=f"Interview invitation received from {sender}."
            )
        elif is_assessment:
            link = assessment_links[0] if assessment_links else None
            return EmailClassificationResult(
                intent=RecruiterEmailIntent.ONLINE_ASSESSMENT,
                confidence=0.92,
                action_link=link,
                suggested_action="Complete the technical assessment before deadline",
                summary=f"Online assessment requested from {sender}."
            )
        elif is_rejection:
            return EmailClassificationResult(
                intent=RecruiterEmailIntent.REJECTION,
                confidence=0.90,
                suggested_action="Archive and move forward",
                summary=f"Application status update: Not selected by {sender}."
            )
        elif is_confirmation:
            return EmailClassificationResult(
                intent=RecruiterEmailIntent.APPLICATION_RECEIVED,
                confidence=0.95,
                summary=f"Application receipt acknowledged by {sender}."
            )

        # 2. LLM Reasoning Fallback for ambiguous recruiter emails
        try:
            prompt = f"""
            Analyze the following email from a recruiter or job platform:
            Sender: {sender}
            Subject: {subject}
            Body:
            {body_text[:1500]}

            Classify into one intent:
            INTERVIEW_INVITATION, ONLINE_ASSESSMENT, APPLICATION_RECEIVED, REJECTION, GENERAL_INQUIRY, UNKNOWN.
            Respond in JSON with keys:
            intent, confidence (0.0 to 1.0), company, job_title, action_link, suggested_action, summary
            """
            res = await llm_client.generate_json(prompt, system_prompt="You are an expert HR recruiter email classifier.")
            if res and res.get("intent") in RecruiterEmailIntent.__members__:
                return EmailClassificationResult(
                    intent=RecruiterEmailIntent(res["intent"]),
                    confidence=float(res.get("confidence", 0.8)),
                    company=res.get("company"),
                    job_title=res.get("job_title"),
                    action_link=res.get("action_link"),
                    suggested_action=res.get("suggested_action"),
                    summary=res.get("summary", "Processed by AI classifier.")
                )
        except Exception as e:
            logger.debug(f"[InboxMonitor] LLM fallback error: {e}")

        return EmailClassificationResult(
            intent=RecruiterEmailIntent.UNKNOWN,
            confidence=0.5,
            summary="Could not determine recruiter intent."
        )

    async def process_classified_email(
        self,
        classification: EmailClassificationResult,
        sender: str,
        subject: str
    ):
        """Dispatch notifications and update application statuses based on recruiter intent."""
        if classification.intent == RecruiterEmailIntent.INTERVIEW_INVITATION:
            await notification_service.notify(
                event_type=NotificationEventType.INTERVIEW_INVITATION,
                title="🎉 Interview Invitation Detected!",
                message=f"Recruiter at {sender} sent an interview invitation. Action: {classification.suggested_action or 'Reply'}",
                details={
                    "sender": sender,
                    "subject": subject,
                    "action_link": classification.action_link,
                    "confidence": classification.confidence
                }
            )

        elif classification.intent == RecruiterEmailIntent.ONLINE_ASSESSMENT:
            await notification_service.notify(
                event_type=NotificationEventType.ASSESSMENT_REQUEST,
                title="📝 Coding Assessment Required",
                message=f"Assessment invitation from {sender}. Link: {classification.action_link or 'Check email'}",
                details={
                    "sender": sender,
                    "subject": subject,
                    "action_link": classification.action_link
                }
            )

    async def scan_inbox(self, max_emails: int = 10) -> List[EmailClassificationResult]:
        """Check IMAP inbox for unseen recruiter emails and process alerts."""
        if not self.enabled or not self.host or not self.user or not self.password:
            logger.info("[InboxMonitor] IMAP monitoring is disabled or unconfigured.")
            return []

        results: List[EmailClassificationResult] = []
        try:
            if self.use_ssl:
                mail = imaplib.IMAP4_SSL(self.host, self.port)
            else:
                mail = imaplib.IMAP4(self.host, self.port)

            mail.login(self.user, self.password)
            mail.select("INBOX")

            status, data = mail.search(None, "UNSEEN")
            if status != "OK" or not data[0]:
                mail.close()
                mail.logout()
                return []

            email_ids = data[0].split()
            # Process latest emails
            for eid in email_ids[-max_emails:]:
                status, msg_data = mail.fetch(eid, "(RFC822)")
                if status != "OK":
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # Decode subject
                subject_raw, encoding = decode_header(msg.get("Subject", ""))[0]
                if isinstance(subject_raw, bytes):
                    subject = subject_raw.decode(encoding or "utf-8", errors="ignore")
                else:
                    subject = str(subject_raw)

                sender = msg.get("From", "")

                # Extract plain text body
                body = ""
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            payload = part.get_payload(decode=True)
                            if payload:
                                body += payload.decode("utf-8", errors="ignore")
                else:
                    payload = msg.get_payload(decode=True)
                    if payload:
                        body = payload.decode("utf-8", errors="ignore")

                classification = await self.classify_email_content(sender, subject, body)
                results.append(classification)
                await self.process_classified_email(classification, sender, subject)

            mail.close()
            mail.logout()
        except Exception as e:
            logger.error(f"[InboxMonitor] IMAP error during inbox scan: {e}")

        return results


inbox_monitor_service = InboxMonitorService()
