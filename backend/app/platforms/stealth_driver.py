"""
Human Biometrics & Anti-Ban Stealth Driver.
Provides realistic, non-linear Bezier mouse movements, humanized typing cadence
with deliberate typo-correction simulation, reading pauses, and platform challenge detection.
"""

import math
import random
import asyncio
from typing import List, Tuple, Optional, Union
from playwright.async_api import Page, ElementHandle, Locator

from app.core.logger import logger


class PlatformCoolDownException(Exception):
    """Raised when an anti-bot challenge, CAPTCHA, or rate limit threshold is encountered."""
    def __init__(self, platform: str, reason: str, cooldown_minutes: int = 120):
        super().__init__(f"Platform '{platform}' triggered cooldown ({reason}). Sleeping for {cooldown_minutes} min.")
        self.platform = platform
        self.reason = reason
        self.cooldown_minutes = cooldown_minutes


class HumanBiometricsDriver:
    """
    Simulates organic human interaction patterns for browser automation.
    Adheres to Fitts' Law and realistic cognitive-motor delays.
    """

    CHALLENGE_KEYWORDS = [
        "verify you are a human",
        "access denied",
        "too many requests",
        "please solve this puzzle",
        "security check",
        "cloudflare",
        "unusual traffic",
        "bot detected"
    ]

    QWERTY_ADJACENT = {
        'a': ['s', 'q', 'z'],
        'b': ['v', 'g', 'h', 'n'],
        'c': ['x', 'd', 'v'],
        'd': ['s', 'e', 'r', 'f', 'c', 'x'],
        'e': ['w', 's', 'd', 'r'],
        'f': ['d', 'r', 't', 'g', 'v', 'c'],
        'g': ['f', 't', 'y', 'h', 'b', 'v'],
        'h': ['g', 'y', 'u', 'j', 'n', 'b'],
        'i': ['u', 'j', 'k', 'o'],
        'j': ['h', 'u', 'i', 'k', 'm', 'n'],
        'k': ['j', 'i', 'o', 'l', 'm'],
        'l': ['k', 'o', 'p'],
        'm': ['n', 'j', 'k'],
        'n': ['b', 'h', 'j', 'm'],
        'o': ['i', 'k', 'l', 'p'],
        'p': ['o', 'l'],
        'q': ['w', 'a'],
        'r': ['e', 'd', 'f', 't'],
        's': ['a', 'w', 'e', 'd', 'x', 'z'],
        't': ['r', 'f', 'g', 'y'],
        'u': ['y', 'h', 'j', 'i'],
        'v': ['c', 'f', 'g', 'b'],
        'w': ['q', 'a', 's', 'e'],
        'x': ['z', 's', 'd', 'c'],
        'y': ['t', 'g', 'h', 'u'],
        'z': ['a', 's', 'x']
    }

    def __init__(self, current_pos: Tuple[float, float] = (100.0, 100.0)):
        self.current_x = current_pos[0]
        self.current_y = current_pos[1]

    @staticmethod
    def calculate_bezier_curve(
        start: Tuple[float, float],
        end: Tuple[float, float],
        num_points: int = 25,
        deviation: float = 0.25
    ) -> List[Tuple[float, float]]:
        """
        Generates a smooth cubic Bezier trajectory between start and end coordinates.
        Control points are perturbed with controlled randomness for natural curvature.
        """
        x0, y0 = start
        x3, y3 = end

        distance = math.hypot(x3 - x0, y3 - y0)
        spread = max(15.0, distance * deviation)

        # Control point 1: near start with lateral deviation
        ctrl1_x = x0 + (x3 - x0) * 0.25 + random.uniform(-spread, spread)
        ctrl1_y = y0 + (y3 - y0) * 0.25 + random.uniform(-spread, spread)

        # Control point 2: near end with decaying deviation
        ctrl2_x = x0 + (x3 - x0) * 0.75 + random.uniform(-spread * 0.5, spread * 0.5)
        ctrl2_y = y0 + (y3 - y0) * 0.75 + random.uniform(-spread * 0.5, spread * 0.5)

        points = []
        for i in range(num_points + 1):
            t = i / float(num_points)
            u = 1.0 - t

            # Cubic Bezier formula: B(t) = (1-t)^3*P0 + 3(1-t)^2*t*P1 + 3(1-t)*t^2*P2 + t^3*P3
            px = (u ** 3) * x0 + 3 * (u ** 2) * t * ctrl1_x + 3 * u * (t ** 2) * ctrl2_x + (t ** 3) * x3
            py = (u ** 3) * y0 + 3 * (u ** 2) * t * ctrl1_y + 3 * u * (t ** 2) * ctrl2_y + (t ** 3) * y3

            # Apply micro-jitter (sub-pixel human hand tremor)
            if 0 < i < num_points:
                px += random.gauss(0, 0.4)
                py += random.gauss(0, 0.4)

            points.append((round(px, 2), round(py, 2)))

        return points

    async def human_move(
        self,
        page: Page,
        target_x: float,
        target_y: float,
        num_points: int = 20,
        speed_factor: float = 1.0
    ):
        """Moves the mouse cursor along a cubic Bezier curve to the target location."""
        start = (self.current_x, self.current_y)
        end = (target_x, target_y)
        path = self.calculate_bezier_curve(start, end, num_points=num_points)

        for px, py in path:
            await page.mouse.move(px, py)
            step_delay = max(0.002, random.uniform(0.005, 0.015) / speed_factor)
            await asyncio.sleep(step_delay)

        self.current_x = target_x
        self.current_y = target_y

    async def human_click(
        self,
        page: Page,
        target: Union[str, ElementHandle, Locator],
        click_type: str = "left"
    ):
        """Moves cursor to target element with natural curve, hovers briefly, and clicks."""
        if isinstance(target, str):
            element = await page.wait_for_selector(target, timeout=5000)
        elif isinstance(target, Locator):
            element = await target.element_handle()
        else:
            element = target

        if not element:
            raise ValueError(f"Target element not found for human click: {target}")

        box = await element.bounding_box()
        if not box:
            await element.click()
            return

        # Target center with slight natural offset
        target_x = box["x"] + box["width"] * random.uniform(0.35, 0.65)
        target_y = box["y"] + box["height"] * random.uniform(0.35, 0.65)

        await self.human_move(page, target_x, target_y)
        await asyncio.sleep(random.uniform(0.08, 0.22))  # Pre-click fixation pause

        await page.mouse.down(button=click_type)
        await asyncio.sleep(random.uniform(0.04, 0.09))  # Physical click depression duration
        await page.mouse.up(button=click_type)
        await asyncio.sleep(random.uniform(0.05, 0.15))  # Post-click reaction delay

    async def human_type(
        self,
        page: Page,
        selector_or_element: Union[str, ElementHandle, Locator],
        text: str,
        typo_chance: float = 0.03,
        min_delay_ms: int = 40,
        max_delay_ms: int = 160
    ):
        """
        Types text character-by-character with organic latency distributions
        and realistic typo-correction behavior.
        """
        if isinstance(selector_or_element, str):
            await page.click(selector_or_element)
            target = page.locator(selector_or_element)
        elif isinstance(selector_or_element, Locator):
            await selector_or_element.click()
            target = selector_or_element
        else:
            await selector_or_element.click()
            target = selector_or_element

        for i, char in enumerate(text):
            # Typo simulation: inject adjacent character, pause, backspace, and correct
            if typo_chance > 0 and random.random() < typo_chance and char.lower() in self.QWERTY_ADJACENT:
                typo_char = random.choice(self.QWERTY_ADJACENT[char.lower()])
                if char.isupper():
                    typo_char = typo_char.upper()

                await page.keyboard.type(typo_char)
                await asyncio.sleep(random.uniform(0.12, 0.28))  # Realization delay
                await page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.08, 0.18))  # Reaction delay

            # Type actual character
            await page.keyboard.type(char)

            # Character latency: spaces and punctuation cause longer cognitive pauses
            if char in " .,\n":
                delay = random.uniform(0.12, 0.28)
            else:
                delay = random.uniform(min_delay_ms / 1000.0, max_delay_ms / 1000.0)

            await asyncio.sleep(delay)

    @staticmethod
    async def natural_reading_pause(char_count: int, reading_wpm: int = 240, max_seconds: float = 4.0):
        """Simulates a user reading content on the page before taking an action."""
        words = max(1, char_count // 5)
        expected_seconds = (words / reading_wpm) * 60.0
        capped_seconds = min(max_seconds, max(0.5, expected_seconds))
        # Random variance
        actual_delay = capped_seconds * random.uniform(0.8, 1.2)
        await asyncio.sleep(actual_delay)

    async def detect_and_handle_challenges(self, page: Page, platform: str = "Unknown"):
        """Inspects page content and title for anti-bot triggers and CAPTCHAs."""
        try:
            content = (await page.content()).lower()
            title = (await page.title()).lower()

            for kw in self.CHALLENGE_KEYWORDS:
                if kw in title or kw in content:
                    logger.warning(f"Anti-bot challenge pattern detected on {platform}: '{kw}'")
                    raise PlatformCoolDownException(
                        platform=platform,
                        reason=f"Challenge keyword '{kw}' detected on page",
                        cooldown_minutes=120
                    )
        except PlatformCoolDownException:
            raise
        except Exception as e:
            logger.debug(f"Challenge inspection error (non-fatal): {e}")


# Global stealth driver instance
stealth_driver = HumanBiometricsDriver()
