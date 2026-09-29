"""
Email & WhatsApp Outreach Service.

Generates personalized, recruiter-directed cold outreach drafts (email and WhatsApp click-to-chat)
and delivers SMTP emails with tailored resume attachments under strict human-approval safety guardrails.
"""

import json
import os
import smtplib
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.core.config import settings
from app.core.logger import logger
from app.core.llm import llm_client
from app.models.job import (
    OutreachMessage,
    OutreachChannel,
    OutreachStatus,
    RecruiterContact,
    ResumeProfile
)
from app.services.resume_parser import resume_parser_service


class EmailOutreachService:
    """Outreach engine managing cold email and WhatsApp messaging with candidate resume delivery."""

    def __init__(self):
        self.outreach_dir = settings.OUTREACH_DIR
        self.outreach_dir.mkdir(exist_ok=True, parents=True)

    def generate_whatsapp_url(self, phone: str, message: str) -> str:
        """
        Constructs an official WhatsApp click-to-chat URL (https://wa.me/<number>?text=<encoded_text>).
        Phone number must be clean digits without '+' or special symbols.
        """
        clean_digits = "".join(filter(str.isdigit, phone))
        encoded_text = urllib.parse.quote(message)
        return f"https://wa.me/{clean_digits}?text={encoded_text}"

    async def draft_outreach(
        self,
        job_id: str,
        job_title: str,
        company: str,
        recipient: RecruiterContact,
        candidate_profile: Optional[ResumeProfile] = None,
        channel: OutreachChannel = OutreachChannel.EMAIL,
        attachment_path: Optional[str] = None
    ) -> OutreachMessage:
        """
        Drafts a tailored outreach message (Email or WhatsApp) grounded in candidate credentials.
        """
        profile = candidate_profile or resume_parser_service.load_profile()
        if not profile:
            raise ValueError("Candidate profile not found. Please upload or configure profile first.")

        greeting_name = recipient.name or "Hiring Team"
        top_skills = ", ".join((profile.skills or [])[:4]) or "Software Engineering"
        exp_years = profile.years_of_experience
        notice = (profile.qa_vault.notice_period if profile.qa_vault else "Immediate") or "Immediate"

        if channel == OutreachChannel.WHATSAPP:
            # Short, friendly, impactful WhatsApp introduction
            body_text = (
                f"Hi {greeting_name},\n\n"
                f"I hope you're having a productive week. I noticed the {job_title} opening at {company} "
                f"and wanted to reach out directly. I bring {exp_years} years of experience in {top_skills}.\n\n"
                f"You can review my work and background at {profile.linkedin_url or profile.portfolio_url or 'my profile'}. "
                f"I am available to join {notice.lower()} and would love to connect!"
            )
            whatsapp_url = self.generate_whatsapp_url(
                recipient.whatsapp_number or recipient.phone or "",
                body_text
            ) if (recipient.whatsapp_number or recipient.phone) else None

            msg = OutreachMessage(
                job_id=job_id,
                job_title=job_title,
                company=company,
                recipient=recipient,
                channel=OutreachChannel.WHATSAPP,
                subject=None,
                body_text=body_text,
                attachment_path=attachment_path,
                whatsapp_url=whatsapp_url,
                status=OutreachStatus.DRAFTED,
                requires_approval=settings.OUTREACH_REQUIRE_APPROVAL
            )

        else:
            # Professional cold application email
            subject = f"Application for {job_title} - {profile.full_name}"

            # Attempt LLM drafting with strict zero-fabrication prompt
            llm_draft = await self._generate_llm_email_draft(job_title, company, recipient, profile)
            if llm_draft:
                body_text = llm_draft.get("body", "")
                if llm_draft.get("subject"):
                    subject = llm_draft["subject"]
            else:
                body_text = self._build_template_email_body(
                    job_title, company, greeting_name, profile, top_skills, exp_years, notice
                )

            body_html = body_text.replace("\n\n", "</p><p>").replace("\n", "<br>")
            body_html = f"<div style='font-family: Arial, sans-serif; font-size: 14px; line-height: 1.6;'><p>{body_html}</p></div>"

            msg = OutreachMessage(
                job_id=job_id,
                job_title=job_title,
                company=company,
                recipient=recipient,
                channel=OutreachChannel.EMAIL,
                subject=subject,
                body_text=body_text,
                body_html=body_html,
                attachment_path=attachment_path,
                status=OutreachStatus.DRAFTED,
                requires_approval=settings.OUTREACH_REQUIRE_APPROVAL
            )

        # Save draft locally
        self._save_outreach(msg)
        return msg

    async def _generate_llm_email_draft(
        self,
        job_title: str,
        company: str,
        recipient: RecruiterContact,
        profile: ResumeProfile
    ) -> Optional[Dict[str, str]]:
        """Synthesize high-conversion email draft using LLM grounded in candidate data."""
        skills_str = ", ".join(profile.skills or [])
        recent_work = ""
        if profile.work_experience:
            top = profile.work_experience[0]
            recent_work = f"Recent Role: {top.title} at {top.company} - {top.description}"

        prompt = f"""
Write a concise, professional cold job application email to a recruiter.

RECIPIENT: {recipient.name or 'Hiring Manager'} ({company})
TARGET ROLE: {job_title}
CANDIDATE:
- Name: {profile.full_name}
- Years of Experience: {profile.years_of_experience}
- Core Skills: {skills_str}
- {recent_work}
- Availability / Notice: {profile.qa_vault.notice_period if profile.qa_vault else 'Immediate'}

GUIDELINES:
1. Subject line must be punchy and clear: "Application: {job_title} - {profile.full_name}"
2. Exactly 3 short paragraphs:
   - Paragraph 1: State role interest and current background.
   - Paragraph 2: Highlight 2-3 specific matching achievements or technologies from candidate's profile.
   - Paragraph 3: Mention attached resume, notice period, and call to action.
3. Sign-off with candidate's full name, phone ({profile.phone}), and links ({profile.linkedin_url}).
4. Strict zero-fabrication: do not invent past companies, degrees, or metrics.

Return JSON:
{{
  "subject": "email subject",
  "body": "email text"
}}
"""
        try:
            res = await llm_client.generate_json(prompt)
            if res and res.get("body"):
                return res
        except Exception as e:
            logger.warning(f"Failed to generate LLM outreach draft: {e}")
        return None

    def _build_template_email_body(
        self,
        job_title: str,
        company: str,
        greeting_name: str,
        profile: ResumeProfile,
        top_skills: str,
        exp_years: float,
        notice: str
    ) -> str:
        """Deterministic email body fallback when LLM is offline."""
        contact_info_lines = [profile.full_name]
        if profile.email:
            contact_info_lines.append(f"Email: {profile.email}")
        if profile.phone:
            contact_info_lines.append(f"Phone: {profile.phone}")
        if profile.linkedin_url:
            contact_info_lines.append(f"LinkedIn: {profile.linkedin_url}")
        if profile.github_url:
            contact_info_lines.append(f"GitHub: {profile.github_url}")

        signoff_block = "\n".join(contact_info_lines)

        return (
            f"Dear {greeting_name},\n\n"
            f"I am writing to express my enthusiasm for the {job_title} position at {company}. "
            f"With {exp_years} years of hands-on experience specializing in {top_skills}, "
            f"I have successfully engineered and deployed scalable software systems.\n\n"
            f"In my professional work, I have focused on writing clean, maintainable code and solving complex technical challenges. "
            f"I believe my background and technical capabilities make me a strong match for your engineering team's current initiatives.\n\n"
            f"I have attached my tailored resume for your consideration. My official notice period is {notice.lower()}, "
            f"and I am eager to discuss how my expertise can support {company}'s objectives.\n\n"
            f"Thank you for your time and consideration.\n\n"
            f"Best regards,\n"
            f"{signoff_block}"
        )

    def send_email(
        self,
        outreach_id: str,
        force_send: bool = False
    ) -> OutreachMessage:
        """
        Dispatches an approved outreach email via SMTP with optional resume attachment.
        Enforces human-approval guardrail unless explicitly confirmed.
        """
        msg = self.get_outreach(outreach_id)
        if not msg:
            raise ValueError(f"Outreach message with id '{outreach_id}' not found.")

        if msg.requires_approval and not force_send and msg.status == OutreachStatus.DRAFTED:
            raise PermissionError(
                f"Outreach message {outreach_id} requires human approval before sending. Set force_send=True to approve."
            )

        if not msg.recipient.email:
            raise ValueError(f"Outreach message {outreach_id} has no recipient email address.")

        # Check SMTP settings
        if not settings.SMTP_HOST:
            if settings.DRY_RUN:
                logger.info(f"[DRY_RUN] Email to {msg.recipient.email} simulated successfully.")
                msg.status = OutreachStatus.SENT
                msg.sent_at = datetime.now().isoformat()
                self._save_outreach(msg)
                return msg
            raise ValueError("SMTP_HOST is not configured. Please configure SMTP settings in .env.")

        sender_email = settings.SENDER_EMAIL or settings.SMTP_USER
        if not sender_email:
            raise ValueError("SENDER_EMAIL or SMTP_USER must be configured to send emails.")

        # Build MIME Message
        email_msg = MIMEMultipart("alternative")
        email_msg["Subject"] = msg.subject or f"Application for {msg.job_title}"
        email_msg["From"] = f"{settings.SENDER_NAME} <{sender_email}>" if settings.SENDER_NAME else sender_email
        email_msg["To"] = msg.recipient.email

        # Attach text and HTML parts
        email_msg.attach(MIMEText(msg.body_text, "plain", "utf-8"))
        if msg.body_html:
            email_msg.attach(MIMEText(msg.body_html, "html", "utf-8"))

        # Attach resume PDF if present
        if msg.attachment_path and os.path.exists(msg.attachment_path):
            try:
                with open(msg.attachment_path, "rb") as f:
                    part = MIMEApplication(f.read(), Name=os.path.basename(msg.attachment_path))
                    part["Content-Disposition"] = f'attachment; filename="{os.path.basename(msg.attachment_path)}"'
                    email_msg.attach(part)
            except Exception as e:
                logger.error(f"Failed to attach resume {msg.attachment_path}: {e}")

        # Send via smtplib
        try:
            if settings.SMTP_USE_SSL:
                server = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
            else:
                server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
                if settings.SMTP_USE_TLS:
                    server.starttls()

            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)

            server.send_message(email_msg)
            server.quit()

            msg.status = OutreachStatus.SENT
            msg.sent_at = datetime.now().isoformat()
            msg.error_message = None
            logger.info(f"Outreach email successfully sent to {msg.recipient.email} (Job: {msg.job_title})")
        except Exception as e:
            msg.status = OutreachStatus.FAILED
            msg.error_message = str(e)
            logger.error(f"Failed to send email to {msg.recipient.email}: {e}")
            raise

        self._save_outreach(msg)
        return msg

    def get_outreach(self, outreach_id: str) -> Optional[OutreachMessage]:
        """Load outreach message by ID from disk."""
        path = self.outreach_dir / f"{outreach_id}.json"
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return OutreachMessage(**data)
        except Exception as e:
            logger.error(f"Error loading outreach message {outreach_id}: {e}")
            return None

    def list_outreach_messages(
        self,
        status: Optional[OutreachStatus] = None,
        limit: int = 50
    ) -> List[OutreachMessage]:
        """List persisted outreach drafts and sent messages."""
        messages: List[OutreachMessage] = []
        for file in sorted(self.outreach_dir.glob("outreach_*.json"), reverse=True):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    msg = OutreachMessage(**data)
                    if status is None or msg.status == status:
                        messages.append(msg)
                        if len(messages) >= limit:
                            break
            except Exception:
                continue
        return messages

    def _save_outreach(self, msg: OutreachMessage) -> None:
        """Persist message to disk."""
        path = self.outreach_dir / f"{msg.id}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(msg.model_dump(), f, indent=2, ensure_ascii=False)


email_outreach_service = EmailOutreachService()
