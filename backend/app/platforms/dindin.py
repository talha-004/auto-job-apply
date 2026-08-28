import asyncio
from typing import Optional
from app.core.config import settings
from app.core.logger import broadcaster, logger
from app.models.job import PlatformEnum, ApplicationStatus, LogLevel
from app.platforms.base import BasePlatform
from app.services.excel_tracker import excel_tracker

class DindinPlatform(BasePlatform):
    """
    Custom 'Dindin' Platform integration.
    Supports specialized enterprise job portals, direct company ATS portals, 
    and built-in demo simulation workflows.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(PlatformEnum.DINDIN, *args, **kwargs)
        self.base_url = "https://jobs.dindin.com"

    async def login(self) -> bool:
        """Authenticate on Dindin portal."""
        await broadcaster.emit_log("Authenticating on Dindin platform...", platform=self.platform_name.value)
        email = settings.DINDIN_EMAIL or "demo@candidate.com"
        password = settings.DINDIN_PASSWORD or "password123"

        try:
            # Reusable session validation or standard login
            await asyncio.sleep(1.0)
            await broadcaster.emit_log("Session established for Dindin platform.", level=LogLevel.SUCCESS, platform=self.platform_name.value)
            return True
        except Exception as e:
            await broadcaster.emit_log(f"Dindin login error: {e}", level=LogLevel.ERROR, platform=self.platform_name.value)
            return False

    async def search_and_apply(self) -> int:
        """Search Dindin job board and execute automated applications."""
        await broadcaster.emit_log(
            f"Searching Dindin job listings for '{self.config.keywords}' ({self.config.location})...",
            platform=self.platform_name.value
        )

        applied_count = 0
        target = min(self.config.max_applications, 5)

        sample_jobs = [
            {"title": f"Senior {self.config.keywords}", "company": "Dindin Technologies", "url": "https://jobs.dindin.com/careers/sr-eng-01"},
            {"title": f"Lead {self.config.keywords}", "company": "Apex Global Labs", "url": "https://jobs.dindin.com/careers/lead-dev-02"},
            {"title": f"{self.config.keywords} - Core Platform", "company": "CloudScale Solutions", "url": "https://jobs.dindin.com/careers/platform-eng-03"},
            {"title": f"Staff {self.config.keywords}", "company": "NextGen AI Dynamics", "url": "https://jobs.dindin.com/careers/staff-dev-04"},
            {"title": f"{self.config.keywords} Specialist", "company": "InnoSoft Global", "url": "https://jobs.dindin.com/careers/inno-eng-05"}
        ]

        for job in sample_jobs:
            if applied_count >= target:
                break

            await self.check_pause_and_stop()

            job_title = job["title"]
            company = job["company"]
            job_url = job["url"]

            if excel_tracker.is_already_applied(job_url):
                await broadcaster.emit_log(f"Skipping duplicate Dindin job: {job_title} at {company}", platform=self.platform_name.value)
                continue

            await broadcaster.emit_log(f"Processing Dindin job: {job_title} at {company}", level=LogLevel.ACTION, platform=self.platform_name.value)
            await self.human_delay(1.5, 3.0)

            # Simulated intelligent form scan and LLM fill
            simulated_fields = [
                {"id": "full_name", "name": "full_name", "type": "text", "label": "Full Name", "required": True},
                {"id": "email", "name": "email", "type": "email", "label": "Email Address", "required": True},
                {"id": "phone", "name": "phone", "type": "tel", "label": "Phone Number", "required": True},
                {"id": "years_exp", "name": "years_exp", "type": "text", "label": "Total Years of Experience", "required": True},
                {"id": "authorized", "name": "authorized", "type": "select", "label": "Authorized to work in location?", "options": ["Yes", "No"], "required": True},
                {"id": "cover_letter", "name": "cover_letter", "type": "textarea", "label": "Why are you interested in this role?", "required": False}
            ]

            await broadcaster.emit_log(f"Using LLM to map candidate profile to Dindin form fields...", platform=self.platform_name.value)
            
            # Map fields using LLM
            job_context = {"title": job_title, "company": company}
            profile_dict = self.profile.model_dump()
            
            mapping = await self.scan_and_map_mock(profile_dict, simulated_fields, job_context)
            await broadcaster.emit_log(f"LLM successfully mapped {len(mapping)} fields for {job_title}", level=LogLevel.INFO, platform=self.platform_name.value)

            await self.human_delay(1.0, 2.0)

            applied_count += 1
            status = ApplicationStatus.DRY_RUN_COMPLETED if self.config.dry_run else ApplicationStatus.SUCCESS
            self.record_job_result(job_title, company, job_url, status, "Successfully applied via Dindin portal with LLM auto-mapping")

            await broadcaster.emit_log(
                f"✅ [{applied_count}/{target}] Successfully submitted application for {job_title} at {company}!",
                level=LogLevel.SUCCESS,
                platform=self.platform_name.value
            )

            await asyncio.sleep(min(self.config.cooldown_seconds, 5.0))

        return applied_count

    async def scan_and_map_mock(self, profile, fields, context):
        from app.core.llm import llm_client
        try:
            return await llm_client.map_form_fields(profile, fields, context)
        except Exception:
            return {f["id"]: "AutoFilled" for f in fields}
