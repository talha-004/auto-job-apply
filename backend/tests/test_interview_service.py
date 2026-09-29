import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from app.main import app
from app.services.interview_service import (
    InterviewPipelineService,
    interview_service,
    PostApplyStatus,
)

client = TestClient(app)


@pytest.fixture(autouse=True)
def cleanup_interview_service():
    interview_service._records.clear()
    yield
    interview_service._records.clear()


def test_lifecycle_status_transitions():
    """Verify that an application progresses cleanly across post-apply stages."""
    app_id = "app_1001"
    rec = interview_service.get_or_create(app_id)
    assert rec.current_status == PostApplyStatus.APPLIED

    # Transition to Viewed
    rec = interview_service.update_status(app_id, PostApplyStatus.VIEWED)
    assert rec.current_status == PostApplyStatus.VIEWED

    # Transition to Screening
    rec = interview_service.update_status(app_id, PostApplyStatus.SCREENING)
    assert rec.current_status == PostApplyStatus.SCREENING


def test_interview_scheduling_and_offer():
    """Verify scheduling multiple interview rounds and recording final offers."""
    app_id = "app_1002"

    # Schedule Round 1 (Technical)
    r1 = interview_service.schedule_interview(
        application_id=app_id,
        round_type="Technical",
        interviewer_name="Sarah Connor",
        meeting_link="https://meet.google.com/abc-xyz",
        notes="Live coding session in Python."
    )
    assert r1.round_number == 1
    assert r1.round_type == "Technical"

    rec = interview_service.get_or_create(app_id)
    assert rec.current_status == PostApplyStatus.INTERVIEW_SCHEDULED
    assert len(rec.interviews) == 1

    # Schedule Round 2 (System Design)
    r2 = interview_service.schedule_interview(
        application_id=app_id,
        round_type="System Design",
        interviewer_name="John Doe"
    )
    assert r2.round_number == 2
    assert len(rec.interviews) == 2

    # Record Offer
    rec = interview_service.record_offer(app_id, "$150,000 / year")
    assert rec.current_status == PostApplyStatus.OFFER_RECEIVED
    assert rec.offer_salary == "$150,000 / year"


def test_interview_api_endpoints():
    """Verify interview REST API endpoints."""
    app_id = "app_api_test"

    # 1. Update status
    res = client.post(
        f"/api/interview/{app_id}/status",
        json={"status": "Screening", "notes": "HR Phone Screen scheduled"}
    )
    assert res.status_code == 200
    assert res.json()["current_status"] == "Screening"

    # 2. Schedule interview via API
    sched_res = client.post(
        f"/api/interview/{app_id}/schedule",
        json={
            "round_type": "Recruiter Screen",
            "interviewer_name=" : "Alice Smith",
            "meeting_link": "https://zoom.us/j/12345"
        }
    )
    assert sched_res.status_code == 200
    assert sched_res.json()["round_number"] == 1

    # 3. Record Offer via API
    offer_res = client.post(
        f"/api/interview/{app_id}/offer",
        json={"salary_amount": "₹28 LPA"}
    )
    assert offer_res.status_code == 200
    assert offer_res.json()["current_status"] == "Offer Received"

    # 4. Pipeline metrics
    metrics_res = client.get("/api/interview/metrics")
    assert metrics_res.status_code == 200
    metrics = metrics_res.json()
    assert metrics["Offer Received"] == 1
