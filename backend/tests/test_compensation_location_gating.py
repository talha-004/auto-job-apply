import pytest
from app.models.job import SearchConfig, DiscoveredJob, ResumeProfile
from app.services.job_evaluator import job_evaluator, parse_salary_text
from app.services.policy_engine import policy_engine, PolicyDecision, AutonomyMode, PolicyEngine


def test_parse_salary_text():
    # LPA formats
    r1 = parse_salary_text("12 - 18 LPA")
    assert r1["min_salary"] == 12.0
    assert r1["max_salary"] == 18.0
    assert r1["currency"] == "INR"
    assert r1["period"] == "LPA"

    r2 = parse_salary_text("15 Lacs P.A.")
    assert r2["min_salary"] == 15.0
    assert r2["max_salary"] == 15.0

    r3 = parse_salary_text("₹ 14,00,000 - 20,00,000 P.A.")
    assert r3["min_salary"] == 14.0
    assert r3["max_salary"] == 20.0
    assert r3["period"] == "LPA"

    # USD formats
    r4 = parse_salary_text("$120k - $160k")
    assert r4["min_salary"] == 120000.0
    assert r4["max_salary"] == 160000.0
    assert r4["currency"] == "USD"

    r5 = parse_salary_text("$50 - $75 an hour")
    assert r5["min_salary"] == 50.0
    assert r5["max_salary"] == 75.0
    assert r5["period"] == "HOURLY"


def test_job_evaluator_compensation_gating():
    profile = ResumeProfile(
        full_name="Test Candidate",
        skills=["Python", "FastAPI", "React", "PostgreSQL"],
        years_of_experience=4
    )

    # Low salary with strict enforcement -> Hard Disqualified
    config_strict = SearchConfig(
        min_salary=15.0,
        salary_currency="INR",
        strict_salary_enforcement=True
    )
    job_low_salary = DiscoveredJob(
        job_id="job-1",
        platform="Naukri",
        title="Full Stack Python Developer",
        company="TechCorp",
        location="Remote",
        job_url="https://example.com/job1",
        description="Looking for Python FastAPI React developer. Salary: 8 - 12 LPA.",
        raw_metadata={"salary": "8 - 12 LPA"}
    )

    res_strict = job_evaluator.evaluate_job(job_low_salary, profile, config_strict)
    assert not res_strict.is_eligible
    assert any("below minimum expected floor" in r for r in res_strict.disqualification_reasons)
    assert res_strict.suggested_action == "SKIP"

    # Higher salary -> Eligible
    job_high_salary = DiscoveredJob(
        job_id="job-2",
        platform="Naukri",
        title="Senior Python FastAPI Developer",
        company="HighPayTech",
        location="Remote",
        job_url="https://example.com/job2",
        description="Looking for Python FastAPI React developer. Salary: 18 - 25 LPA.",
        raw_metadata={"salary": "18 - 25 LPA"}
    )
    res_high = job_evaluator.evaluate_job(job_high_salary, profile, config_strict)
    assert res_high.is_eligible
    assert res_high.suggested_action == "APPLY"


def test_job_evaluator_location_gating():
    profile = ResumeProfile(
        full_name="Test Candidate",
        skills=["Python", "FastAPI", "React"],
        years_of_experience=4
    )

    config_location = SearchConfig(
        prohibited_locations=["Kolkata", "Chennai"],
        allowed_locations=["Bengaluru", "Hyderabad", "Pune"],
        strict_location_enforcement=True
    )

    # Job in prohibited location
    job_prohibited = DiscoveredJob(
        job_id="job-p",
        platform="LinkedIn",
        title="Software Engineer",
        company="EastCoast Co",
        location="Chennai, Tamil Nadu, India",
        job_url="https://example.com/jobp",
        description="Onsite developer needed."
    )
    res_p = job_evaluator.evaluate_job(job_prohibited, profile, config_location)
    assert not res_p.is_eligible
    assert any("prohibited locations filter" in r for r in res_p.disqualification_reasons)

    # Job outside allowed location
    job_outside = DiscoveredJob(
        job_id="job-o",
        platform="LinkedIn",
        title="Software Engineer",
        company="NorthCo",
        location="Gurgaon, Haryana, India",
        job_url="https://example.com/jobo",
        description="Onsite role in Gurgaon."
    )
    res_o = job_evaluator.evaluate_job(job_outside, profile, config_location)
    assert not res_o.is_eligible
    assert any("outside permitted locations" in r for r in res_o.disqualification_reasons)

    # Job in allowed location
    job_allowed = DiscoveredJob(
        job_id="job-a",
        platform="LinkedIn",
        title="Software Engineer",
        company="Bangalore Tech",
        location="Bengaluru, Karnataka, India",
        job_url="https://example.com/joba",
        description="Onsite or hybrid role in Bengaluru."
    )
    res_a = job_evaluator.evaluate_job(job_allowed, profile, config_location)
    assert res_a.is_eligible


def test_policy_engine_compensation_and_location():
    engine = PolicyEngine(mode=AutonomyMode.AUTONOMOUS)

    # Prohibited location -> BLOCK
    eval_loc = engine.evaluate_application(
        job_title="Dev",
        company="Acme",
        match_score=85.0,
        answers=[],
        location="Kolkata",
        prohibited_locations=["Kolkata", "Jaipur"]
    )
    assert eval_loc.decision == PolicyDecision.BLOCK

    # Salary below floor -> BLOCK
    eval_sal = engine.evaluate_application(
        job_title="Dev",
        company="Acme",
        match_score=85.0,
        answers=[],
        salary_max=10.0,
        min_salary_floor=15.0
    )
    assert eval_sal.decision == PolicyDecision.BLOCK
