"""
Comprehensive End-to-End Test Suite for AutoApplyJobs V2 Enhancements (Phases 16 - 22).
Verifies that all 6 advanced subsystems function cohesively in an integrated lifecycle:
1. Stealth Human Biometrics & Anti-Ban Driver
2. Smart Form Intelligence & Semantic Dropdown Resolver
3. ATS Keyword Gap Analyzer & Multi-Template Resume Engine
4. Recruiter Lead Discovery & Automated 5-Day Follow-Up
5. Mobile Quick-Action Companion (Telegram Bot)
6. Conversion Funnel Analytics & Platform ROI Calculation
"""

import os
from pathlib import Path
import pytest
from unittest.mock import MagicMock, AsyncMock

from app.models.job import ResumeProfile, WorkExperience, Education
from app.platforms.stealth_driver import HumanBiometricsDriver, PlatformCoolDownException
from app.services.form_intelligence import FormIntelligenceService
from app.services.ats_scorer import ATSScorer
from app.services.resume_tailorer import ResumeTailorer, TemplateType
from app.services.recruiter_discovery import RecruiterDiscoveryService
from app.services.followup_service import FollowUpService
from app.services.telegram_bot import TelegramCompanionService
from app.services.analytics_service import AnalyticsService


@pytest.fixture
def candidate_profile() -> ResumeProfile:
    return ResumeProfile(
        full_name="Morgan Vance",
        email="morgan.vance@techcorp.io",
        phone="+1 555-901-2345",
        location="San Francisco, CA",
        github_url="https://github.com/morganvance",
        portfolio_url="https://morganvance.dev",
        years_of_experience=4.0,
        summary="Senior Software Engineer specializing in Python, FastAPI, React, and cloud native architectures with Docker and PostgreSQL.",
        skills=["Python", "FastAPI", "React", "Docker", "PostgreSQL", "AWS", "Git"],
        work_experience=[
            WorkExperience(
                company="Nexus Systems",
                title="Software Engineer",
                start_date="2022-01",
                end_date="Present",
                description="Built high-throughput distributed microservices using Python and FastAPI. Managed container deployments with Docker."
            )
        ],
        education=[
            Education(
                institution="UC Berkeley",
                degree="B.S. Electrical Engineering & Computer Science",
                graduation_year="2021"
            )
        ]
    )


@pytest.mark.asyncio
async def test_v2_integrated_lifecycle(tmp_path: Path, candidate_profile: ResumeProfile):
    """Executes a full multi-subsystem v2 test sequence."""

    # 1. Stealth Driver Verification
    stealth = HumanBiometricsDriver(current_pos=(100.0, 100.0))
    path = stealth.calculate_bezier_curve((100.0, 100.0), (500.0, 700.0), num_points=15)
    assert len(path) == 16
    assert path[0] == (100.0, 100.0)
    assert path[-1] == (500.0, 700.0)

    # 2. Form Intelligence & Salary Resolution
    form_intel = FormIntelligenceService()
    jd = "Senior Python Engineer needed at CloudScale. Pay: $130,000 - $170,000. Must have Docker and PostgreSQL experience."
    salary_rec = form_intel.calculate_competitive_salary(jd, candidate_target=140000.0)
    assert salary_rec.recommended_salary == 160000.0  # 75th percentile of 130k-170k

    resolved_auth = form_intel.resolve_dropdown_or_radio(
        "Are you legally authorized to work?",
        ["No", "Yes, authorized", "Need sponsorship"],
        {"work_authorized": True}
    )
    assert resolved_auth.selected_option == "Yes, authorized"

    # 3. ATS Scorecard & Multi-Template PDF Tailoring
    scorer = ATSScorer()
    scorecard = scorer.evaluate_resume_ats_match(candidate_profile, jd)
    assert scorecard.overall_score >= 75.0
    assert "python" in scorecard.matched_keywords
    assert "docker" in scorecard.matched_keywords

    tailorer = ResumeTailorer(storage_dir=tmp_path)
    resume_res = tailorer.generate_tailored_resume(
        profile=candidate_profile,
        job_title="Senior Python Engineer",
        jd_text=jd,
        job_id="v2_cert_test_job",
        template=TemplateType.TECH_MINIMALIST
    )
    assert os.path.exists(resume_res.pdf_path)
    assert resume_res.template_used == "tech_minimalist"
    assert resume_res.ats_score is not None

    # 4. Recruiter Discovery & Follow-Up Check-in
    discovery = RecruiterDiscoveryService()
    leads = discovery.discover_leads_for_company("CloudScale", "Senior Python Engineer")
    assert len(leads) >= 1
    assert "careers@cloudscale.com" in leads[0].email

    followup = FollowUpService()
    draft = followup.generate_followup_draft(
        job_title="Senior Python Engineer",
        company="CloudScale",
        applied_date="2026-09-20",
        candidate_name="Morgan Vance",
        key_skills=["Python", "FastAPI"]
    )
    assert "Senior Python Engineer" in draft["subject"]
    assert "Morgan Vance" in draft["body"]

    # 5. Mobile Quick-Action Companion Alert & Callback
    telegram = TelegramCompanionService()
    alert = telegram.format_intervention_alert(
        ticket_id="v2_test_ticket_1",
        job_title="Senior Python Engineer",
        company="CloudScale",
        question_text="Confirm expected salary",
        default_answer="$160,000"
    )
    assert "CloudScale" in alert["text"]
    assert alert["reply_markup"]["inline_keyboard"][0][0]["callback_data"] == "approve_v2_test_ticket_1"

    callback_res = await telegram.handle_callback_query("approve_v2_test_ticket_1")
    assert callback_res["success"] is True
    assert callback_res["action"] == "APPROVED"

    # 6. Conversion Funnel Analytics
    analytics = AnalyticsService()
    funnel = analytics.compute_funnel_summary()
    assert funnel.total_discovered >= 0
    assert len(funnel.stages) == 6

    roi = analytics.compute_platform_roi()
    assert len(roi) >= 3

    print("\n✓ Comprehensive V2 multi-subsystem integration lifecycle passed with 100% success.")
