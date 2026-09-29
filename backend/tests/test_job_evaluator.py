"""
Unit tests for JobEvaluator and Phase 3 hard disqualification logic.
"""

import pytest
from app.models.job import (
    ResumeProfile,
    WorkExperience,
    SearchConfig,
    DiscoveredJob,
    JobEvaluationResult
)
from app.services.match_scorer import match_scorer
from app.services.job_evaluator import job_evaluator, JobEvaluator


@pytest.fixture
def candidate_profile() -> ResumeProfile:
    return ResumeProfile(
        full_name="Syed Talha Ahmed",
        email="syedtalhaahmed004@gmail.com",
        phone="+91 81439 23984",
        location="Hyderabad, India",
        years_of_experience=2.0,
        summary="Full-Stack Developer experienced in React, TypeScript, Node.js, Express, and PostgreSQL.",
        skills=[
            "JavaScript", "TypeScript", "Python", "SQL", "React.js",
            "Node.js", "Express.js", "FastAPI", "PostgreSQL", "MongoDB"
        ],
        work_experience=[
            WorkExperience(
                title="Software Developer Associate",
                company="Invertio Software Solutions",
                location="Hyderabad, India"
            )
        ]
    )


def test_job_evaluator_eligible_high_match(candidate_profile):
    """Job matching candidate skills and clean criteria should be ELIGIBLE with APPLY action."""
    job = DiscoveredJob(
        job_id="JOB-101",
        platform="LinkedIn",
        title="Full Stack Developer (React / Node / PostgreSQL)",
        company="Global Tech Innovations",
        location="Hyderabad, India",
        is_remote=False,
        job_url="https://linkedin.com/jobs/view/101",
        description="""
        We are seeking a Full Stack Developer with 2-3 years of experience.
        Required Skills: React, Node, TypeScript, PostgreSQL.
        Salary: 12 - 18 LPA.
        Direct recruiter contact: priya.sharma@globaltech.com
        """
    )
    config = SearchConfig(min_match_score=60, match_gating_mode="enforce")
    eval_res: JobEvaluationResult = job_evaluator.evaluate_job(job, candidate_profile, config)

    assert eval_res.is_eligible is True
    assert eval_res.suggested_action == "APPLY"
    assert eval_res.match_score >= 70
    assert eval_res.quality_score >= 40
    assert eval_res.priority_score >= 50
    assert len(eval_res.contacts) > 0
    assert eval_res.hr_email == "priya.sharma@globaltech.com"
    assert len(eval_res.disqualification_reasons) == 0


def test_job_evaluator_excluded_company_disqualification(candidate_profile):
    """Excluded company should be immediately disqualified."""
    job = DiscoveredJob(
        job_id="JOB-102",
        platform="Naukri",
        title="Full Stack Developer",
        company="Spam Consultants Private Limited",
        location="Hyderabad, India",
        job_url="https://naukri.com/job/102",
        description="Looking for React, Node developer. Experience: 2 years."
    )
    config = SearchConfig(excluded_companies=["Spam Consultants", "Fake Agency"])
    eval_res = job_evaluator.evaluate_job(job, candidate_profile, config)

    assert eval_res.is_eligible is False
    assert eval_res.suggested_action == "SKIP"
    assert any("matches excluded company filter" in r for r in eval_res.disqualification_reasons)


def test_job_evaluator_excluded_keyword_disqualification(candidate_profile):
    """Excluded keywords (e.g. telecalling, unpaid) should trigger disqualification."""
    job = DiscoveredJob(
        job_id="JOB-103",
        platform="Indeed",
        title="Full Stack Developer / Telecalling Coordinator",
        company="SalesForce Pro",
        location="Hyderabad, India",
        job_url="https://indeed.com/job/103",
        description="""
        Requires candidate to do telecalling and cold outreach along with basic web work.
        Unpaid internship for first 3 months.
        """
    )
    config = SearchConfig(excluded_keywords=["telecalling", "unpaid internship"])
    eval_res = job_evaluator.evaluate_job(job, candidate_profile, config)

    assert eval_res.is_eligible is False
    assert eval_res.suggested_action == "SKIP"
    assert any("Excluded keyword" in r for r in eval_res.disqualification_reasons)


def test_job_evaluator_critical_risk_flag_disqualification(candidate_profile):
    """Jobs with severe scam risk flags (e.g. security deposit required) must be disqualified."""
    job = DiscoveredJob(
        job_id="JOB-104",
        platform="LinkedIn",
        title="React Developer",
        company="Shady Tech",
        location="Remote",
        is_remote=True,
        job_url="https://linkedin.com/jobs/view/104",
        description="""
        Great opportunity for React and Node developers.
        Selected candidates must submit a refundable laptop deposit of 10000 INR.
        """
    )
    config = SearchConfig()
    eval_res = job_evaluator.evaluate_job(job, candidate_profile, config)

    assert eval_res.is_eligible is False
    assert eval_res.suggested_action == "SKIP"
    assert "DEPOSIT_REQUIRED" in eval_res.risk_flags
    assert any("Critical risk flag 'DEPOSIT_REQUIRED'" in r for r in eval_res.disqualification_reasons)


