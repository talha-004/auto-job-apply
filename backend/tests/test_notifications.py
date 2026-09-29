import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.notification_service import (
    NotificationService,
    NotificationEventType,
    NotificationPayload,
    notification_service
)
from app.services.inbox_monitor import (
    InboxMonitorService,
    RecruiterEmailIntent,
    EmailClassificationResult,
    inbox_monitor_service
)

client = TestClient(app)


def test_notification_event_types():
    """Verify all critical notification event types are supported."""
    assert NotificationEventType.APPLICATION_SUBMITTED == "APPLICATION_SUBMITTED"
    assert NotificationEventType.INTERVIEW_INVITATION == "INTERVIEW_INVITATION"
    assert NotificationEventType.ASSESSMENT_REQUEST == "ASSESSMENT_REQUEST"
    assert NotificationEventType.HUMAN_INTERVENTION_REQUIRED == "HUMAN_INTERVENTION_REQUIRED"
    assert NotificationEventType.DAILY_CAP_REACHED == "DAILY_CAP_REACHED"
    assert NotificationEventType.SESSION_EXPIRED == "SESSION_EXPIRED"
    assert NotificationEventType.SYSTEM_ALERT == "SYSTEM_ALERT"


@pytest.mark.asyncio
async def test_notification_service_websocket_dispatch():
    """Verify notification service emits to websocket broadcaster."""
    svc = NotificationService()
    svc.enable_desktop = False
    svc.enable_webhook = False
    svc.notification_email = ""

    with patch("app.services.notification_service.broadcaster.emit_log", new_callable=AsyncMock) as mock_broadcast:
        res = await svc.notify(
            event_type=NotificationEventType.APPLICATION_SUBMITTED,
            title="Application Sent",
            message="Successfully applied to Google",
            details={"company": "Google", "job_title": "Staff Engineer"}
        )

        assert res.success is True
        assert "websocket" in res.channels_dispatched
        mock_broadcast.assert_called_once()


@pytest.mark.asyncio
async def test_notification_service_webhook_dispatch():
    """Verify webhook payload formatting and delivery."""
    svc = NotificationService()
    svc.enable_desktop = False
    svc.enable_webhook = True
    svc.webhook_url = "https://discord.com/api/webhooks/mock/test"
    svc.notification_email = ""

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        res = await svc.notify(
            event_type=NotificationEventType.INTERVIEW_INVITATION,
            title="Interview Requested!",
            message="Recruiter wants to schedule an interview",
            details={"company": "Meta", "link": "https://calendly.com/recruiter/30min"}
        )

        assert res.success is True
        assert "webhook" in res.channels_dispatched
        mock_post.assert_called_once()


@pytest.mark.asyncio
async def test_inbox_monitor_classify_interview_invitation():
    """Verify deterministic detection of interview invitations and meeting links."""
    body = (
        "Hi Candidate,\n\n"
        "We reviewed your resume and were impressed by your profile. "
        "We would love to schedule a 30-minute phone screen with our engineering lead. "
        "Please select a time slot here: https://calendly.com/techcorp-recruiting/intro\n\n"
        "Best regards,\nTechCorp Recruiting"
    )

    result = await inbox_monitor_service.classify_email_content(
        sender="jobs@techcorp.com",
        subject="Interview Invitation - Senior Software Engineer",
        body_text=body
    )

    assert result.intent == RecruiterEmailIntent.INTERVIEW_INVITATION
    assert result.confidence >= 0.9
    assert result.action_link == "https://calendly.com/techcorp-recruiting/intro"
    assert "interview" in result.suggested_action.lower()


@pytest.mark.asyncio
async def test_inbox_monitor_classify_online_assessment():
    """Verify deterministic detection of technical assessments."""
    body = (
        "Dear Candidate,\n\n"
        "Thank you for your interest in the Backend Architect role. "
        "As the next step, please complete this 70-minute coding challenge on HackerRank:\n"
        "https://hackerrank.com/tests/take/backend-eval-2026\n\n"
        "You have 48 hours to complete it."
    )

    result = await inbox_monitor_service.classify_email_content(
        sender="talent@fintech.io",
        subject="Fintech Online Technical Assessment",
        body_text=body
    )

    assert result.intent == RecruiterEmailIntent.ONLINE_ASSESSMENT
    assert result.confidence >= 0.9
    assert "hackerrank.com" in result.action_link
    assert "deadline" in result.suggested_action.lower()


@pytest.mark.asyncio
async def test_inbox_monitor_classify_rejection():
    """Verify detection of rejection and non-selection notices."""
    body = (
        "Dear Applicant,\n\n"
        "Thank you for taking the time to speak with us about the position. "
        "Unfortunately, after careful consideration, we have decided not to proceed "
        "with your application at this time as we are pursuing other candidates whose "
        "backgrounds align more closely with our needs.\n\n"
        "We wish you the best in your job search."
    )

    result = await inbox_monitor_service.classify_email_content(
        sender="no-reply@enterprise.com",
        subject="Update on your application",
        body_text=body
    )

    assert result.intent == RecruiterEmailIntent.REJECTION
    assert result.confidence >= 0.85
    assert "Archive" in result.suggested_action


@pytest.mark.asyncio
async def test_inbox_monitor_classify_application_received():
    """Verify detection of application submission acknowledgements."""
    body = (
        "Hello,\n\n"
        "Thank you for applying to the Lead Developer role at StartupX. "
        "We have received your resume and application materials. "
        "Our hiring team will review your qualifications and reach out if there is a match."
    )

    result = await inbox_monitor_service.classify_email_content(
        sender="careers@startupx.com",
        subject="We received your application at StartupX",
        body_text=body
    )

    assert result.intent == RecruiterEmailIntent.APPLICATION_RECEIVED
    assert result.confidence >= 0.9


def test_api_get_notification_config():
    """Verify GET /api/notifications/config returns current system settings."""
    resp = client.get("/api/notifications/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "desktop_enabled" in data
    assert "webhook_enabled" in data
    assert "inbox_monitor_enabled" in data


def test_api_send_test_notification():
    """Verify POST /api/notifications/test dispatches alert."""
    payload = {
        "event_type": "SYSTEM_ALERT",
        "title": "Automated Unit Test Alert",
        "message": "Testing notification pipeline integrity"
    }
    resp = client.post("/api/notifications/test", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["event_type"] == "SYSTEM_ALERT"
    assert "websocket" in data["channels_dispatched"]


def test_api_classify_email_endpoint():
    """Verify POST /api/notifications/classify-email parses recruiter emails."""
    payload = {
        "sender": "recruiter@bigtech.com",
        "subject": "Interview Scheduling - AI Engineer",
        "body_text": "We would like to schedule a call with you. Please choose a slot: https://calendly.com/bigtech/interview"
    }
    resp = client.post("/api/notifications/classify-email", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["intent"] == "INTERVIEW_INVITATION"
    assert "calendly.com" in data["action_link"]
