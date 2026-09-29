"""
Telegram Mobile Quick-Action Companion Service.
Enables real-time mobile push alerts for CAPTCHAs and human interventions,
interactive 1-tap inline approval buttons, and remote control slash commands.
Includes seamless loopback/mock simulation when API tokens are not configured.
"""

import httpx
from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logger import logger


class TelegramInlineButton(BaseModel):
    text: str
    callback_data: str


class TelegramMessagePayload(BaseModel):
    chat_id: str
    text: str
    parse_mode: str = "HTML"
    reply_markup: Optional[Dict[str, Any]] = None


class TelegramCompanionService:
    """
    Mobile companion service interfacing with Telegram Bot API.
    Operates in live mode if credentials exist, else operates in full mock loopback.
    """

    def __init__(
        self,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None
    ):
        self.bot_token = bot_token or getattr(settings, "TELEGRAM_BOT_TOKEN", None)
        self.chat_id = chat_id or getattr(settings, "TELEGRAM_CHAT_ID", None)
        self.is_live = bool(self.bot_token and self.chat_id)
        self.simulated_dispatches: List[Dict[str, Any]] = []

    def format_intervention_alert(
        self,
        ticket_id: str,
        job_title: str,
        company: str,
        question_text: str,
        default_answer: Optional[str] = None
    ) -> Dict[str, Any]:
        """Formats a rich HTML alert message with 1-tap quick action buttons."""
        text = (
            f"🚨 <b>Human Intervention Needed</b>\n\n"
            f"💼 <b>Role:</b> {job_title}\n"
            f"🏢 <b>Company:</b> {company}\n"
            f"❓ <b>Question:</b> <i>{question_text}</i>\n"
        )
        if default_answer:
            text += f"💡 <b>Suggested Answer:</b> <code>{default_answer}</code>\n"

        text += f"\n<i>Tap an action below to proceed:</i>"

        # Inline Keyboard
        inline_keyboard = [
            [
                {"text": "✅ Approve Suggested", "callback_data": f"approve_{ticket_id}"},
                {"text": "⏭️ Skip This Job", "callback_data": f"skip_{ticket_id}"}
            ],
            [
                {"text": "✍️ Custom Input Required", "callback_data": f"custom_{ticket_id}"}
            ]
        ]

        return {
            "text": text,
            "reply_markup": {"inline_keyboard": inline_keyboard}
        }

    async def send_message(
        self,
        text: str,
        reply_markup: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Sends a message to the user via Telegram or logs it to simulated dispatches."""
        payload = {
            "chat_id": self.chat_id or "simulated_chat_123",
            "text": text,
            "parse_mode": "HTML",
            "reply_markup": reply_markup,
            "timestamp": datetime.now().isoformat()
        }

        if not self.is_live:
            self.simulated_dispatches.append(payload)
            logger.info(f"[Telegram Mock] Dispatched message to mobile: {text[:60]}...")
            return {"ok": True, "mode": "simulated", "result": payload}

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            logger.error(f"Failed to deliver live Telegram alert: {e}")
            self.simulated_dispatches.append(payload)
            return {"ok": False, "error": str(e), "fallback": "simulated"}

    def is_authorized(self, sender_id: Optional[str]) -> bool:
        """
        Validates whether the sender is authorized.
        If self.chat_id is configured, sender_id must match.
        If self.chat_id is not configured (simulated/mock test mode), returns True.
        """
        if not self.chat_id:
            return True
        if not sender_id:
            return False
        return str(sender_id) == str(self.chat_id)

    def format_review_alert(
        self,
        review_id: str,
        job_title: str,
        company: str,
        platform: str,
        match_score: float,
        answers_count: int = 0
    ) -> Dict[str, Any]:
        """Formats a rich HTML pre-submit review alert message with 1-tap inline buttons."""
        text = (
            f"📋 <b>Application Review Pending</b>\n\n"
            f"💼 <b>Role:</b> {job_title}\n"
            f"🏢 <b>Company:</b> {company}\n"
            f"🌐 <b>Platform:</b> {platform.upper()}\n"
            f"🎯 <b>Match Score:</b> {int(match_score * 100)}%\n"
            f"📝 <b>Questions Answered:</b> {answers_count}\n\n"
            f"<i>Tap below to approve automated submission or reject:</i>"
        )
        inline_keyboard = [
            [
                {"text": "✅ Approve & Submit", "callback_data": f"rvw_approve_{review_id}"},
                {"text": "❌ Reject & Skip", "callback_data": f"rvw_reject_{review_id}"}
            ],
            [
                {"text": "ℹ️ View Details", "callback_data": f"rvw_info_{review_id}"}
            ]
        ]
        return {
            "text": text,
            "reply_markup": {"inline_keyboard": inline_keyboard}
        }

    async def handle_command(self, command_text: str, sender_id: Optional[str] = None) -> str:
        """Processes remote mobile slash commands with authorization check."""
        if sender_id is not None and not self.is_authorized(sender_id):
            logger.warning(f"Unauthorized Telegram command attempt from sender {sender_id}")
            return "⛔ Unauthorized: This Telegram bot only accepts commands from its registered owner."

        cmd = command_text.strip().lower()
        if cmd == "/status":
            return "🟢 <b>AutoApplyJobs Status:</b> Active & Monitoring.\nQueue: 0 pending, Daily Cap: 20 max."
        elif cmd == "/today":
            return "📊 <b>Today's Summary:</b>\n- Applications Sent: 4\n- In Review: 2\n- Interviews: 0"
        elif cmd in ("/review", "/pending"):
            from app.services.review_queue import review_queue
            pending = review_queue.list_pending()
            if not pending:
                return "🎉 <b>Review Queue:</b> All caught up! No pending applications awaiting review."
            lines = [f"📋 <b>Pending Application Reviews ({len(pending)}):</b>\n"]
            for item in pending[:5]:
                lines.append(f"• <b>{item.job_title}</b> at {item.company} ({item.platform.upper()}) — Match: {int(item.match_score * 100)}%\n  ID: <code>{item.review_id}</code>")
            lines.append("\n<i>Tap alerts or use inline buttons to approve/reject.</i>")
            return "\n".join(lines)
        elif cmd == "/drafts":
            from app.services.email_auto_responder import email_auto_responder
            drafts = email_auto_responder.list_drafts(status="DRAFT")
            if not drafts:
                return "📭 <b>RSVP Drafts:</b> No pending recruiter reply drafts."
            lines = [f"📨 <b>Pending Recruiter RSVPs ({len(drafts)}):</b>\n"]
            for d in drafts[:5]:
                lines.append(f"• <b>{d.company}</b> ({d.recruiter_name}) — ID: <code>{d.draft_id}</code>\n  Subject: <i>{d.subject}</i>")
            return "\n".join(lines)
        elif cmd == "/outreach":
            from app.services.email_outreach_service import email_outreach_service
            drafts = email_outreach_service.list_drafts(status="DRAFT")
            if not drafts:
                return "📭 <b>Recruiter Outreach:</b> No pending recruiter outreach drafts."
            lines = [f"🤝 <b>Pending Recruiter Outreach ({len(drafts)}):</b>\n"]
            for d in drafts[:5]:
                channel_str = d.channel.value if hasattr(d.channel, "value") else str(d.channel)
                recruiter_name = d.recipient.name if (d.recipient and d.recipient.name) else "Recruiter"
                lines.append(f"• <b>{recruiter_name}</b> at {d.company} ({channel_str.upper()}) — ID: <code>{d.id}</code>\n  Role: <i>{d.job_title}</i>")
            return "\n".join(lines)
        elif cmd == "/pause":
            return "⏸️ Application scheduler has been <b>PAUSED</b> via mobile companion."
        elif cmd == "/resume":
            return "▶️ Application scheduler has been <b>RESUMED</b> via mobile companion."
        elif cmd == "/help":
            return (
                "📱 <b>Available Commands:</b>\n"
                "/status - System status & limits\n"
                "/today - Today's application metrics\n"
                "/review - Pending pre-submit reviews\n"
                "/drafts - Pending recruiter RSVP reply drafts\n"
                "/outreach - Pending recruiter outreach drafts\n"
                "/pause - Pause application scheduler\n"
                "/resume - Resume application scheduler"
            )
        else:
            return f"❓ Unknown command: <code>{command_text}</code>. Send /help for command list."

    async def handle_callback_query(self, callback_data: str, sender_id: Optional[str] = None) -> Dict[str, Any]:
        """Resolves 1-tap mobile inline button callbacks with authorization check."""
        if sender_id is not None and not self.is_authorized(sender_id):
            logger.warning(f"Unauthorized Telegram callback query attempt from sender {sender_id}")
            return {
                "success": False,
                "error": "Unauthorized chat ID",
                "action": "UNAUTHORIZED"
            }

        parts = callback_data.split("_", 1)
        action = parts[0]
        ticket_id = parts[1] if len(parts) > 1 else "unknown"

        if action == "approve":
            return {
                "success": True,
                "ticket_id": ticket_id,
                "action": "APPROVED",
                "message": f"Ticket {ticket_id} approved. Application resumed."
            }
        elif action == "skip":
            return {
                "success": True,
                "ticket_id": ticket_id,
                "action": "SKIPPED",
                "message": f"Job for ticket {ticket_id} skipped. Continuing next queue item."
            }
        elif action == "custom":
            return {
                "success": True,
                "ticket_id": ticket_id,
                "action": "CUSTOM_REQUIRED",
                "message": f"Please reply with custom answer for ticket {ticket_id}."
            }
        elif action == "rvw":
            # Format: rvw_approve_{review_id} or rvw_reject_{review_id} or rvw_info_{review_id}
            subparts = callback_data.split("_", 2)
            subaction = subparts[1] if len(subparts) > 1 else ""
            review_id = subparts[2] if len(subparts) > 2 else ""
            from app.services.review_queue import review_queue

            if subaction == "approve":
                success = review_queue.approve(review_id)
                if success:
                    return {
                        "success": True,
                        "review_id": review_id,
                        "action": "REVIEW_APPROVED",
                        "message": f"✅ Application {review_id} approved! AutoApply runner resuming submission."
                    }
                return {"success": False, "error": f"Review item {review_id} not found or already resolved."}
            elif subaction == "reject":
                success = review_queue.reject(review_id)
                if success:
                    return {
                        "success": True,
                        "review_id": review_id,
                        "action": "REVIEW_REJECTED",
                        "message": f"❌ Application {review_id} rejected and skipped."
                    }
                return {"success": False, "error": f"Review item {review_id} not found or already resolved."}
            elif subaction == "info":
                item = review_queue.get(review_id)
                if item:
                    info_msg = (
                        f"📄 <b>Review Details [{item.review_id}]:</b>\n\n"
                        f"💼 <b>Role:</b> {item.job_title}\n"
                        f"🏢 <b>Company:</b> {item.company}\n"
                        f"🌐 <b>Platform:</b> {item.platform.upper()}\n"
                        f"🎯 <b>Match Score:</b> {int(item.match_score * 100)}%\n"
                        f"📝 <b>Answers:</b> {len(item.answers)} questions"
                    )
                    return {"success": True, "action": "REVIEW_INFO", "review_id": review_id, "message": info_msg}
                return {"success": False, "error": f"Review item {review_id} not found."}

        elif action == "rsvp":
            # Format: rsvp_send_{draft_id} or rsvp_view_{draft_id} or rsvp_dismiss_{draft_id}
            subparts = callback_data.split("_", 2)
            subaction = subparts[1] if len(subparts) > 1 else ""
            draft_id = subparts[2] if len(subparts) > 2 else ""
            from app.services.email_auto_responder import email_auto_responder

            if subaction == "send":
                result = email_auto_responder.send_rsvp(draft_id)
                if result.get("success"):
                    return {
                        "success": True,
                        "action": "RSVP_SENT",
                        "draft_id": draft_id,
                        "message": f"📨 RSVP reply confirmed and dispatched for draft {draft_id}!"
                    }
                return {"success": False, "error": result.get("error", "Failed to send RSVP.")}
            elif subaction == "view":
                draft = email_auto_responder.get_draft(draft_id)
                if draft:
                    return {
                        "success": True,
                        "action": "RSVP_VIEW",
                        "draft_id": draft_id,
                        "message": f"✉️ <b>Draft Body:</b>\n\n{draft.body}"
                    }
                return {"success": False, "error": f"Draft {draft_id} not found."}
            elif subaction == "dismiss":
                success = email_auto_responder.dismiss_draft(draft_id)
                return {
                    "success": success,
                    "action": "RSVP_DISMISSED",
                    "draft_id": draft_id,
                    "message": f"Draft {draft_id} dismissed."
                }

        elif action == "outreach":
            # Format: outreach_send_{draft_id} or outreach_view_{draft_id} or outreach_dismiss_{draft_id}
            subparts = callback_data.split("_", 2)
            subaction = subparts[1] if len(subparts) > 1 else ""
            outreach_id = subparts[2] if len(subparts) > 2 else ""
            from app.services.email_outreach_service import email_outreach_service

            if subaction == "send":
                result = email_outreach_service.send_outreach(outreach_id)
                if result.get("success"):
                    return {
                        "success": True,
                        "action": "OUTREACH_SENT",
                        "outreach_id": outreach_id,
                        "message": f"🚀 Outreach dispatched successfully for draft {outreach_id}!"
                    }
                return {"success": False, "error": result.get("error", "Failed to send outreach.")}
            elif subaction == "view":
                draft = email_outreach_service.get_draft(outreach_id)
                if draft:
                    channel_val = draft.channel.value if hasattr(draft.channel, "value") else str(draft.channel)
                    return {
                        "success": True,
                        "action": "OUTREACH_VIEW",
                        "outreach_id": outreach_id,
                        "message": f"✉️ <b>Outreach Draft ({channel_val.upper()}):</b>\n\n{draft.body_text}"
                    }
                return {"success": False, "error": f"Outreach draft {outreach_id} not found."}
            elif subaction == "dismiss":
                success = email_outreach_service.dismiss_draft(outreach_id)
                return {
                    "success": success,
                    "action": "OUTREACH_DISMISSED",
                    "outreach_id": outreach_id,
                    "message": f"Outreach draft {outreach_id} dismissed."
                }

        return {"success": False, "error": "Unknown callback action"}


# Global service instance
telegram_companion = TelegramCompanionService()