def test_job_evaluator_remote_requirement_enforcement(candidate_profile):
    """When require_remote=True, strictly on-site jobs are disqualified."""
    job = DiscoveredJob(
        job_id="JOB-105",
        platform="Indeed",
        title="Frontend React Developer",
        company="Mumbai FinTech",
        location="Mumbai, Maharashtra",
        is_remote=False,
        job_url="https://indeed.com/job/105",
        description="Strictly on-site position in Mumbai. Office presence mandatory Monday to Friday."
    )
    config = SearchConfig(require_remote=True)
    eval_res = job_evaluator.evaluate_job(job, candidate_profile, config)

    assert eval_res.is_eligible is False
    assert eval_res.suggested_action == "SKIP"
    assert any("not remote" in r.lower() for r in eval_res.disqualification_reasons)


def test_job_evaluator_match_gating_modes(candidate_profile):
    """Compare observe mode (permits through) vs enforce mode (strictly gates)."""
    low_match_job = DiscoveredJob(
        job_id="JOB-106",
        platform="LinkedIn",
        title="Ruby on Rails Architect",
        company="Rails Corp",
        location="Remote",
        is_remote=True,
        job_url="https://linkedin.com/jobs/view/106",
        description="Ruby on Rails senior lead. Must have deep Elixir and Kubernetes knowledge."
    )

    # In observe mode: not hard-disqualified by match score alone
    config_observe = SearchConfig(min_match_score=70, match_gating_mode="observe")
    eval_observe = job_evaluator.evaluate_job(low_match_job, candidate_profile, config_observe)
    assert eval_observe.match_score < 70
    assert eval_observe.is_eligible is True

    # In enforce mode: strictly disqualified
    config_enforce = SearchConfig(min_match_score=70, match_gating_mode="enforce")
    eval_enforce = job_evaluator.evaluate_job(low_match_job, candidate_profile, config_enforce)
    assert eval_enforce.is_eligible is False
    assert eval_enforce.suggested_action == "SKIP"
    assert any("below required minimum threshold" in r for r in eval_enforce.disqualification_reasons)


def test_job_evaluator_experience_gap_disqualification(candidate_profile):
    """Job requiring 10+ years for a 2-year candidate exceeding max_experience_gap should be disqualified."""
    job = DiscoveredJob(
        job_id="JOB-107",
        platform="Naukri",
        title="Principal Software Architect",
        company="Enterprise Tech",
        location="Hyderabad, India",
        job_url="https://naukri.com/job/107",
        description="Requires at least 10+ years of software engineering experience."
    )
    config = SearchConfig(max_experience_gap=3.0)
    eval_res = job_evaluator.evaluate_job(job, candidate_profile, config)

    assert eval_res.is_eligible is False
    assert eval_res.suggested_action == "SKIP"
    assert any("exceeds candidate's experience" in r for r in eval_res.disqualification_reasons)


def test_job_evaluator_batch_and_ranking(candidate_profile):
    """Test evaluate_batch and filter_and_rank sorting."""
    job_good = DiscoveredJob(
        job_id="JOB-GOOD",
        platform="LinkedIn",
        title="Full Stack Developer (React, Node)",
        company="Good Co",
        location="Remote",
        is_remote=True,
        job_url="https://linkedin.com/jobs/view/good",
        description="React and Node developer. Experience: 2 years. Salary: 10 LPA."
    )
    job_bad = DiscoveredJob(
        job_id="JOB-BAD",
        platform="LinkedIn",
        title="Sales Telecalling Specialist",
        company="Bad Co",
        location="Remote",
        is_remote=True,
        job_url="https://linkedin.com/jobs/view/bad",
        description="Cold calling and lead gen."
    )

    config = SearchConfig(excluded_keywords=["telecalling"])
    ranked = job_evaluator.filter_and_rank([job_bad, job_good], candidate_profile, config)

    assert len(ranked) == 1
    assert ranked[0][0].job_id == "JOB-GOOD"
    assert ranked[0][1].is_eligible is True


def test_match_scorer_score_jobs_batch(candidate_profile):
    """Verify MatchScorer batch method works with diverse input types."""
    inputs = [
        ("React Developer", "Looking for React, TypeScript developer. 2 years exp."),
        {"title": "Backend Python", "description": "Python, FastAPI, SQL. 2 years exp."},
    ]
    batch_results = match_scorer.score_jobs_batch(inputs, candidate_profile, min_threshold=50)
    assert len(batch_results) == 2
    assert all(r.score > 0 for r in batch_results)
