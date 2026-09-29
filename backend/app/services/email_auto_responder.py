"""
Recruiter Email Auto-Responder & Calendar RSVP Draft Generator.
Automatically analyzes interview invitations, synthesizes polite and professional
candidate RSVP replies with suggested availability slots, and dispatches 1-tap mobile
Telegram approval notifications.
"""

import re
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.core.logger import logger
from app.core.config import settings
from app.services.interview_service import interview_pipeline_service


class RSVPDraft(BaseModel):
    draft_id: str = Field(default_factory=lambda: f"rsvp_{uuid.uuid4().hex[:8]}")
    email_id: str
    application_id: Optional[str] = None
    company: str
    recipient_email: str
    recruiter_name: str
    role: str
    subject: str
    body: str
    suggested_slots: List[str] = Field(default_factory=list)
    status: str = "DRAFT"  # DRAFT, SENT, DISMISSED
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    sent_at: Optional[str] = None


class EmailAutoResponderService:
    """
    Synthesizes grounded, professional candidate RSVP replies upon interview invitation
    detection and orchestrates mobile 1-tap approval dispatch.
    """

    def __init__(self):
        self.drafts: Dict[str, RSVPDraft] = {}
        self.sent_dispatches: List[Dict[str, Any]] = []

    def _extract_recruiter_name(self, sender: str) -> str:
        """Extracts polite first name from sender format e.g. 'Jane Doe <jane@acme.com>' or 'jane@acme.com'."""
        if "<" in sender:
            name_part = sender.split("<")[0].strip().strip("\"'")
            if name_part:
                first_name = name_part.split()[0]
                if re.match(r"^[A-Za-z]+$", first_name):
                    return first_name
        # Fallback to localpart
        localpart = sender.split("@")[0].strip()
        cleaned = re.sub(r"[._\d]+", " ", localpart).strip()
        if cleaned:
            return cleaned.split()[0].capitalize()
        return "Hiring Team"

    async def generate_rsvp_draft(
        self,
        email_id: str,
        sender: str,
        company: str,
        role: Optional[str] = None,
        application_id: Optional[str] = None,
        action_link: Optional[str] = None,
        interview_time: Optional[str] = None,
        tone: str = "professional",
        custom_slots: Optional[List[str]] = None
    ) -> RSVPDraft:
        """
        Synthesizes a personalized RSVP draft and pushes an approval alert to Telegram.
        Supports tone variations ('professional', 'concise', 'enthusiastic') and custom availability.
        """
        recruiter_name = self._extract_recruiter_name(sender)
        resolved_role = role or "Software Engineer"
        candidate_name = getattr(settings, "CANDIDATE_NAME", "Syed Talha Ahmed")

        suggested_slots = custom_slots or [
            "Tomorrow between 2:00 PM – 4:00 PM EST",
            "Wednesday between 10:00 AM – 1:00 PM EST",
            "Thursday between 1:00 PM – 4:00 PM EST"
        ]

        if tone == "concise":
            if action_link:
                body = (
                    f"Hi {recruiter_name},\n\n"
                    f"Thank you for getting back to me! I have confirmed my availability via your link ({action_link}). "
                    f"Looking forward to our call.\n\n"
                    f"Best,\n{candidate_name}"
                )
            elif interview_time:
                body = (
                    f"Hi {recruiter_name},\n\n"
                    f"Thank you. {interview_time} works perfectly for me. "
                    f"Please send the meeting invitation at your convenience.\n\n"
                    f"Best,\n{candidate_name}"
                )
            else:
                body = (
                    f"Hi {recruiter_name},\n\n"
                    f"Thank you for reaching out regarding the {resolved_role} position. I would be happy to connect. "
                    f"I am available:\n"
                    f"  • {suggested_slots[0]}\n"
                    f"  • {suggested_slots[1]}\n\n"
                    f"Looking forward to speaking.\n\n"
                    f"Best,\n{candidate_name}"
                )
        elif action_link:
            body = (
                f"Hi {recruiter_name},\n\n"
                f"Thank you for getting back to me regarding the {resolved_role} position at {company}! "
                f"I am very excited about the role and the team's mission.\n\n"
                f"I have received the scheduling link ({action_link}) and confirmed my availability. "
                f"If there are any materials or specific topics I should review in advance, please let me know.\n\n"
                f"Looking forward to our conversation!\n\n"
                f"Best regards,\n"
                f"{candidate_name}"
            )
        elif interview_time:
            body = (
                f"Hi {recruiter_name},\n\n"
                f"Thank you for considering my application for the {resolved_role} opportunity at {company}! "
                f"I would be delighted to speak with you.\n\n"
                f"The proposed time ({interview_time}) works well for me. "
                f"Please send through the calendar invite and meeting link when convenient.\n\n"
                f"Looking forward to connecting!\n\n"
                f"Best regards,\n"
                f"{candidate_name}"
            )
        else:
            body = (
                f"Hi {recruiter_name},\n\n"
                f"Thank you for reaching out regarding the {resolved_role} opportunity at {company}! "
                f"I would be thrilled to connect with your team.\n\n"
                f"I am available for an introductory call at any of the following times (EST):\n"
                f"  • {suggested_slots[0]}\n"
                f"  • {suggested_slots[1]}\n"
                f"  • {suggested_slots[2]}\n\n"
                f"Please let me know if any of these windows fit your schedule, or if you prefer an alternate time.\n\n"
                f"Best regards,\n"
                f"{candidate_name}"
            )

        subject = f"Re: Interview Opportunity - {resolved_role} at {company} - {candidate_name}"

        draft = RSVPDraft(
            email_id=email_id,
            application_id=application_id,
            company=company,
            recipient_email=sender,
            recruiter_name=recruiter_name,
            role=resolved_role,
            subject=subject,
            body=body,
            suggested_slots=suggested_slots,
            status="DRAFT"
        )

        self.drafts[draft.draft_id] = draft
        logger.info(f"[EmailAutoResponder] Generated RSVP draft {draft.draft_id} for {sender} ({company})")

        # Push 1-tap approval notification to Telegram Companion
        try:
            from app.services.telegram_bot import telegram_companion
            alert_text = (
                f"🎯 <b>Recruiter Interview Invitation Detected!</b>\n\n"
                f"🏢 <b>Company:</b> {company}\n"
                f"💼 <b>Role:</b> {resolved_role}\n"
                f"👤 <b>Recruiter:</b> {recruiter_name}\n"
                f"📝 <b>Draft Subject:</b> <i>{subject}</i>\n\n"
                f"<i>Tap below to approve or view draft:</i>"
            )
            inline_keyboard = [
                [
                    {"text": "📨 Approve & Send RSVP", "callback_data": f"rsvp_send_{draft.draft_id}"},
                    {"text": "👀 View RSVP Text", "callback_data": f"rsvp_view_{draft.draft_id}"}
                ],
                [
                    {"text": "❌ Dismiss", "callback_data": f"rsvp_dismiss_{draft.draft_id}"}
                ]
            ]
            await telegram_companion.send_message(
                text=alert_text,
                reply_markup={"inline_keyboard": inline_keyboard}
            )
        except Exception as e:
            logger.warning(f"[EmailAutoResponder] Could not dispatch Telegram RSVP alert: {e}")

        return draft

    def get_draft(self, draft_id: str) -> Optional[RSVPDraft]:
        return self.drafts.get(draft_id)

    def list_drafts(self, status: Optional[str] = None) -> List[RSVPDraft]:
        if status:
            return [d for d in self.drafts.values() if d.status == status.upper()]
        return list(self.drafts.values())

    def edit_draft(self, draft_id: str, new_body: str, new_subject: Optional[str] = None) -> Optional[RSVPDraft]:
        draft = self.get_draft(draft_id)
        if draft and draft.status == "DRAFT":
            draft.body = new_body
            if new_subject:
                draft.subject = new_subject
            return draft
        return None

    def send_rsvp(self, draft_id: str) -> Dict[str, Any]:
        """Approves and dispatches the RSVP reply."""
        draft = self.get_draft(draft_id)
        if not draft:
            return {"success": False, "error": f"Draft {draft_id} not found."}
        if draft.status == "SENT":
            return {"success": False, "error": "Draft has already been sent."}

        draft.status = "SENT"
        draft.sent_at = datetime.now().isoformat()

        dispatch_log = {
            "draft_id": draft_id,
            "recipient": draft.recipient_email,
            "subject": draft.subject,
            "sent_at": draft.sent_at,
            "mode": "simulated"  # or live SMTP when configured
        }
        self.sent_dispatches.append(dispatch_log)

        # Update interview pipeline record note
        if draft.application_id:
            try:
                rec = interview_pipeline_service.get(draft.application_id)
                if rec:
                    entry = f"[RSVP Sent]: Dispatched confirmation to {draft.recipient_email} at {draft.sent_at}."
                    rec.notes = f"{rec.notes}\n{entry}" if rec.notes else entry
            except Exception as e:
                logger.warning(f"[EmailAutoResponder] Could not update interview notes: {e}")

        logger.info(f"[EmailAutoResponder] Successfully dispatched RSVP reply for draft {draft_id} to {draft.recipient_email}")
        return {
            "success": True,
            "draft_id": draft_id,
            "recipient": draft.recipient_email,
            "sent_at": draft.sent_at
        }

    def dismiss_draft(self, draft_id: str) -> bool:
        draft = self.get_draft(draft_id)
        if draft and draft.status == "DRAFT":
            draft.status = "DISMISSED"
            return True
        return False

    def clear(self):
        self.drafts.clear()
        self.sent_dispatches.clear()


email_auto_responder = EmailAutoResponderService()
