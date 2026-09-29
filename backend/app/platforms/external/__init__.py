"""
External ATS Application Adapters Package.
"""

from app.platforms.external.greenhouse import greenhouse_adapter, GreenhouseAdapter
from app.platforms.external.lever import lever_adapter, LeverAdapter
from app.platforms.external.ats_detector import ats_detector, detect_ats

__all__ = [
    "greenhouse_adapter",
    "GreenhouseAdapter",
    "lever_adapter",
    "LeverAdapter",
    "ats_detector",
    "detect_ats",
]
