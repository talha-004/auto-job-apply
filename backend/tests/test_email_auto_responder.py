"""
Unit Tests for Recruiter Email Auto-Responder & Calendar RSVP Generator.
Validates draft generation, personalization, recruiter name extraction,
Telegram push alerts, manual/1-tap approvals, and REST API management endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.email_auto_responder import email_auto_responder
from app.services.interview_service import interview_pipeline_service
from app.services.email_sync import email_sync_service


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    email_auto_responder.clear()
    yield
    email_auto_responder.clear()


@pytest.mark.asyncio
async def test_generate_rsvp_draft_with_action_link():
    draft = await email_auto_responder.generate_rsvp_draft(
        email_id="email_101",
        sender="Alice Walker <alice.walker@stripe.com>",
        company="Stripe",
        role="Senior Infrastructure Engineer",
        action_link="https://calendly.com/alice-stripe/30min"
    )

    assert draft.status == "DRAFT"
    assert draft.recruiter_name == "Alice"
    assert draft.company == "Stripe"
    assert "https://calendly.com/alice-stripe/30min" in draft.body
    assert "Senior Infrastructure Engineer" in draft.subject
    assert email_auto_responder.get_draft(draft.draft_id) is not None


@pytest.mark.asyncio
async def test_generate_rsvp_draft_with_interview_time():
    draft = await email_auto_responder.generate_rsvp_draft(
        email_id="email_102",
        sender="recruiter@figma.com",
        company="Figma",
        role="Full Stack Engineer",
        interview_time="Thursday at 3:00 PM EST"
    )

    assert draft.recruiter_name == "Recruiter"
    assert "Thursday at 3:00 PM EST" in draft.body
    assert "Figma" in draft.subject


@pytest.mark.asyncio
async def test_generate_rsvp_draft_generic_availability():
    draft = await email_auto_responder.generate_rsvp_draft(
        email_id="email_103",
        sender="Bob Vance <bob@vancerefrigeration.com>",
        company="Vance",
        role="DevOps Engineer"
    )

    assert len(draft.suggested_slots) == 3
    assert "Tomorrow between 2:00 PM" in draft.body
    assert draft.recruiter_name == "Bob"


@pytest.mark.asyncio
async def test_send_and_dismiss_rsvp():
    # Set up interview pipeline record
    app_rec = interview_pipeline_service.get_or_create(
        application_id="app_test_rsvp_1",
        company="Netflix",
        job_title="Software Architect"
    )

    draft = await email_auto_responder.generate_rsvp_draft(
        email_id="email_104",
        sender="David Fincher <david@netflix.com>",
        company="Netflix",
        role="Software Architect",
        application_id="app_test_rsvp_1"
    )

    send_res = email_auto_responder.send_rsvp(draft.draft_id)
    assert send_res["success"] is True
    assert draft.status == "SENT"
    assert draft.sent_at is not None
    assert len(email_auto_responder.sent_dispatches) == 1

    # Check that interview notes were updated
    assert "[RSVP Sent]" in app_rec.notes

    # Dismiss test
    draft2 = await email_auto_responder.generate_rsvp_draft(
        email_id="email_105",
        sender="recruiter@uber.com",
        company="Uber"
    )
    dismiss_res = email_auto_responder.dismiss_draft(draft2.draft_id)
    assert dismiss_res is True
    assert draft2.status == "DISMISSED"


@pytest.mark.asyncio
async def test_email_sync_automatically_creates_rsvp_draft():
    # Simulate inbound interview invitation
    rec = await email_sync_service.ingest_and_process_email(
        sender="Sarah Connor <sarah@cyberdyne.com>",
        subject="Interview Invitation for Systems Engineer at Cyberdyne",
        body="Hi Syed, we loved your profile. Are you free to speak tomorrow at 2:00 PM EST?"
    )

    from app.services.inbox_monitor import RecruiterEmailIntent
    assert rec.intent == RecruiterEmailIntent.INTERVIEW_INVITATION
    drafts = email_auto_responder.list_drafts()
    assert len(drafts) >= 1
    matching = [d for d in drafts if d.company == "Cyberdyne"]
    assert len(matching) == 1
    assert matching[0].recruiter_name == "Sarah"


def test_rsvp_api_endpoints(client: TestClient):
    # Manually create a draft for testing
    import asyncio
    draft = asyncio.run(email_auto_responder.generate_rsvp_draft(
        email_id="api_test_email",
        sender="Marcus Aurelius <marcus@rome.com>",
        company="Rome",
        role="Platform Engineer"
    ))

    # GET /api/email/rsvp-drafts
    list_resp = client.get("/api/email/rsvp-drafts")
    assert list_resp.status_code == 200
    assert len(list_resp.json()) >= 1

    # GET /api/email/rsvp-drafts/{draft_id}
    detail_resp = client.get(f"/api/email/rsvp-drafts/{draft.draft_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["company"] == "Rome"

    # POST /api/email/rsvp-drafts/{draft_id}/edit
    edit_resp = client.post(
        f"/api/email/rsvp-drafts/{draft.draft_id}/edit",
        json={"body": "Updated body text for Marcus.", "subject": "Updated Subject"}
    )
    assert edit_resp.status_code == 200
    assert edit_resp.json()["body"] == "Updated body text for Marcus."

    # POST /api/email/rsvp-drafts/{draft_id}/send
    send_resp = client.post(f"/api/email/rsvp-drafts/{draft.draft_id}/send")
    assert send_resp.status_code == 200
    assert send_resp.json()["success"] is True

    # Confirm status is now SENT
    assert draft.status == "SENT"
