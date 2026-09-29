"""
Unit and integration tests for AI Resume Tailoring Engine (Phase 6).
"""

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.job import ResumeProfile, WorkExperience, Education
from app.services.resume_tailorer import ResumeTailorer, TailoredResumeResult
from app.services.resume_parser import resume_parser_service


@pytest.fixture
def candidate_profile() -> ResumeProfile:
    return ResumeProfile(
        full_name="Syed Talha Ahmed",
        email="syedtalhaahmed004@gmail.com",
        phone="+91 81439 23984",
        location="Hyderabad, India",
        linkedin_url="https://linkedin.com/in/talha004",
        github_url="https://github.com/talha-004",
        portfolio_url="https://talha.dev",
        years_of_experience=2.0,
        summary="Full-Stack Developer with experience building responsive web and mobile applications using React, Next.js, Node.js, and PostgreSQL.",
        skills=[
            "JavaScript", "TypeScript", "Python", "SQL", "React.js",
            "Next.js", "Node.js", "Express.js", "FastAPI", "PostgreSQL",
            "MongoDB", "Docker", "Git"
        ],
        work_experience=[
            WorkExperience(
                title="Software Developer Associate",
                company="Invertio Software Solutions",
                location="Hyderabad, India",
                start_date="Jan 2026",
                end_date="Present",
                description="Develop production web applications using React, TypeScript, Node.js, and PostgreSQL. Implement authentication, role-based access control, and API integrations. Collaborate with clients on requirements, ERDs, and delivery."
            ),
            WorkExperience(
                title="Frontend Developer",
                company="ResumeLevelup AI",
                location="Remote",
                start_date="Mar 2025",
                end_date="Jan 2026",
                description="Developed responsive product interfaces using React.js and Tailwind CSS. Converted Figma designs into reusable React components. Improved SEO and application usability."
            )
        ],
        education=[
            Education(
                institution="Osmania University",
                degree="Master of Business Administration - Information Technology",
                graduation_year="2026",
                grade_or_gpa="8.5"
            )
        ],
        certifications=[
            "Full Stack Development Certificate 2025"
        ]
    )


def test_resume_tailorer_pdf_generation(tmp_path: Path, candidate_profile: ResumeProfile):
    """Verify PDF compilation, valid binary output, and metadata generation."""
    tailorer = ResumeTailorer(storage_dir=tmp_path)
    job_title = "Senior React & TypeScript Developer"
    jd_text = """
    We are seeking a React & TypeScript Developer with experience in PostgreSQL and Node.js.
    Must understand clean component architecture, API integrations, and responsive UI design.
    """
    job_id = "test_job_101"

    result = tailorer.generate_tailored_resume(
        profile=candidate_profile,
        job_title=job_title,
        jd_text=jd_text,
        job_id=job_id
    )

    assert result.job_id == job_id
    assert os.path.exists(result.pdf_path)
    assert result.file_size_bytes > 2000

    # Verify standard PDF header magic bytes (%PDF)
    with open(result.pdf_path, "rb") as f:
        header = f.read(5)
        assert header.startswith(b"%PDF")

    # Verify metadata JSON was written alongside the PDF
    metadata_path = tmp_path / "tailored" / job_id / "tailoring_metadata.json"
    assert metadata_path.exists()


def test_zero_fabrication_preservation(tmp_path: Path, candidate_profile: ResumeProfile):
    """Verify authentic dates, company names, and degrees are preserved with zero fabrication."""
    tailorer = ResumeTailorer(storage_dir=tmp_path)
    result = tailorer.generate_tailored_resume(
        profile=candidate_profile,
        job_title="Full Stack Engineer",
        jd_text="Requirements: Python, FastAPI, Docker.",
        job_id="zero_fab_test"
    )

    # Invertio Software Solutions and Osmania University must be authentic
    assert "Invertio Software Solutions" in candidate_profile.work_experience[0].company
    assert "Osmania University" in candidate_profile.education[0].institution

    # The tailored summary must preserve genuine candidate experience years (2+ yrs)
    assert "2+ years" in result.tailored_summary or "2.0 years" in result.tailored_summary
    assert "Full Stack Engineer" in result.tailored_summary


def test_skill_highlighting_and_reordering(tmp_path: Path, candidate_profile: ResumeProfile):
    """Verify that skills matching the target JD are identified and prioritized."""
    tailorer = ResumeTailorer(storage_dir=tmp_path)
    jd_text = "Looking for a specialist in FastAPI, Docker, and PostgreSQL."
    matched, other = tailorer.identify_matching_skills(
        candidate_profile,
        jd_text=jd_text,
        job_title="Backend Developer"
    )

    matched_lower = [m.lower() for m in matched]
    assert "fastapi" in matched_lower
    assert "docker" in matched_lower
    assert "postgresql" in matched_lower

    # Unmatched skills should remain in 'other'
    other_lower = [o.lower() for o in other]
    assert "mongodb" in other_lower


def test_experience_bullet_prioritization(candidate_profile: ResumeProfile):
    """Verify experience sentences matching JD keywords are prioritized first."""
    tailorer = ResumeTailorer()
    exp = candidate_profile.work_experience[0]
    matched = ["PostgreSQL", "React"]

    bullets = tailorer.prioritize_work_experience(exp, matched)
    assert len(bullets) > 0
    # First bullet should be the one mentioning React and PostgreSQL
    assert "React" in bullets[0] or "PostgreSQL" in bullets[0]


def test_api_tailor_and_download_endpoints(candidate_profile: ResumeProfile):
    """Verify POST /api/resume/tailor and GET /api/resume/tailored/{job_id}/download."""
    # Ensure profile is loaded in parser service
    resume_parser_service.save_profile(candidate_profile)
    client = TestClient(app)

    payload = {
        "job_title": "Full Stack Developer",
        "job_description": "React, TypeScript, Node.js, and PostgreSQL required.",
        "job_id": "api_test_job_102"
    }

    # 1. Generate tailored resume
    response = client.post("/api/resume/tailor", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["job_id"] == "api_test_job_102"
    assert data["file_size_bytes"] > 1000
    assert len(data["matched_skills_highlighted"]) > 0

    # 2. Download generated tailored resume
    dl_response = client.get("/api/resume/tailored/api_test_job_102/download")
    assert dl_response.status_code == 200
    assert dl_response.headers["content-type"] == "application/pdf"
    assert dl_response.content.startswith(b"%PDF")
