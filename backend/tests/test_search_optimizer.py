"""
Unit Tests for SearchOptimizerService & Search Intelligence.
Validates multi-query expansion, boolean query construction, platform-specific URL generation,
title relevance and negative keyword gating, and search yield telemetry.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.discovery.search_optimizer import search_optimizer


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def cleanup():
    search_optimizer.clear()
    yield
    search_optimizer.clear()


def test_expand_queries():
    # Test known dictionary role
    py_expansions = search_optimizer.expand_queries("Python Developer", max_variations=3)
    assert len(py_expansions) >= 2
    assert py_expansions[0] == "Python Developer"
    assert any("Engineer" in q or "Backend" in q for q in py_expansions[1:])

    # Test heuristic fallback role
    custom_expansions = search_optimizer.expand_queries("Solidity Developer", max_variations=2)
    assert custom_expansions[0] == "Solidity Developer"
    assert len(custom_expansions) >= 2


def test_build_boolean_search():
    bool_query = search_optimizer.build_boolean_search(
        keywords="Python Developer",
        negative_keywords=["Intern", "Director"],
        required_skills=["FastAPI", "PostgreSQL"]
    )

    assert "Python Developer" in bool_query
    assert "OR" in bool_query
    assert "AND" in bool_query
    assert "NOT" in bool_query
    assert "Intern" in bool_query
    assert "FastAPI" in bool_query


def test_build_platform_search_urls():
    # LinkedIn
    li_url = search_optimizer.build_platform_search_url(
        platform="linkedin",
        keywords="Python Engineer",
        location="Bangalore",
        is_remote=True,
        hours_old=48,
        experience_level="mid"
    )
    assert "linkedin.com/jobs/search" in li_url
    assert "Python+Engineer" in li_url
    assert "f_TPR=r172800" in li_url  # 48h in seconds
    assert "f_WT=2" in li_url
    assert "f_E=3,4" in li_url

    # Indeed
    indeed_url = search_optimizer.build_platform_search_url(
        platform="indeed",
        keywords="Full Stack",
        location="India",
        is_remote=True,
        hours_old=72
    )
    assert "indeed.com/jobs" in indeed_url
    assert "fromage=3" in indeed_url
    assert "attr%28DSIDE%29" in indeed_url

    # Naukri
    naukri_url = search_optimizer.build_platform_search_url(
        platform="naukri",
        keywords="Data Engineer",
        location="Hyderabad",
        is_remote=False,
        hours_old=24
    )
    assert "naukri.com/data-engineer-jobs-in-hyderabad" in naukri_url
    assert "glbl_qc_job_age=1" in naukri_url


def test_filter_title_relevance():
    # Negative keyword rejections
    is_rel, reason = search_optimizer.filter_title_relevance(
        title="Software Engineering Intern",
        target_query="Python Developer"
    )
    assert is_rel is False
    assert "negative keyword" in reason.lower()

    is_rel, reason = search_optimizer.filter_title_relevance(
        title="Director of Engineering",
        target_query="Backend Engineer"
    )
    assert is_rel is False
    assert "negative keyword" in reason.lower()

    # Positive relevance matches
    is_rel, reason = search_optimizer.filter_title_relevance(
        title="Senior Python Backend Engineer",
        target_query="Python Developer"
    )
    assert is_rel is True
    assert "relevant" in reason.lower()

    is_rel, reason = search_optimizer.filter_title_relevance(
        title="Full Stack Software Engineer (React / Python)",
        target_query="Full Stack Developer"
    )
    assert is_rel is True

    # Completely unrelated title rejection
    is_rel, reason = search_optimizer.filter_title_relevance(
        title="Registered Dental Nurse",
        target_query="Python Developer"
    )
    assert is_rel is False
    assert "zero semantic overlap" in reason.lower()


def test_telemetry_recording_and_yield():
    telemetry = search_optimizer.record_telemetry(
        base_query="Python Developer",
        expanded_queries=["Python Developer", "Python Engineer"],
        location="Remote",
        total_scraped=50,
        relevance_filtered=15,
        duplicates_skipped=10,
        fresh_eligible=25
    )

    assert telemetry.total_scraped == 50
    assert telemetry.fresh_eligible == 25
    assert telemetry.yield_rate_pct == 50.0

    recent = search_optimizer.get_recent_telemetry(limit=5)
    assert len(recent) == 1
    assert recent[0].base_query == "Python Developer"


def test_search_api_endpoints(client: TestClient):
    # Preview search expansion endpoint
    expand_resp = client.get("/api/bot/search/expand?keywords=React%20Developer&location=Remote&is_remote=true")
    assert expand_resp.status_code == 200
    expand_data = expand_resp.json()
    assert expand_data["base_query"] == "React Developer"
    assert len(expand_data["expanded_queries"]) >= 1
    assert "linkedin" in expand_data["platform_urls"]
    assert "indeed" in expand_data["platform_urls"]

    # Telemetry endpoint
    # First record one entry
    search_optimizer.record_telemetry(
        base_query="DevOps Engineer",
        expanded_queries=["DevOps Engineer"],
        location="India",
        total_scraped=20,
        relevance_filtered=2,
        duplicates_skipped=3,
        fresh_eligible=15
    )

    tel_resp = client.get("/api/bot/search/telemetry?limit=5")
    assert tel_resp.status_code == 200
    tel_data = tel_resp.json()
    assert len(tel_data) == 1
    assert tel_data[0]["base_query"] == "DevOps Engineer"
    assert tel_data[0]["yield_rate_pct"] == 75.0
