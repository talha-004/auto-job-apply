import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from pathlib import Path
from app.models.job import (
    OutreachMessage,
    OutreachChannel,
    OutreachStatus,
    RecruiterContact,
    ResumeProfile,
    QAVault
)
from app.services.email_outreach_service import EmailOutreachService
from app.services.telegram_bot import TelegramCompanionService


@pytest.fixture
def mock_profile():
    return ResumeProfile(
        full_name="Alex Mercer",
        email="alex.mercer@example.com",
        phone="+1234567890",
        skills=["Python", "FastAPI", "React", "Docker", "PostgreSQL"],
        years_of_experience=5.0,
        linkedin_url="https://linkedin.com/in/alexmercer",
        qa_vault=QAVault(notice_period="Immediate")
    )


@pytest.mark.asyncio
async def test_draft_linkedin_connection_note(tmp_path, mock_profile):
    service = EmailOutreachService()
    service.outreach_dir = tmp_path

    recipient = RecruiterContact(
        name="Sarah Jenkins",
        email="sarah.jenkins@techcorp.com",
        company="TechCorp"
    )

    draft = await service.draft_outreach(
        job_id="job-101",
        job_title="Senior Python Engineer",
        company="TechCorp",
        recipient=recipient,
        candidate_profile=mock_profile,
        channel=OutreachChannel.LINKEDIN_MESSAGE
    )

    assert draft.channel == OutreachChannel.LINKEDIN_MESSAGE
    assert draft.status == OutreachStatus.DRAFTED
    assert "Sarah Jenkins" in draft.body_text
    assert "Senior Python Engineer" in draft.body_text
    assert "TechCorp" in draft.body_text
    # Must adhere to LinkedIn 300 character invitation limit
    assert len(draft.body_text) <= 300


@pytest.mark.asyncio
async def test_trigger_post_application_outreach_flow(tmp_path, mock_profile):
    service = EmailOutreachService()
    service.outreach_dir = tmp_path

    # Mock candidate profile loader
    with patch("app.services.resume_parser.resume_parser_service.load_profile", return_value=mock_profile), \
         patch("app.services.recruiter_discovery.recruiter_discovery.discover_leads_for_company") as mock_discover, \
         patch("app.services.telegram_bot.telegram_companion.send_message", new_callable=AsyncMock) as mock_tg_send:

        lead_mock = MagicMock()
        lead_mock.name = "John Doe"
        lead_mock.email = "john@acme.com"
        mock_discover.return_value = [lead_mock]

        draft = await service.trigger_post_application_outreach(
            job_id="job-202",
            job_title="Cloud Architect",
            company="Acme Corp"
        )

        assert draft is not None
        assert draft.recipient.name == "John Doe"
        assert draft.job_title == "Cloud Architect"
        assert draft.company == "Acme Corp"
        assert mock_tg_send.called

        # Inspect Telegram payload
        call_args = mock_tg_send.call_args[0]
        alert_text = call_args[0]
        reply_markup = mock_tg_send.call_args[1].get("reply_markup", {})
        assert "Recruiter Outreach Drafted" in alert_text
        assert "Cloud Architect" in alert_text

        inline_keyboard = reply_markup.get("inline_keyboard", [])
        button_callbacks = [btn["callback_data"] for row in inline_keyboard for btn in row]
        assert f"outreach_send_{draft.id}" in button_callbacks
        assert f"outreach_view_{draft.id}" in button_callbacks
        assert f"outreach_dismiss_{draft.id}" in button_callbacks


@pytest.mark.asyncio
async def test_telegram_outreach_callbacks_and_commands(tmp_path, mock_profile):
    service = EmailOutreachService()
    service.outreach_dir = tmp_path

    recipient = RecruiterContact(name="Elena Rostova", email="elena@meta.com", company="Meta")
    draft = await service.draft_outreach(
        job_id="job-303",
        job_title="Full Stack Developer",
        company="Meta",
        recipient=recipient,
        candidate_profile=mock_profile,
        channel=OutreachChannel.LINKEDIN_MESSAGE
    )

    tg = TelegramCompanionService()

    with patch("app.services.email_outreach_service.email_outreach_service", service):
        # 1. Test /outreach command
        outreach_cmd_res = await tg.handle_command("/outreach")
        assert "Pending Recruiter Outreach" in outreach_cmd_res
        assert "Elena Rostova" in outreach_cmd_res
        assert "Meta" in outreach_cmd_res

        # 2. Test view callback
        view_res = await tg.handle_callback_query(f"outreach_view_{draft.id}")
        assert view_res["success"] is True
        assert view_res["action"] == "OUTREACH_VIEW"
        assert "Elena Rostova" in view_res["message"]

        # 3. Test send callback
        send_res = await tg.handle_callback_query(f"outreach_send_{draft.id}")
        assert send_res["success"] is True
        assert send_res["action"] == "OUTREACH_SENT"

        # Check status updated on disk
        updated_draft = service.get_draft(draft.id)
        assert updated_draft.status == OutreachStatus.SENT

        # 4. Test dismiss callback on new draft
        draft2 = await service.draft_outreach(
            job_id="job-304",
            job_title="Data Engineer",
            company="Netflix",
            recipient=recipient,
            candidate_profile=mock_profile,
            channel=OutreachChannel.LINKEDIN_MESSAGE
        )
        dismiss_res = await tg.handle_callback_query(f"outreach_dismiss_{draft2.id}")
        assert dismiss_res["success"] is True
        assert dismiss_res["action"] == "OUTREACH_DISMISSED"

        updated_draft2 = service.get_draft(draft2.id)
        assert updated_draft2.status == OutreachStatus.FAILED
