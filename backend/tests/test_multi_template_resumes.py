"""
Unit Tests for Phase 18: Multi-Template Resume Engine.
Validates PDF resume generation across CLASSIC_ATS, TECH_MINIMALIST,
and COMPACT_ONE_PAGE templates with ATS scorecards and zero fabrication.
"""

import os
from pathlib import Path
import pytest

from app.models.job import ResumeProfile, WorkExperience, Education
from app.services.resume_tailorer import ResumeTailorer, TemplateType


@pytest.fixture
def sample_profile() -> ResumeProfile:
    return ResumeProfile(
        full_name="Jordan Reed",
        email="jordan.reed@example.com",
        phone="+1 555-876-5432",
        location="Seattle, WA",
        github_url="https://github.com/jordanreed",
        portfolio_url="https://jordanreed.io",
        years_of_experience=3.0,
        summary="Software Engineer specializing in modern cloud backends with Python, FastAPI, and PostgreSQL.",
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "AWS", "Git"],
        work_experience=[
            WorkExperience(
                company="CloudScale Systems",
                title="Software Engineer",
                start_date="2023-01",
                end_date="Present",
                description="Engineered cloud microservices processing 1M daily requests using Python and FastAPI. Optimized PostgreSQL queries reducing average response latency by 35%."
            )
        ],
        education=[
            Education(
                institution="University of Washington",
                degree="B.S. Computer Science",
                graduation_year="2022"
            )
        ]
    )


def test_classic_ats_template_generation(tmp_path: Path, sample_profile: ResumeProfile):
    tailorer = ResumeTailorer(storage_dir=tmp_path)
    jd = "Seeking Python Engineer with PostgreSQL and Docker experience."
    res = tailorer.generate_tailored_resume(
        profile=sample_profile,
        job_title="Python Engineer",
        jd_text=jd,
        job_id="test_classic_101",
        template=TemplateType.CLASSIC_ATS
    )

    assert os.path.exists(res.pdf_path)
    assert res.file_size_bytes > 1000
    assert res.template_used == "classic_ats"
    assert res.ats_score is not None
    assert res.ats_tier in ("STRONG_MATCH", "COMPETITIVE_MATCH")


def test_tech_minimalist_template_generation(tmp_path: Path, sample_profile: ResumeProfile):
    tailorer = ResumeTailorer(storage_dir=tmp_path)
    jd = "Seeking Full-Stack Python Engineer with AWS experience."
    res = tailorer.generate_tailored_resume(
        profile=sample_profile,
        job_title="Full-Stack Engineer",
        jd_text=jd,
        job_id="test_tech_102",
        template=TemplateType.TECH_MINIMALIST
    )

    assert os.path.exists(res.pdf_path)
    assert res.file_size_bytes > 1000
    assert res.template_used == "tech_minimalist"
    assert res.ats_score is not None


def test_compact_one_page_template_generation(tmp_path: Path, sample_profile: ResumeProfile):
    tailorer = ResumeTailorer(storage_dir=tmp_path)
    jd = "Seeking Backend Engineer with FastAPI and Docker experience."
    res = tailorer.generate_tailored_resume(
        profile=sample_profile,
        job_title="Backend Engineer",
        jd_text=jd,
        job_id="test_compact_103",
        template=TemplateType.COMPACT_ONE_PAGE
    )

    assert os.path.exists(res.pdf_path)
    assert res.file_size_bytes > 1000
    assert res.template_used == "compact_one_page"
    assert res.ats_score is not None
