"""
ATS Detector and Factory.
Identifies target ATS systems (Greenhouse, Lever, etc.) from job URLs or page markup
and instantiates the appropriate ApplicationAdapter.
"""

from typing import Optional, List
from app.platforms.adapter_interface import ApplicationAdapter
from app.platforms.external.greenhouse import greenhouse_adapter, GreenhouseAdapter
from app.platforms.external.lever import lever_adapter, LeverAdapter
from app.platforms.external.workday import workday_adapter, WorkdayAdapter


class ATSDetector:
    """Detects ATS systems and returns matching ApplicationAdapter."""

    def __init__(self):
        self._adapters: List[ApplicationAdapter] = [
            greenhouse_adapter,
            lever_adapter,
            workday_adapter,
        ]

    def register_adapter(self, adapter: ApplicationAdapter):
        """Register a new external ATS adapter."""
        self._adapters.append(adapter)

    def detect_adapter(self, url: str, page_content: Optional[str] = None) -> Optional[ApplicationAdapter]:
        """Detect and return the appropriate adapter for a given URL or page content."""
        if not url:
            return None
        for adapter in self._adapters:
            if adapter.detect(url, page_content=page_content):
                return adapter
        return None


ats_detector = ATSDetector()


def detect_ats(url: str, page_content: Optional[str] = None) -> Optional[ApplicationAdapter]:
    """Helper function to quickly detect an ATS adapter."""
    return ats_detector.detect_adapter(url, page_content=page_content)
