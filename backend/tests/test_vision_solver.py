"""
Unit Tests for Phase 13 (Pillar 4): Vision-Assisted Coordinate Fallback Solver.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from app.platforms.vision_solver import VisionCoordinateSolver, BoundingBox


def test_bounding_box_geometry():
    box = BoundingBox(x=100.0, y=200.0, width=50.0, height=30.0)
    assert box.center == (125.0, 215.0)

    # Sample click point must lie within the bounds
    for _ in range(20):
        cx, cy = box.sample_natural_click_point()
        assert 100.0 <= cx <= 150.0
        assert 200.0 <= cy <= 230.0


@pytest.mark.asyncio
async def test_get_element_bounding_box_primary():
    solver = VisionCoordinateSolver()
    mock_page = MagicMock()
    mock_el = MagicMock()
    mock_el.bounding_box = AsyncMock(return_value={"x": 50, "y": 80, "width": 120, "height": 40})
    mock_page.query_selector = AsyncMock(return_value=mock_el)

    bbox = await solver.get_element_bounding_box(mock_page, "#submit-btn")
    assert bbox is not None
    assert bbox.x == 50
    assert bbox.width == 120


@pytest.mark.asyncio
async def test_get_element_bounding_box_js_fallback():
    solver = VisionCoordinateSolver()
    mock_page = MagicMock()
    mock_el = MagicMock()
    mock_el.bounding_box = AsyncMock(return_value=None)  # Fails primary
    mock_page.query_selector = AsyncMock(return_value=mock_el)
    mock_page.evaluate = AsyncMock(return_value={"x": 300, "y": 450, "width": 80, "height": 35})

    bbox = await solver.get_element_bounding_box(mock_page, ".shadow-root-btn")
    assert bbox is not None
    assert bbox.x == 300
    assert bbox.y == 450


@pytest.mark.asyncio
async def test_resilient_click_standard_success():
    solver = VisionCoordinateSolver()
    mock_page = MagicMock()
    mock_el = MagicMock()
    mock_el.is_visible = AsyncMock(return_value=True)
    mock_el.click = AsyncMock()
    mock_page.wait_for_selector = AsyncMock(return_value=mock_el)

    result = await solver.resilient_click(mock_page, "#normal-btn")
    assert result is True
    mock_el.click.assert_awaited_once()


@pytest.mark.asyncio
async def test_resilient_click_fallback_to_coordinate():
    solver = VisionCoordinateSolver()
    mock_page = MagicMock()
    # Standard click raises error
    mock_page.wait_for_selector = AsyncMock(side_effect=Exception("Element obscured by modal"))

    mock_el = MagicMock()
    mock_el.bounding_box = AsyncMock(return_value={"x": 200, "y": 300, "width": 100, "height": 50})
    mock_page.query_selector = AsyncMock(return_value=mock_el)
    mock_page.mouse = MagicMock()
    mock_page.mouse.move = AsyncMock()
    mock_page.mouse.down = AsyncMock()
    mock_page.mouse.up = AsyncMock()

    result = await solver.resilient_click(mock_page, "#obscured-btn")
    assert result is True
    mock_page.mouse.down.assert_awaited_once()
    mock_page.mouse.up.assert_awaited_once()
