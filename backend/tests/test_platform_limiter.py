"""
Unit Tests for Phase 8: Platform Limiter & Telegram Security Guardrails.
"""

import pytest
from datetime import date, timedelta
from app.services.platform_limiter import PlatformLimiter, PlatformLimitStatus
from app.services.telegram_bot import TelegramCompanionService


def test_platform_limiter_defaults():
    limiter = PlatformLimiter()
    status = limiter.check_limit("LinkedIn")
    assert status.allowed is True
    assert status.daily_limit == 25
    assert status.current_count == 0
    assert status.remaining == 25


def test_platform_limiter_enforces_cap():
    limiter = PlatformLimiter(custom_limits={"linkedin": 2})
    limiter.record_application("LinkedIn")
    status1 = limiter.check_limit("LinkedIn")
    assert status1.allowed is True
    assert status1.current_count == 1
    assert status1.remaining == 1

    limiter.record_application("LinkedIn")
    status2 = limiter.check_limit("LinkedIn")
    assert status2.allowed is False
    assert status2.current_count == 2
    assert status2.remaining == 0
    assert "Daily quota" in status2.reason


def test_platform_limiter_date_rollover():
    limiter = PlatformLimiter(custom_limits={"indeed": 5})
    limiter.record_application("indeed")
    limiter.record_application("indeed")
    assert limiter.counts["indeed"] == 2

    # Simulate rollover to yesterday/tomorrow
    limiter.active_date = date.today() - timedelta(days=1)
    status = limiter.check_limit("indeed")
    assert status.allowed is True
    assert status.current_count == 0
    assert limiter.counts.get("indeed", 0) == 0


def test_platform_limiter_jitter():
    limiter = PlatformLimiter()
    delay = limiter.calculate_jitter_delay("naukri")
    # Base is 45, jitter 10-30 -> 55 to 75
    assert 55.0 <= delay <= 75.0


@pytest.mark.asyncio
async def test_telegram_security_authorization():
    # Service configured with a specific chat ID
    service = TelegramCompanionService(bot_token="test_bot_token", chat_id="12345678")

    # Authorized sender
    cmd_resp = await service.handle_command("/status", sender_id="12345678")
    assert "Active & Monitoring" in cmd_resp

    # Unauthorized sender
    unauth_resp = await service.handle_command("/status", sender_id="99999999")
    assert "Unauthorized" in unauth_resp

    # Authorized callback query
    cb_auth = await service.handle_callback_query("approve_ticket_123", sender_id="12345678")
    assert cb_auth["success"] is True
    assert cb_auth["action"] == "APPROVED"

    # Unauthorized callback query
    cb_unauth = await service.handle_callback_query("approve_ticket_123", sender_id="hacker_999")
    assert cb_unauth["success"] is False
    assert cb_unauth["action"] == "UNAUTHORIZED"
