"""
Unit Tests for Phase 16: Human Biometrics & Anti-Ban Stealth Driver.
Validates Bezier curve path mathematics, organic typing cadence, typo simulation,
natural reading pauses, and platform challenge detection.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.platforms.stealth_driver import (
    HumanBiometricsDriver,
    PlatformCoolDownException,
    stealth_driver
)


def test_bezier_curve_generation():
    """Verify cubic Bezier curve points, start/end precision, and trajectory shape."""
    start = (100.0, 150.0)
    end = (850.0, 600.0)
    num_points = 30

    points = HumanBiometricsDriver.calculate_bezier_curve(start, end, num_points=num_points, deviation=0.2)

    assert len(points) == num_points + 1
    # Check start and end proximity
    assert points[0] == start
    assert points[-1] == end

    # Verify that the trajectory has smooth, bounded delta steps
    for i in range(len(points) - 1):
        x1, y1 = points[i]
        x2, y2 = points[i + 1]
        dist = ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5
        assert dist < 100.0, f"Discontinuous jump detected at step {i}: {dist}"


def test_qwerty_adjacent_key_mapping():
    """Verify that common letters have valid QWERTY keyboard adjacent substitutions."""
    driver = HumanBiometricsDriver()
    for char in ['a', 'e', 'i', 'o', 's', 't']:
        assert char in driver.QWERTY_ADJACENT
        assert len(driver.QWERTY_ADJACENT[char]) >= 2
        for adj in driver.QWERTY_ADJACENT[char]:
            assert isinstance(adj, str)
            assert len(adj) == 1


@pytest.mark.asyncio
async def test_natural_reading_pause_duration():
    """Verify that reading pause scales reasonably with text length and stays bounded."""
    # Test short snippet (50 chars ~ 10 words)
    start = asyncio.get_event_loop().time()
    await HumanBiometricsDriver.natural_reading_pause(char_count=50, max_seconds=0.1)
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 0.3

    # Verify max_seconds cap
    start = asyncio.get_event_loop().time()
    await HumanBiometricsDriver.natural_reading_pause(char_count=10000, max_seconds=0.1)
    elapsed = asyncio.get_event_loop().time() - start
    assert elapsed < 0.3


@pytest.mark.asyncio
async def test_challenge_detection_triggers_cooldown():
    """Verify that challenge keywords trigger PlatformCoolDownException with appropriate backoff."""
    driver = HumanBiometricsDriver()
    mock_page = MagicMock()
    mock_page.content = AsyncMock(return_value="<html><body>Please verify you are a human before proceeding.</body></html>")
    mock_page.title = AsyncMock(return_value="Cloudflare Security Check")

    with pytest.raises(PlatformCoolDownException) as exc_info:
        await driver.detect_and_handle_challenges(mock_page, platform="LinkedIn")

    assert exc_info.value.platform == "LinkedIn"
    assert exc_info.value.cooldown_minutes == 120
    assert "verify you are a human" in exc_info.value.reason.lower()


@pytest.mark.asyncio
async def test_challenge_detection_clean_page():
    """Verify that normal job board pages do not trigger cooldown exceptions."""
    driver = HumanBiometricsDriver()
    mock_page = MagicMock()
    mock_page.content = AsyncMock(return_value="<html><body>Apply to Lead Python Engineer at Tech Corp</body></html>")
    mock_page.title = AsyncMock(return_value="Lead Python Engineer - Tech Corp")

    # Should not raise any exception
    await driver.detect_and_handle_challenges(mock_page, platform="Indeed")


@pytest.mark.asyncio
async def test_human_move_mouse_trajectory():
    """Verify mouse moves along Bezier curve coordinates."""
    driver = HumanBiometricsDriver(current_pos=(50.0, 50.0))
    mock_page = MagicMock()
    mock_page.mouse = MagicMock()
    mock_page.mouse.move = AsyncMock()

    await driver.human_move(mock_page, target_x=300.0, target_y=400.0, num_points=10, speed_factor=10.0)

    assert mock_page.mouse.move.call_count == 11
    assert driver.current_x == 300.0
    assert driver.current_y == 400.0


@pytest.mark.asyncio
async def test_human_type_simulation():
    """Verify human typing dispatches keyboard events with typo correction."""
    driver = HumanBiometricsDriver()
    mock_page = MagicMock()
    mock_page.click = AsyncMock()
    mock_page.keyboard = MagicMock()
    mock_page.keyboard.type = AsyncMock()
    mock_page.keyboard.press = AsyncMock()
    mock_page.locator = MagicMock(return_value=MagicMock())

    # Test with typo_chance=0.0 (deterministic typing)
    await driver.human_type(mock_page, "#search-input", "Python", typo_chance=0.0, min_delay_ms=1, max_delay_ms=2)

    typed_chars = [call.args[0] for call in mock_page.keyboard.type.call_args_list]
    assert "".join(typed_chars) == "Python"


@pytest.mark.asyncio
async def test_human_click_with_submit_hesitation():
    """Verify human_click introduces bounded jitter and submit micro-hesitation pause."""
    driver = HumanBiometricsDriver(current_pos=(100.0, 100.0))
    mock_page = MagicMock()
    mock_page.mouse = MagicMock()
    mock_page.mouse.move = AsyncMock()
    mock_page.mouse.down = AsyncMock()
    mock_page.mouse.up = AsyncMock()

    mock_element = MagicMock()
    mock_element.bounding_box = AsyncMock(return_value={"x": 200.0, "y": 300.0, "width": 120.0, "height": 40.0})

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await driver.human_click(mock_page, mock_element, is_submit_action=True)

        # Confirm target position was bounded within the element's box (202 <= x <= 318, 302 <= y <= 338)
        assert 202.0 <= driver.current_x <= 318.0
        assert 302.0 <= driver.current_y <= 338.0

        # Verify mouse down and up were invoked
        mock_page.mouse.down.assert_called_once_with(button="left")
        mock_page.mouse.up.assert_called_once_with(button="left")

        # Verify sleep was called for submit hesitation (> 1.0s)
        sleep_durations = [call.args[0] for call in mock_sleep.call_args_list]
        assert any(d >= 1.2 for d in sleep_durations)

