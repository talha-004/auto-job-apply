"""
Vision-Assisted Coordinate Fallback Solver.
Enables visual coordinate detection, bounding box resolution, and human-like Bézier click fallback
for stubborn Shadow DOM elements, canvas controls, or obfuscated interactive buttons.
"""

import random
import asyncio
from typing import Dict, Any, Optional, Tuple
from pydantic import BaseModel, Field

from app.core.logger import logger
from app.platforms.stealth_driver import stealth_driver


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.width / 2.0, self.y + self.height / 2.0)

    def sample_natural_click_point(self) -> Tuple[float, float]:
        """Samples a point within the central 60% of the element to mimic human targeting."""
        offset_x = self.width * random.uniform(0.25, 0.75)
        offset_y = self.height * random.uniform(0.25, 0.75)
        return (round(self.x + offset_x, 2), round(self.y + offset_y, 2))


class VisionCoordinateSolver:
    """
    Solves interactive element targeting when standard CSS/XPath selectors
    fail due to Shadow DOM encapsulation or canvas obfuscation.
    """

    async def get_element_bounding_box(self, page: Any, selector: str) -> Optional[BoundingBox]:
        """Calculates viewport bounding box for selector or returns None."""
        try:
            el = await page.query_selector(selector)
            if not el:
                return None

            box = await el.bounding_box()
            if box:
                return BoundingBox(
                    x=box["x"],
                    y=box["y"],
                    width=box["width"],
                    height=box["height"]
                )
        except Exception as e:
            logger.debug(f"[VisionSolver] Error querying bounding box for '{selector}': {e}")

        # Fallback to JavaScript getBoundingClientRect
        try:
            js_script = f"""
            (() => {{
                const el = document.querySelector('{selector}');
                if (!el) return null;
                const rect = el.getBoundingClientRect();
                return {{ x: rect.x, y: rect.y, width: rect.width, height: rect.height }};
            }})()
            """
            rect = await page.evaluate(js_script)
            if rect and rect.get("width", 0) > 0 and rect.get("height", 0) > 0:
                return BoundingBox(**rect)
        except Exception as e:
            logger.debug(f"[VisionSolver] JS eval fallback error: {e}")

        return None

    async def click_coordinate_with_stealth(
        self,
        page: Any,
        x: float,
        y: float
    ) -> bool:
        """Dispatches natural Bézier curve mouse trajectory to coordinate followed by click."""
        try:
            # Move mouse using human biometrics driver
            if hasattr(stealth_driver, "human_move"):
                await stealth_driver.human_move(page, target_x=float(x), target_y=float(y))
            elif hasattr(page, "mouse"):
                await page.mouse.move(float(x), float(y))

            await asyncio.sleep(random.uniform(0.08, 0.22))

            # Mouse click with realistic human hold time
            if hasattr(page, "mouse"):
                await page.mouse.down()
                await asyncio.sleep(random.uniform(0.05, 0.12))
                await page.mouse.up()
            logger.info(f"[VisionSolver] Successfully executed stealth coordinate click at ({x}, {y})")
            return True
        except Exception as e:
            logger.warning(f"[VisionSolver] Failed stealth coordinate click at ({x}, {y}): {e}")
            return False

    async def resilient_click(
        self,
        page: Any,
        selector: str,
        timeout_ms: int = 3000
    ) -> bool:
        """
        Attempts standard Playwright click first.
        If blocked, obscured, or timeout occurs, resolves visual coordinates and clicks via Bézier stealth.
        """
        try:
            el = await page.wait_for_selector(selector, timeout=timeout_ms)
            if el and await el.is_visible():
                await el.click(timeout=timeout_ms)
                return True
        except Exception:
            logger.info(f"[VisionSolver] Standard click failed for '{selector}'. Falling back to visual coordinate solver.")

        # Visual Coordinate Fallback
        bbox = await self.get_element_bounding_box(page, selector)
        if bbox:
            target_x, target_y = bbox.sample_natural_click_point()
            return await self.click_coordinate_with_stealth(page, target_x, target_y)

        logger.warning(f"[VisionSolver] Could not locate bounding box for selector '{selector}'")
        return False


vision_solver = VisionCoordinateSolver()
