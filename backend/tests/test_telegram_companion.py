"""
Unit Tests for Phase 20: Mobile Quick-Action Companion (Telegram Bot).
Validates loopback mock simulation, alert formatting, inline keyboard generation,
remote slash commands, and webhook updates.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.telegram_bot import TelegramCompanionService, telegram_companion


@pytest.fixture
def client():
    return TestClient(app)


def test_telegram_companion_initial_mode():
    service = TelegramCompanionService(bot_token=None, chat_id=None)
    assert service.is_live is False
    assert len(service.simulated_dispatches) == 0


def test_format_intervention_alert():
    service = TelegramCompanionService()
    alert = service.format_intervention_alert(
        ticket_id="ticket_456",
        job_title="Senior Python Engineer",
        company="Datadog",
        question_text="Do you have experience with Kubernetes in production?",
        default_answer="Yes, 3+ years"
    )

    assert "Senior Python Engineer" in alert["text"]
    assert "Datadog" in alert["text"]
    assert "Kubernetes in production" in alert["text"]
    assert "Yes, 3+ years" in alert["text"]

    keyboard = alert["reply_markup"]["inline_keyboard"]
    assert len(keyboard) == 2
    assert keyboard[0][0]["callback_data"] == "approve_ticket_456"
    assert keyboard[0][1]["callback_data"] == "skip_ticket_456"
    assert keyboard[1][0]["callback_data"] == "custom_ticket_456"


@pytest.mark.asyncio
async def test_send_message_in_mock_mode():
    service = TelegramCompanionService(bot_token=None, chat_id=None)
    res = await service.send_message("Test mobile notification message")

    assert res["ok"] is True
    assert res["mode"] == "simulated"
    assert len(service.simulated_dispatches) == 1
    assert "Test mobile notification message" in service.simulated_dispatches[0]["text"]


@pytest.mark.asyncio
async def test_slash_command_processing():
    service = TelegramCompanionService()
    status_reply = await service.handle_command("/status")
    assert "Active & Monitoring" in status_reply

    today_reply = await service.handle_command("/today")
    assert "Today's Summary" in today_reply

    pause_reply = await service.handle_command("/pause")
    assert "PAUSED" in pause_reply

    resume_reply = await service.handle_command("/resume")
    assert "RESUMED" in resume_reply

    unknown_reply = await service.handle_command("/foobar")
    assert "Unknown command" in unknown_reply


@pytest.mark.asyncio
async def test_callback_query_actions():
    service = TelegramCompanionService()
    res_approve = await service.handle_callback_query("approve_ticket_789")
    assert res_approve["success"] is True
    assert res_approve["action"] == "APPROVED"
    assert res_approve["ticket_id"] == "ticket_789"

    res_skip = await service.handle_callback_query("skip_ticket_789")
    assert res_skip["success"] is True
    assert res_skip["action"] == "SKIPPED"


def test_mobile_companion_endpoints(client: TestClient):
    # Status endpoint
    status_resp = client.get("/api/mobile/status")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert "mode" in data

    # Command endpoint
    cmd_resp = client.post("/api/mobile/command", json={"command": "/status"})
    assert cmd_resp.status_code == 200
    assert "reply" in cmd_resp.json()

    # Simulate alert endpoint
    sim_resp = client.post(
        "/api/mobile/simulate-alert",
        json={
            "ticket_id": "test_endpoint_1",
            "job_title": "Backend Lead",
            "company": "Figma",
            "question_text": "Are you comfortable working in PST hours?",
            "default_answer": "Yes"
        }
    )
    assert sim_resp.status_code == 200
    assert sim_resp.json()["success"] is True

    # Webhook endpoint with callback query
    webhook_resp = client.post(
        "/api/mobile/telegram/webhook",
        json={"callback_query": {"data": "approve_test_endpoint_1"}}
    )
    assert webhook_resp.status_code == 200
    assert webhook_resp.json()["ok"] is True
    assert webhook_resp.json()["action_result"]["action"] == "APPROVED"


def test_format_review_alert():
    service = TelegramCompanionService()
    alert = service.format_review_alert(
        review_id="rvw_123",
        job_title="Staff AI Engineer",
        company="Anthropic",
        platform="linkedin",
        match_score=0.92,
        answers_count=3
    )

    assert "Staff AI Engineer" in alert["text"]
    assert "Anthropic" in alert["text"]
    assert "92%" in alert["text"]
    assert "3" in alert["text"]

    keyboard = alert["reply_markup"]["inline_keyboard"]
    assert len(keyboard) == 2
    assert keyboard[0][0]["callback_data"] == "rvw_approve_rvw_123"
    assert keyboard[0][1]["callback_data"] == "rvw_reject_rvw_123"
    assert keyboard[1][0]["callback_data"] == "rvw_info_rvw_123"


@pytest.mark.asyncio
async def test_review_queue_telegram_actions():
    from app.services.review_queue import review_queue
    review_queue.clear()

    item = review_queue.enqueue(
        job_title="ML Infra Lead",
        company="Cohere",
        platform="greenhouse",
        job_url="https://jobs.cohere.com/1",
        match_score=0.88,
        answers=[{"q": "Years of experience?", "a": "6"}]
    )

    service = TelegramCompanionService()

    # Test /review command
    cmd_reply = await service.handle_command("/review")
    assert "ML Infra Lead" in cmd_reply
    assert "Cohere" in cmd_reply
    assert item.review_id in cmd_reply

    # Test rvw_info callback
    info_res = await service.handle_callback_query(f"rvw_info_{item.review_id}")
    assert info_res["success"] is True
    assert info_res["action"] == "REVIEW_INFO"
    assert "ML Infra Lead" in info_res["message"]

    # Test rvw_approve callback
    appr_res = await service.handle_callback_query(f"rvw_approve_{item.review_id}")
    assert appr_res["success"] is True
    assert appr_res["action"] == "REVIEW_APPROVED"
    assert item.status == "APPROVED"


@pytest.mark.asyncio
async def test_rsvp_telegram_actions():
    from app.services.email_auto_responder import email_auto_responder
    email_auto_responder.clear()

    draft = await email_auto_responder.generate_rsvp_draft(
        email_id="tg_test_email",
        sender="Elena Rostova <elena@palantir.com>",
        company="Palantir",
        role="Forward Deployed Engineer"
    )

    service = TelegramCompanionService()

    # Test /drafts command
    drafts_reply = await service.handle_command("/drafts")
    assert "Palantir" in drafts_reply
    assert draft.draft_id in drafts_reply

    # Test rsvp_view callback
    view_res = await service.handle_callback_query(f"rsvp_view_{draft.draft_id}")
    assert view_res["success"] is True
    assert view_res["action"] == "RSVP_VIEW"
    assert "Palantir" in view_res["message"]

    # Test rsvp_send callback
    send_res = await service.handle_callback_query(f"rsvp_send_{draft.draft_id}")
    assert send_res["success"] is True
    assert send_res["action"] == "RSVP_SENT"
    assert draft.status == "SENT"

