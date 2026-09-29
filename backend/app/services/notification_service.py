"""
Enterprise Notification & Alert Dispatcher Service.
Supports Desktop notifications, Discord/Slack webhooks, SMTP email alerts, and WebSocket broadcasting.
"""

import sys
import subprocess
import httpx
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logger import logger, broadcaster, LogLevel


class NotificationEventType(str, Enum):
    APPLICATION_SUBMITTED = "APPLICATION_SUBMITTED"
    INTERVIEW_INVITATION = "INTERVIEW_INVITATION"
    ASSESSMENT_REQUEST = "ASSESSMENT_REQUEST"
    HUMAN_INTERVENTION_REQUIRED = "HUMAN_INTERVENTION_REQUIRED"
    DAILY_CAP_REACHED = "DAILY_CAP_REACHED"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    SYSTEM_ALERT = "SYSTEM_ALERT"


class NotificationPayload(BaseModel):
    event_type: NotificationEventType
    title: str
    message: str
    details: Dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class NotificationDispatchResult(BaseModel):
    success: bool
    event_type: NotificationEventType
    channels_dispatched: List[str] = Field(default_factory=list)
    errors: Dict[str, str] = Field(default_factory=dict)


class NotificationService:
    """Multi-channel notification dispatcher for autonomous application events."""

    def __init__(self):
        self.webhook_url = settings.WEBHOOK_URL
        self.enable_desktop = settings.ENABLE_DESKTOP_NOTIFICATIONS
        self.enable_webhook = settings.ENABLE_WEBHOOK_NOTIFICATIONS
        self.notification_email = settings.NOTIFICATION_EMAIL

    async def notify(
        self,
        event_type: NotificationEventType,
        title: str,
        message: str,
        details: Optional[Dict[str, Any]] = None
    ) -> NotificationDispatchResult:
        """Dispatch notification across all enabled channels."""
        payload = NotificationPayload(
            event_type=event_type,
            title=title,
            message=message,
            details=details or {}
        )

        channels: List[str] = []
        errors: Dict[str, str] = {}

        # 1. Live WebSocket Broadcaster
        try:
            log_level = LogLevel.SUCCESS if event_type in [
                NotificationEventType.APPLICATION_SUBMITTED,
                NotificationEventType.INTERVIEW_INVITATION
            ] else (
                LogLevel.WARNING if event_type in [
                    NotificationEventType.HUMAN_INTERVENTION_REQUIRED,
                    NotificationEventType.DAILY_CAP_REACHED
                ] else LogLevel.INFO
            )
            await broadcaster.emit_log(f"🔔 [{event_type.value}] {title}: {message}", level=log_level, details=payload.details)
            channels.append("websocket")
        except Exception as e:
            errors["websocket"] = str(e)

        # 2. Desktop Notification
        if self.enable_desktop:
            try:
                self._send_desktop_notification(title, message)
                channels.append("desktop")
            except Exception as e:
                errors["desktop"] = str(e)

        # 3. HTTP Webhook (Slack / Discord / Teams)
        if self.enable_webhook and self.webhook_url:
            try:
                await self._send_webhook_notification(payload)
                channels.append("webhook")
            except Exception as e:
                errors["webhook"] = str(e)

        # 4. Email Notification
        if self.notification_email and settings.SMTP_HOST:
            try:
                self._send_email_notification(payload)
                channels.append("email")
            except Exception as e:
                errors["email"] = str(e)

        return NotificationDispatchResult(
            success=len(channels) > 0,
            event_type=event_type,
            channels_dispatched=channels,
            errors=errors
        )

    def _send_desktop_notification(self, title: str, message: str):
        """Display cross-platform desktop toast notification."""
        clean_title = title.replace('"', "'")
        clean_msg = message.replace('"', "'")

        if sys.platform == "win32":
            # Windows PowerShell notification balloon/toast
            ps_script = f"""
            [reflection.assembly]::loadwithpartialname('System.Windows.Forms') | Out-Null
            $notify = New-Object System.Windows.Forms.NotifyIcon
            $notify.Icon = [System.Drawing.SystemIcons]::Information
            $notify.Visible = $true
            $notify.ShowBalloonTip(5000, "{clean_title}", "{clean_msg}", [System.Windows.Forms.ToolTipIcon]::Info)
            """
            try:
                subprocess.Popen(
                    ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
            except Exception as e:
                logger.debug(f"[Notification] Windows balloon toast error: {e}")
        else:
            logger.info(f"[Desktop Notification] {title}: {message}")

    async def _send_webhook_notification(self, payload: NotificationPayload):
        """Deliver rich webhook notification to Slack or Discord."""
        # Generic payload compatible with Discord and Slack webhooks
        body = {
            "text": f"*{payload.title}*\n{payload.message}",
            "content": f"🚨 **{payload.title}**\n{payload.message}",
            "embeds": [
                {
                    "title": payload.title,
                    "description": payload.message,
                    "color": 39149 if payload.event_type == NotificationEventType.INTERVIEW_INVITATION else 16753920,
                    "timestamp": payload.timestamp,
                    "fields": [
                        {"name": k, "value": str(v), "inline": True}
                        for k, v in list(payload.details.items())[:6]
                    ]
                }
            ]
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(self.webhook_url, json=body)
            if resp.status_code >= 400:
                raise RuntimeError(f"Webhook returned HTTP {resp.status_code}: {resp.text}")

    def _send_email_notification(self, payload: NotificationPayload):
        """Send notification alert email to candidate."""
        import smtplib
        from email.mime.text import MIMEText

        sender = settings.SENDER_EMAIL or settings.SMTP_USER
        if not sender:
            return

        msg = MIMEText(f"{payload.title}\n\n{payload.message}\n\nDetails:\n{payload.details}")
        msg["Subject"] = f"[AutoApply Alert] {payload.title}"
        msg["From"] = sender
        msg["To"] = self.notification_email

        if settings.DRY_RUN or not settings.SMTP_HOST:
            logger.info(f"[DRY_RUN] Notification email to {self.notification_email} simulated.")
            return

        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
        if settings.SMTP_USE_TLS:
            server.starttls()
        if settings.SMTP_USER and settings.SMTP_PASSWORD:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()


notification_service = NotificationService()
