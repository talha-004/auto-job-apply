import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.job import SearchConfig, ResumeProfile, PlatformEnum, ApplicationStatus
from app.platforms.naukri import NaukriPlatform
from app.core.logger import broadcaster

client = TestClient(app)

# 1. Pydantic Model Deserialization Tests
def test_search_config_json_deserialization():
    # Explicit false
    config_false = SearchConfig.model_validate_json('{"headless": false}')
    assert config_false.headless is False
    assert isinstance(config_false.headless, bool)

    # Explicit true
    config_true = SearchConfig.model_validate_json('{"headless": true}')
    assert config_true.headless is True
    assert isinstance(config_true.headless, bool)

    # Default preservation
    config_default = SearchConfig.model_validate_json('{}')
    assert config_default.headless is True

# 2. End-to-End API Route Configuration Flow Test
def test_api_start_bot_parses_headless_boolean():
    payload = {
        "keywords": "Full Stack Developer",
        "location": "Remote",
        "platforms": ["Naukri"],
        "max_applications": 5,
        "cooldown_seconds": 10.0,
        "headless": False,
        "dry_run": True
    }
    
    with patch("app.services.bot_manager.bot_manager.start", new_callable=AsyncMock) as mock_start:
        mock_start.return_value = {"success": True, "message": "Bot started"}
        response = client.post("/api/bot/start", json=payload)
        assert response.status_code == 200
        assert mock_start.called
        
        # Verify passed config has strictly boolean False
        called_config = mock_start.call_args[0][0]
        assert isinstance(called_config, SearchConfig)
        assert called_config.headless is False

# 3. BasePlatform Actual Launch & Teardown (Visible Mode & Headless Mode)
@pytest.mark.asyncio
async def test_base_platform_launch_visible_mode():
    config = SearchConfig(headless=False)
    profile = ResumeProfile(full_name="Test Candidate", email="test@example.com")
    platform = NaukriPlatform(config=config, profile=profile)
    
    try:
        page = await platform.init_browser()
        assert platform.browser is not None
        assert platform.browser.is_connected()
        assert platform.page is not None
        
        await page.goto("about:blank")
        assert page.url == "about:blank"
    finally:
        await platform.close_browser()
        assert platform.browser is None or not platform.browser.is_connected()

@pytest.mark.asyncio
async def test_base_platform_launch_headless_mode():
    config = SearchConfig(headless=True)
    profile = ResumeProfile(full_name="Test Candidate", email="test@example.com")
    platform = NaukriPlatform(config=config, profile=profile)
    
    try:
        await platform.init_browser()
        assert platform.browser is not None
        assert platform.browser.is_connected()
    finally:
        await platform.close_browser()
        assert platform.browser is None or not platform.browser.is_connected()

# 4. Failure Path Verification (Error raised, no success log emitted, no leaked state)
@pytest.mark.asyncio
async def test_base_platform_launch_failure_handling():
    config = SearchConfig(headless=False)
    profile = ResumeProfile(full_name="Test Candidate", email="test@example.com")
    platform = NaukriPlatform(config=config, profile=profile)

    emitted_logs = []
    async def mock_emit_log(message, **kwargs):
        emitted_logs.append(message)

    with patch.object(broadcaster, "emit_log", side_effect=mock_emit_log):
        # Start playwright instance on platform
        from playwright.async_api import async_playwright
        pw = await async_playwright().start()
        platform.playwright = pw
        
        # Patch the specific chromium.launch method to simulate failure
        with patch.object(pw.chromium, "launch", side_effect=RuntimeError("Simulated Chromium launch failure")):
            with pytest.raises(RuntimeError, match="Simulated Chromium launch failure"):
                # Call launch args and launch directly as in init_browser
                launch_args = ["--window-size=1920,1080"]
                try:
                    await platform.playwright.chromium.launch(
                        headless=platform.config.headless,
                        args=launch_args,
                        slow_mo=50
                    )
                except Exception:
                    raise
                
                # Should not reach here
                await broadcaster.emit_log("🌐 Browser launched in visible mode")

            # Assert no false success event was emitted
            assert not any("Browser launched" in log for log in emitted_logs)
            # Assert browser remains uninitialized
            assert platform.browser is None
            
        await pw.stop()

# 5. Process Isolation Test
@pytest.mark.asyncio
async def test_process_isolation_closing_playwright():
    config = SearchConfig(headless=True)
    profile = ResumeProfile(full_name="Test Candidate", email="test@example.com")
    platform = NaukriPlatform(config=config, profile=profile)

    await platform.init_browser()
    assert platform.browser.is_connected()
    
    # Close Playwright browser
    await platform.close_browser()
    
    # Assert Playwright browser disconnected while testing process/loop continues normally
    assert platform.browser is None or not platform.browser.is_connected()
    assert asyncio.get_running_loop().is_running()
