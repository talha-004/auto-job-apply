import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.services.policy_engine import (
    PolicyEngine,
    AutonomyMode,
    PolicyDecision,
    policy_engine,
)
from app.services.review_queue import review_queue

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_review_queue():
    review_queue.clear()
    policy_engine.mode = AutonomyMode.SUPERVISED
    yield
    review_queue.clear()
    policy_engine.mode = AutonomyMode.SUPERVISED


def test_assist_mode_always_requires_review():
    """Verify that in Assist mode, all applications are held for human confirmation."""
    engine = PolicyEngine(mode=AutonomyMode.ASSIST)
    eval_result = engine.evaluate_application(
        job_title="Frontend Engineer",
        company="Shopify",
        match_score=92.0,
        answers=[{"question": "Years with React?", "confidence": 1.0, "requires_human_intervention": False}],
    )
    assert eval_result.decision == PolicyDecision.REQUIRE_REVIEW
    assert "Assist Mode active" in eval_result.reasons[0]


def test_supervised_mode_allows_high_confidence():
    """Verify that Supervised mode auto-submits when all answers are high-confidence and non-sensitive."""
    engine = PolicyEngine(mode=AutonomyMode.SUPERVISED)
    eval_result = engine.evaluate_application(
        job_title="Backend Developer",
        company="Stripe",
        match_score=88.0,
        answers=[{"question": "Experience with Python APIs?", "confidence": 0.95, "requires_human_intervention": False}],
    )
    assert eval_result.decision == PolicyDecision.ALLOW


def test_supervised_mode_catches_sensitive_salary():
    """Verify that Supervised mode routes salary questions to the review queue."""
    engine = PolicyEngine(mode=AutonomyMode.SUPERVISED)
    eval_result = engine.evaluate_application(
        job_title="Software Architect",
        company="Netflix",
        match_score=90.0,
        answers=[{"question": "What is your desired compensation / CTC?", "confidence": 0.9, "requires_human_intervention": False}],
    )
    assert eval_result.decision == PolicyDecision.REQUIRE_REVIEW
    assert any("Sensitive screening questions detected" in r for r in eval_result.reasons)


def test_policy_blocks_blacklisted_company():
    """Verify that company blacklists immediately block application."""
    engine = PolicyEngine(mode=AutonomyMode.AUTONOMOUS)
    eval_result = engine.evaluate_application(
        job_title="Developer",
        company="Predatory Agency LLC",
        match_score=95.0,
        answers=[],
        blacklisted_companies=["Predatory Agency"],
    )
    assert eval_result.decision == PolicyDecision.BLOCK
    assert "blacklisted" in eval_result.reasons[0]


def test_review_queue_lifecycle_and_api():
    """Verify review queue enqueue, approve, reject, and API endpoints."""
    # 1. Enqueue an item
    item = review_queue.enqueue(
        job_title="Senior Rust Engineer",
        company="Cloudflare",
        platform="LinkedIn",
        job_url="https://linkedin.com/jobs/view/998877",
        match_score=85.0,
        answers=[{"question": "Desired CTC?", "answer": "$140,000"}],
    )
    assert item.status == "PENDING"

    # 2. Query pending via API
    res = client.get("/api/review/pending")
    assert res.status_code == 200
    pending_list = res.json()
    assert len(pending_list) == 1
    assert pending_list[0]["job_title"] == "Senior Rust Engineer"

    # 3. Approve via API
    approve_res = client.post(f"/api/review/approve/{item.review_id}")
    assert approve_res.status_code == 200

    # 4. Check queue is now empty
    res_after = client.get("/api/review/pending")
    assert len(res_after.json()) == 0

    # 5. Autonomy Mode API
    mode_res = client.get("/api/review/mode")
    assert mode_res.status_code == 200

    set_res = client.post("/api/review/mode/assist")
    assert set_res.status_code == 200
    assert set_res.json()["mode"] == "assist"
