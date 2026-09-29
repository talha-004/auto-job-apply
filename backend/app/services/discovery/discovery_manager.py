"""
DiscoveryManager — Central Coordinator for Multi-Board Job Discovery & Deduplication.
Runs discovery providers, filters out duplicates, and feeds fresh jobs to evaluation.
"""

import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

from app.core.logger import logger, broadcaster, LogLevel
from app.models.job import DiscoveredJob, DiscoveryConfig
from app.services.discovery.base import JobDiscoveryProvider
from app.services.discovery.jobspy_provider import JobSpyProvider
from app.services.excel_tracker import excel_tracker


class DiscoveryManager:
    """Coordinates job discovery across multiple providers with bounded concurrency and deduplication."""

    def __init__(self):
        self.providers: List[JobDiscoveryProvider] = [
            JobSpyProvider()
        ]
        self._session_seen_urls: set = set()

    def register_provider(self, provider: JobDiscoveryProvider) -> None:
        """Register a new discovery provider dynamically."""
        self.providers.append(provider)

    async def discover_jobs(self, config: DiscoveryConfig) -> List[DiscoveredJob]:
        """
        Executes job discovery across all registered providers, aggregates results,
        and applies strict layered deduplication.
        
        Returns:
            List of fresh, non-duplicate DiscoveredJob instances.
        """
        await broadcaster.emit_log(
            f"🔎 Starting job discovery for '{config.keywords}' ({config.location}) across {len(self.providers)} provider(s)...",
            level=LogLevel.INFO
        )

        all_discovered: List[DiscoveredJob] = []

        # Execute providers concurrently with error isolation
        tasks = [self._execute_provider_safe(p, config) for p in self.providers]
        provider_results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in provider_results:
            if isinstance(res, list):
                all_discovered.extend(res)
            elif isinstance(res, Exception):
                logger.error(f"Discovery provider error: {res}")

        await broadcaster.emit_log(
            f"📋 Raw discovery completed: {len(all_discovered)} total listings retrieved. Running deduplication...",
            level=LogLevel.INFO
        )

        # Deduplication pipeline
        fresh_jobs: List[DiscoveredJob] = []
        dup_count = 0

        for job in all_discovered:
            # 1. Check in-memory session deduplication
            if job.job_url in self._session_seen_urls:
                dup_count += 1
                continue

            # 2. Check persistent Excel tracker deduplication (Exact URL & Semantic Fingerprint)
            is_dup, dup_type, matched_id = excel_tracker.check_duplicate(
                job_url=job.job_url,
                company=job.company,
                job_title=job.title,
                location=job.location
            )

            if is_dup:
                dup_count += 1
                logger.debug(f"Skipping {dup_type} duplicate job: {job.title} at {job.company} (matched {matched_id})")
                continue

            # Valid fresh job
            self._session_seen_urls.add(job.job_url)
            fresh_jobs.append(job)

        await broadcaster.emit_log(
            f"✨ Deduplication summary: {len(fresh_jobs)} fresh eligible jobs discovered ({dup_count} duplicates skipped).",
            level=LogLevel.SUCCESS
        )

        return fresh_jobs

    async def _execute_provider_safe(self, provider: JobDiscoveryProvider, config: DiscoveryConfig) -> List[DiscoveredJob]:
        """Safely execute a single discovery provider with timeout protection."""
        try:
            return await asyncio.wait_for(provider.discover(config), timeout=60.0)
        except asyncio.TimeoutError:
            logger.warning(f"Discovery provider '{provider.provider_name}' timed out after 60s.")
            return []
        except Exception as e:
            logger.error(f"Discovery provider '{provider.provider_name}' failed: {e}")
            return []

    def clear_session_cache(self) -> None:
        """Clear in-memory session URL cache."""
        self._session_seen_urls.clear()


discovery_manager = DiscoveryManager()
