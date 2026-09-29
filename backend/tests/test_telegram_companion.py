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
