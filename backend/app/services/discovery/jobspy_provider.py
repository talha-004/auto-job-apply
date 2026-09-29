"""
JobSpyProvider — Rapid Multi-Board Job Scraping via python-jobspy & HTTP Guest APIs.
Discovers jobs from LinkedIn, Indeed, Glassdoor, and ZipRecruiter in seconds.
"""

import asyncio
import hashlib
import re
import urllib.parse
from typing import List, Dict, Any, Optional
import httpx

from app.core.logger import logger, broadcaster, LogLevel
from app.models.job import DiscoveredJob, DiscoveryConfig
from app.services.discovery.base import JobDiscoveryProvider


class JobSpyProvider(JobDiscoveryProvider):
    """
    Rapid multi-platform discovery engine using python-jobspy HTTP endpoints
    with resilient guest-API fallback.
    """

    @property
    def provider_name(self) -> str:
        return "JobSpy Fast Scraper"

    async def discover(self, config: DiscoveryConfig) -> List[DiscoveredJob]:
        results: List[DiscoveredJob] = []

        # 1. Primary: Attempt scrape via python-jobspy
        try:
            jobspy_results = await asyncio.to_thread(self._run_jobspy_sync, config)
            if jobspy_results:
                results.extend(jobspy_results)
                await broadcaster.emit_log(
                    f"⚡ JobSpy Discovery: Found {len(results)} jobs for '{config.keywords}' across {config.platforms}!",
                    level=LogLevel.SUCCESS
                )
                return results
        except Exception as e:
            logger.warning(f"JobSpy scrape encounter: {e}. Executing resilient fallback...")

        # 2. Resilient Fallback: LinkedIn Public Guest Search API
        try:
            fallback_results = await self._run_linkedin_guest_search(config)
            if fallback_results:
                results.extend(fallback_results)
                await broadcaster.emit_log(
                    f"⚡ Direct Guest Search: Discovered {len(fallback_results)} listings for '{config.keywords}'!",
                    level=LogLevel.INFO
                )
        except Exception as e:
            logger.error(f"Fallback guest search error: {e}")

        return results

    def _run_jobspy_sync(self, config: DiscoveryConfig) -> List[DiscoveredJob]:
        """Synchronous execution of python-jobspy within a background worker thread."""
        try:
            from jobspy import scrape_jobs
        except ImportError:
            logger.info("python-jobspy not yet available in current runtime, using fallback.")
            return []

        # Map platform names to JobSpy valid site names
        valid_sites = ["linkedin", "indeed", "glassdoor", "zip_recruiter"]
        target_sites = [s.lower() for s in config.platforms if s.lower() in valid_sites]
        if not target_sites:
            target_sites = ["linkedin", "indeed"]

        loc_str = config.location or "India"
        country_indeed = config.country_indeed
        if not country_indeed:
            country_indeed = "india" if any(w in loc_str.lower() for w in ["india", "bangalore", "hyderabad", "chennai", "delhi", "pune", "mumbai"]) else "usa"

        try:
            jobs_df = scrape_jobs(
                site_name=target_sites,
                search_term=config.keywords,
                location=loc_str,
                results_wanted=min(config.results_wanted, 50),
                hours_old=config.hours_old,
                country_indeed=country_indeed,
                is_remote=config.is_remote if config.is_remote is not None else False
            )

            if jobs_df is None or jobs_df.empty:
                return []

            discovered: List[DiscoveredJob] = []
            for _, row in jobs_df.iterrows():
                url = str(row.get("job_url", "")).strip()
                if not url:
                    continue

                title = str(row.get("title", "")).strip() or "Software Engineer"
                company = str(row.get("company", "")).strip() or "Company"
                site = str(row.get("site", "External")).capitalize()
                location = str(row.get("location", loc_str)).strip()
                description = str(row.get("description", "")).strip()

                # Generate unique canonical job_id
                job_id = f"JOB-{hashlib.md5(url.encode('utf-8')).hexdigest()[:8]}"

                # Salary parsing
                salary_min = None
                salary_max = None
                try:
                    s_min = row.get("min_amount")
                    if s_min and not str(s_min).lower() == "nan":
                        salary_min = float(s_min)
                    s_max = row.get("max_amount")
                    if s_max and not str(s_max).lower() == "nan":
                        salary_max = float(s_max)
                except (ValueError, TypeError):
                    pass

                discovered.append(DiscoveredJob(
                    job_id=job_id,
                    platform=site,
                    title=title,
                    company=company,
                    location=location,
                    is_remote=bool(row.get("is_remote", False)),
                    job_url=url,
                    description=description,
                    posted_date=str(row.get("date_posted", "")) if row.get("date_posted") else None,
                    salary_min=salary_min,
                    salary_max=salary_max,
                    currency=str(row.get("currency", "INR")) if row.get("currency") else "INR",
                    job_type=str(row.get("job_type", "fulltime")) if row.get("job_type") else "fulltime",
                    raw_metadata={
                        "emails": row.get("emails", []),
                        "site": site
                    }
                ))

            return discovered

        except Exception as e:
            logger.warning(f"Error executing scrape_jobs: {e}")
            return []

    async def _run_linkedin_guest_search(self, config: DiscoveryConfig) -> List[DiscoveredJob]:
        """Resilient fallback scraper using LinkedIn public guest job card endpoint."""
        q_enc = urllib.parse.quote(config.keywords)
        loc_enc = urllib.parse.quote(config.location or "India")
        api_url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={q_enc}&location={loc_enc}&start=0"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9"
        }

        discovered: List[DiscoveredJob] = []
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(api_url, headers=headers)
            if resp.status_code != 200:
                return []

            html = resp.text
            titles = re.findall(r'<h3 class="base-search-card__title">\s*(.*?)\s*</h3>', html, re.DOTALL)
            companies = re.findall(r'<h4 class="base-search-card__subtitle">\s*<a[^>]*>\s*(.*?)\s*</a>', html, re.DOTALL)
            links = re.findall(r'<a class="base-card__full-link[^"]*" href="([^"?]*)', html)

            limit = min(len(titles), len(companies), len(links), config.results_wanted)
            for i in range(limit):
                clean_title = titles[i].strip()
                clean_company = companies[i].strip()
                clean_url = links[i].strip()
                job_id = f"JOB-{hashlib.md5(clean_url.encode('utf-8')).hexdigest()[:8]}"

                discovered.append(DiscoveredJob(
                    job_id=job_id,
                    platform="LinkedIn",
                    title=clean_title,
                    company=clean_company,
                    location=config.location or "India",
                    is_remote="remote" in clean_title.lower() or "remote" in (config.location or "").lower(),
                    job_url=clean_url,
                    description=f"{clean_title} role at {clean_company}.",
                    job_type="fulltime"
                ))

        return discovered
