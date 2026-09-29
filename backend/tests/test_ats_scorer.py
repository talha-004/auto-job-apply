"""
Unit Tests for Phase 18: ATS Keyword Gap Scorecard Engine.
Validates extraction of tech stack keywords from job descriptions,
scoring calculations, tier categorizations, and missing skill suggestions.
"""

import pytest
from app.models.job import ResumeProfile, WorkExperience, Education
from app.services.ats_scorer import ATSScorer, ATSScorecard, ats_scorer


@pytest.fixture
def sample_profile() -> ResumeProfile:
    return ResumeProfile(
        full_name="Alex Morgan",
        email="alex.morgan@example.com",
        phone="+1 555-019-2834",
        location="Austin, TX",
        github_url="https://github.com/alexmorgan",
        portfolio_url="https://alexmorgan.dev",
        years_of_experience=4.5,
        summary="Experienced Full-Stack Python and React Software Engineer specializing in PostgreSQL, Docker, and REST APIs.",
        skills=["Python", "FastAPI", "React", "PostgreSQL", "Docker", "Git", "REST"],
        work_experience=[
            WorkExperience(
                company="FinTech Core",
                title="Software Engineer",
                start_date="2022-01",
                end_date="Present",
                description="Engineered asynchronous backend microservices using Python, FastAPI, and PostgreSQL. Containerized internal microservices using Docker and orchestrated CI/CD pipelines. Built responsive frontend interfaces in React and TypeScript."
            )
        ],
        education=[
            Education(
                institution="University of Texas",
                degree="B.S. in Computer Science",
                graduation_year="2021"
            )
        ]
    )


def test_keyword_extraction_from_jd():
    scorer = ATSScorer()
    jd = """
    We are seeking a Senior Backend Engineer proficient in Python, PostgreSQL, Docker, and AWS.
    Experience with Redis, Kafka, and Kubernetes is strongly preferred.
    Must have experience building RESTful microservices.
    """
    kws = scorer.extract_keywords_from_jd(jd)
    assert "python" in kws
    assert "postgresql" in kws
    assert "docker" in kws
    assert "aws" in kws
    assert "redis" in kws
    assert "kafka" in kws
    assert "kubernetes" in kws
    assert "rest" in kws


def test_strong_match_evaluation(sample_profile: ResumeProfile):
    scorer = ATSScorer()
    jd = "Looking for a Python Developer experienced with FastAPI, React, PostgreSQL, and Docker."
    scorecard = scorer.evaluate_resume_ats_match(sample_profile, jd)

    assert scorecard.overall_score >= 80.0
    assert scorecard.tier in ("STRONG_MATCH", "COMPETITIVE_MATCH")
    assert "python" in scorecard.matched_keywords
    assert "fastapi" in scorecard.matched_keywords
    assert "docker" in scorecard.matched_keywords
    assert len(scorecard.missing_keywords) == 0


def test_missing_keywords_detection(sample_profile: ResumeProfile):
    scorer = ATSScorer()
    jd = "Senior Cloud Architect required with expertise in AWS, Kubernetes, Terraform, and Go."
    scorecard = scorer.evaluate_resume_ats_match(sample_profile, jd)

    assert scorecard.overall_score < 60.0
    assert "aws" in scorecard.missing_keywords or "kubernetes" in scorecard.missing_keywords
    assert len(scorecard.recommendations) > 0
    assert any("highlighting experience" in rec.lower() for rec in scorecard.recommendations)
