import pytest
import json
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.job import PlatformEnum, SearchConfig, ResumeProfile, QAVault
from app.platforms.base import BasePlatform, AdapterApplicationResult
from app.core.config import settings


class DummyPlatform(BasePlatform):
    """Concrete implementation of BasePlatform for testing session management."""

    async def login(self) -> bool:
        return True

    async def search_jobs(self, limit: int = 10):
        return []

    async def apply_to_job(self, job):
        return True

    async def search_and_apply(self, max_applications: int = 10):
        return []

    async def run(self):
        pass


@pytest.fixture
def mock_platform(tmp_path):
    config = SearchConfig(keywords="Python", location="Remote", headless=True)
    profile = ResumeProfile(
        full_name="Candidate",
        email="candidate@example.com",
        phone="1234567890",
        location="Remote",
        years_of_experience=3.0,
        skills=["Python"],
        qa_vault=QAVault()
    )
    platform = DummyPlatform(PlatformEnum.NAUKRI, config, profile)
    # Redirect paths to tmp_path
    platform.cookie_file = tmp_path / "naukri_cookies.json"
    platform.user_data_dir = tmp_path / "browser_profiles" / "naukri"
    return platform


@pytest.mark.asyncio
async def test_persistent_context_launch(mock_platform):
    """Verify launch_persistent_context is invoked with dedicated user data directory."""
    mock_playwright = MagicMock()
    mock_chromium = MagicMock()
    mock_context = AsyncMock()
    mock_page = AsyncMock()
    mock_page.is_closed = MagicMock(return_value=False)
    mock_context.pages = [mock_page]

    mock_chromium.launch_persistent_context = AsyncMock(return_value=mock_context)
    mock_playwright.chromium = mock_chromium

    with patch("app.platforms.base.async_playwright") as mock_pw_init:
        mock_pw_starter = AsyncMock()
        mock_pw_starter.start = AsyncMock(return_value=mock_playwright)
        mock_pw_init.return_value = mock_pw_starter

        with patch.object(settings, "USE_PERSISTENT_CONTEXT", True):
            page = await mock_platform.init_browser()

            assert page == mock_page
            assert mock_platform.is_persistent_context is True
            mock_chromium.launch_persistent_context.assert_called_once()
            args, kwargs = mock_chromium.launch_persistent_context.call_args
            assert str(mock_platform.user_data_dir) in kwargs.get("user_data_dir", args[0] if args else "")

            # Teardown
            await mock_platform.close_browser()
            mock_context.close.assert_called_once()


@pytest.mark.asyncio
async def test_persistent_context_fallback_on_lock_error(mock_platform):
    """Verify graceful fallback to standard browser when persistent context is locked."""
    mock_playwright = MagicMock()
    mock_chromium = MagicMock()
    mock_browser = AsyncMock()
    mock_context = AsyncMock()
    mock_page = AsyncMock()
    mock_page.is_closed = MagicMock(return_value=False)

    # Persistent context fails with lock error
    mock_chromium.launch_persistent_context = AsyncMock(
        side_effect=Exception("Failed to create user data directory: Profile locked by another process")
    )
    # Standard launch succeeds
    mock_chromium.launch = AsyncMock(return_value=mock_browser)
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_playwright.chromium = mock_chromium

    with patch("app.platforms.base.async_playwright") as mock_pw_init:
        mock_pw_starter = AsyncMock()
        mock_pw_starter.start = AsyncMock(return_value=mock_playwright)
        mock_pw_init.return_value = mock_pw_starter

        with patch.object(settings, "USE_PERSISTENT_CONTEXT", True):
            page = await mock_platform.init_browser()

            assert page == mock_page
            assert mock_platform.is_persistent_context is False
            mock_chromium.launch_persistent_context.assert_called_once()
            mock_chromium.launch.assert_called_once()
            mock_browser.new_context.assert_called_once()

            # Teardown
            await mock_platform.close_browser()
            mock_browser.close.assert_called_once()


