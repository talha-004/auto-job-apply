"""
Unit Tests for Phase 11 (Pillar 2): AI Mock Interview Preparation Coach.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.fact_ledger import CandidateFact, FactCategory
from app.services.fact_ledger import fact_ledger_service
from app.services.interview_coach import interview_coach_service


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def setup_candidate_facts():
    fact_ledger_service.ledger.facts.clear()
    fact_ledger_service.add_fact(
        CandidateFact(
            fact_id="fact_python_1",
            category=FactCategory.TECHNICAL_SKILL,
            subject="Python",
            value="4 years of asynchronous development with FastAPI",
            verified_by_user=True,
            source_document="test_resume.pdf"
        )
    )
    fact_ledger_service.add_fact(
        CandidateFact(
            fact_id="fact_k8s_1",
            category=FactCategory.TECHNICAL_SKILL,
            subject="Docker & Kubernetes",
            value="Containerized microservices running on EKS",
            verified_by_user=True,
            source_document="test_resume.pdf"
        )
    )


@pytest.mark.asyncio
async def test_generate_interview_prep_package():
    pkg = await interview_coach_service.generate_prep_package(
        job_id="test_job_stripe",
        job_title="Staff Backend Engineer",
        company="Stripe",
        job_description="Looking for distributed systems engineer experienced in high-throughput payments and API design."
    )

    assert pkg.job_id == "test_job_stripe"
    assert pkg.company == "Stripe"
    assert len(pkg.dossier.suggested_questions_to_ask) >= 3
    assert len(pkg.technical_questions) >= 3

    # Verify expected technical fields
    q1 = pkg.technical_questions[0]
    assert q1.question != ""
    assert len(q1.expected_concepts) > 0
    assert q1.sample_answer_outline != ""

    # Verify STAR stories
    assert len(pkg.behavioral_stories) >= 1
    s1 = pkg.behavioral_stories[0]
    assert s1.situation != ""
    assert s1.action != ""
    assert s1.result != ""


@pytest.mark.asyncio
async def test_evaluate_practice_response():
    question = "How do you ensure high availability and graceful degradation in distributed APIs?"
    user_answer = (
        "In our payments architecture, we implemented circuit breakers and Redis caching. "
        "When downstream microservices timed out, the system fell back to a cached idempotent response. "
        "This led to a 99.99% uptime metric during peak shopping hours."
    )
    expected_concepts = ["Circuit breakers", "Redis caching", "Graceful degradation"]

    feedback = await interview_coach_service.evaluate_practice_response(
        question=question,
        user_answer=user_answer,
        expected_concepts=expected_concepts
    )

    assert feedback.score >= 7
    assert len(feedback.strengths) >= 1
    assert any("Circuit breakers" in s or "Redis caching" in s for s in feedback.strengths)
    assert feedback.sample_polished_answer != ""


def test_interview_coach_api_endpoints(client: TestClient):
    # Test generation endpoint
    gen_resp = client.post(
        "/api/interview-coach/generate",
        json={
            "job_id": "api_test_meta",
            "job_title": "Production Engineer",
            "company": "Meta",
            "job_description": "Linux systems, high availability, kernel tuning"
        }
    )
    assert gen_resp.status_code == 200
    data = gen_resp.json()
    assert data["company"] == "Meta"
    assert len(data["technical_questions"]) >= 3

    # Test practice evaluation endpoint
    eval_resp = client.post(
        "/api/interview-coach/practice/evaluate",
        json={
            "question": "Explain database indexing trade-offs",
            "user_answer": "Indexes speed up read queries using B-Trees, but they increase write latency and storage overhead.",
            "expected_concepts": ["B-Trees", "Write overhead"]
        }
    )
    assert eval_resp.status_code == 200
    eval_data = eval_resp.json()
    assert eval_data["score"] >= 6
    assert len(eval_data["strengths"]) >= 1
