"""
Unit Tests for Phase 21: Conversion Funnel Analytics & Performance Dashboard.
Validates stage-by-stage funnel calculation, platform ROI computation,
conversion rates, and API endpoint responses.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.job import JobApplicationRecord, ApplicationStatus, PlatformEnum
from app.services.analytics_service import AnalyticsService, analytics_service
from app.services.persistence_service import persistence_service


@pytest.fixture
def client():
    return TestClient(app)


def test_funnel_summary_computation():
    service = AnalyticsService()
    summary = service.compute_funnel_summary()

    assert summary.total_discovered >= summary.total_applied
    assert summary.total_evaluated >= summary.total_applied
    assert len(summary.stages) == 6
    assert summary.applied_to_interview_rate_pct >= 0.0

    # Check stage ordering
    stage_names = [s.stage for s in summary.stages]
    assert any("Discovered" in name for name in stage_names)
    assert any("Submitted" in name for name in stage_names)
    assert any("Interviews" in name for name in stage_names)


def test_platform_roi_computation():
    service = AnalyticsService()
    roi = service.compute_platform_roi()

    assert len(roi) >= 3
    platform_names = [p.platform for p in roi]
    assert "LinkedIn" in platform_names
    assert "Indeed" in platform_names
    assert "Naukri" in platform_names

    for p in roi:
        assert p.applications_count >= 0
        assert p.interviews_count >= 0
        assert 0.0 <= p.conversion_rate_pct <= 100.0


def test_analytics_api_endpoints(client: TestClient):
    # Funnel endpoint
    f_resp = client.get("/api/analytics/funnel")
    assert f_resp.status_code == 200
    f_data = f_resp.json()
    assert "total_applied" in f_data
    assert "stages" in f_data

    # Platform ROI endpoint
    roi_resp = client.get("/api/analytics/platform-roi")
    assert roi_resp.status_code == 200
    assert "platforms" in roi_resp.json()

    # Summary endpoint
    sum_resp = client.get("/api/analytics/summary")
    assert sum_resp.status_code == 200
    s_data = sum_resp.json()
    assert "total_applications" in s_data
    assert "interview_rate_pct" in s_data