def test_session_cookie_validation_valid(mock_platform):
    """Verify is_session_valid returns True when valid unexpired auth cookies exist."""
    future_exp = (datetime.now() + timedelta(days=7)).timestamp()
    cookies = [
        {"name": "naukri_auth", "value": "test_token_123", "domain": ".naukri.com", "expires": future_exp},
        {"name": "random_cookie", "value": "xyz", "expires": future_exp}
    ]
    with open(mock_platform.cookie_file, "w", encoding="utf-8") as f:
        json.dump(cookies, f)

    assert mock_platform.cookie_file.exists()
    assert pytest.approx(mock_platform.get_saved_cookies()[0]["expires"]) == future_exp

    import asyncio
    is_valid = asyncio.run(mock_platform.is_session_valid())
    assert is_valid is True


def test_session_cookie_validation_expired(mock_platform):
    """Verify is_session_valid returns False when auth cookies are expired."""
    past_exp = (datetime.now() - timedelta(days=1)).timestamp()
    cookies = [
        {"name": "naukri_auth", "value": "expired_token", "domain": ".naukri.com", "expires": past_exp}
    ]
    with open(mock_platform.cookie_file, "w", encoding="utf-8") as f:
        json.dump(cookies, f)

    import asyncio
    is_valid = asyncio.run(mock_platform.is_session_valid())
    assert is_valid is False


def test_session_cookie_validation_missing(mock_platform):
    """Verify is_session_valid returns False when no cookie file exists."""
    if mock_platform.cookie_file.exists():
        mock_platform.cookie_file.unlink()

    import asyncio
    is_valid = asyncio.run(mock_platform.is_session_valid())
    assert is_valid is False


def test_clear_saved_session(mock_platform):
    """Verify clear_saved_session removes cookie file and profile directory."""
    mock_platform.cookie_file.parent.mkdir(parents=True, exist_ok=True)
    mock_platform.cookie_file.write_text("[]")
    mock_platform.user_data_dir.mkdir(parents=True, exist_ok=True)
    dummy_file = mock_platform.user_data_dir / "profile_data.bin"
    dummy_file.write_text("test")

    assert mock_platform.cookie_file.exists()
    assert mock_platform.user_data_dir.exists()

    mock_platform.clear_saved_session(clear_profile_dir=True)

    assert not mock_platform.cookie_file.exists()
    assert not mock_platform.user_data_dir.exists()


def test_platform_directory_isolation():
    """Verify each platform gets an isolated persistent profile directory."""
    config = SearchConfig(keywords="Python", location="Remote", headless=True)
    profile = ResumeProfile(full_name="User", email="u@test.com", phone="123", location="Remote", years_of_experience=1.0)

    p_naukri = DummyPlatform(PlatformEnum.NAUKRI, config, profile)
    p_linkedin = DummyPlatform(PlatformEnum.LINKEDIN, config, profile)
    p_indeed = DummyPlatform(PlatformEnum.INDEED, config, profile)

    assert p_naukri.user_data_dir.name == "naukri"
    assert p_linkedin.user_data_dir.name == "linkedin"
    assert p_indeed.user_data_dir.name == "indeed"
    assert p_naukri.user_data_dir != p_linkedin.user_data_dir
    assert p_linkedin.user_data_dir != p_indeed.user_data_dir


@pytest.mark.asyncio
async def test_cleanup_orphaned_tabs(mock_platform):
    """Verify cleanup_orphaned_tabs safely closes popup/redirect pages while keeping worker page."""
    main_page = AsyncMock()
    main_page.is_closed = MagicMock(return_value=False)

    orphaned_tab1 = AsyncMock()
    orphaned_tab1.is_closed = MagicMock(return_value=False)
    orphaned_tab1.close = AsyncMock()

    orphaned_tab2 = AsyncMock()
    orphaned_tab2.is_closed = MagicMock(return_value=False)
    orphaned_tab2.close = AsyncMock()

    mock_platform.page = main_page
    mock_platform.context = MagicMock()
    mock_platform.context.pages = [main_page, orphaned_tab1, orphaned_tab2]

    closed_count = await mock_platform.cleanup_orphaned_tabs()

    assert closed_count == 2
    orphaned_tab1.close.assert_called_once()
    orphaned_tab2.close.assert_called_once()
    main_page.close.assert_not_called()

