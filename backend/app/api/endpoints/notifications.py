from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.config import settings
from app.services.notification_service import (
    notification_service,
    NotificationEventType,
    NotificationDispatchResult
)
from app.services.inbox_monitor import (
    inbox_monitor_service,
    EmailClassificationResult
)

router = APIRouter()


class TestNotificationRequest(BaseModel):
    event_type: NotificationEventType = NotificationEventType.SYSTEM_ALERT
    title: str = "Test Notification from AutoApplyJobs"
    message: str = "This is a verification test of your alert notification system."


class EmailClassifyRequest(BaseModel):
    sender: str = "recruiter@techcorp.com"
    subject: str = "Invitation to interview for Senior Software Engineer"
    body_text: str = Field(..., min_length=5)


@router.get("/config")
async def get_notification_config() -> Dict[str, Any]:
    """Retrieve active status of all notification channels and IMAP monitor."""
    return {
        "desktop_enabled": settings.ENABLE_DESKTOP_NOTIFICATIONS,
        "webhook_enabled": settings.ENABLE_WEBHOOK_NOTIFICATIONS,
        "webhook_configured": bool(settings.WEBHOOK_URL),
        "email_alerts_configured": bool(settings.NOTIFICATION_EMAIL and settings.SMTP_HOST),
        "inbox_monitor_enabled": settings.INBOX_MONITOR_ENABLED,
        "inbox_monitor_configured": bool(settings.IMAP_HOST and settings.IMAP_USER)
    }


@router.post("/test", response_model=NotificationDispatchResult)
async def send_test_notification(req: TestNotificationRequest) -> NotificationDispatchResult:
    """Send an immediate test alert across all enabled channels."""
    return await notification_service.notify(
        event_type=req.event_type,
        title=req.title,
        message=req.message,
        details={"test_dispatch": True}
    )


@router.post("/classify-email", response_model=EmailClassificationResult)
async def classify_recruiter_email(req: EmailClassifyRequest) -> EmailClassificationResult:
    """Analyze email content to identify interview invitations, assessments, or rejections."""
    result = await inbox_monitor_service.classify_email_content(
        sender=req.sender,
        subject=req.subject,
        body_text=req.body_text
    )
    # Process notifications if actionable
    await inbox_monitor_service.process_classified_email(result, req.sender, req.subject)
    return result


@router.post("/scan-inbox", response_model=List[EmailClassificationResult])
async def trigger_inbox_scan(max_emails: int = 10) -> List[EmailClassificationResult]:
    """Scan configured IMAP mailbox for unread recruiter messages and trigger alerts."""
    return await inbox_monitor_service.scan_inbox(max_emails=max_emails)
