"""
JobDiscoveryProvider — Abstract Base Interface for Discovery Providers.
"""

from abc import ABC, abstractmethod
from typing import List
from app.models.job import DiscoveredJob, DiscoveryConfig


class JobDiscoveryProvider(ABC):
    """Abstract base class for all job discovery providers (HTTP scrapers, guest APIs, browser crawlers)."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Human-readable provider name."""
        pass

    @abstractmethod
    async def discover(self, config: DiscoveryConfig) -> List[DiscoveredJob]:
        """Fetch and return normalized discovered jobs."""
        pass

    async def is_healthy(self) -> bool:
        """Check if provider endpoint / client is reachable and operating normally."""
        return True
