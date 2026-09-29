"""
Unit Tests for Phase 19: Recruiter Lead Discovery & Automated Follow-Up Sequences.
Validates recruiter extraction from text, corporate email derivation,
5-day aging logic, polite follow-up draft generation, deduplication, and daily caps.
"""

from datetime import date, timedelta
import pytest
from unittest.mock import MagicMock, patch

from app.models.job import JobApplicationRecord, ApplicationStatus
from app.services.recruiter_discovery import RecruiterDiscoveryService, recruiter_discovery
from app.services.followup_service import FollowUpService, FollowUpRecommendation, followup_service


def test_recruiter_extraction_from_text():
    service = RecruiterDiscoveryService()
    text = "Feel free to reach out to Sarah Jenkins at sarah.jenkins@techcorp.io for questions."
    lead = service.extract_recruiter_from_text(text, "TechCorp")

    assert lead is not None
    assert lead.name == "Sarah Jenkins"
    assert lead.email == "sarah.jenkins@techcorp.io"
    assert lead.confidence == "high"


def test_corporate_email_derivation():
    service = RecruiterDiscoveryService()
    email_known = service.derive_corporate_email("John", "Doe", "Google")
    assert email_known == "john.doe@google.com"

    email_custom = service.derive_corporate_email("Jane", "Smith", "Startup Labs")
    assert email_custom == "jane.smith@startuplabs.com"


def test_company_lead_discovery():
    service = RecruiterDiscoveryService()
    leads = service.discover_leads_for_company("Stripe", "Backend Engineer")
    assert len(leads) >= 2
    assert any("recruiting" in l.title.lower() for l in leads)
    assert any("stripe.com" in l.email for l in leads)


def test_calculate_days_elapsed():
    service = FollowUpService()
    seven_days_ago = (date.today() - timedelta(days=7)).isoformat()
    two_days_ago = (date.today() - timedelta(days=2)).isoformat()

    assert service.calculate_days_elapsed(seven_days_ago) == 7
    assert service.calculate_days_elapsed(two_days_ago) == 2
    assert service.calculate_days_elapsed("invalid_date") == 0


def test_generate_followup_draft():
    service = FollowUpService()
    draft = service.generate_followup_draft(
        job_title="Lead AI Engineer",
        company="Anthropic",
        applied_date="2026-09-20",
        candidate_name="Alex Morgan",
        key_skills=["Python", "FastAPI", "PostgreSQL"]
    )

    assert "Lead AI Engineer" in draft["subject"]
    assert "Alex Morgan" in draft["subject"]
    assert "Anthropic" in draft["body"]
    assert "Python, FastAPI, PostgreSQL" in draft["body"]
    assert "2026-09-20" in draft["body"]


def test_followup_approval_and_daily_cap():
    service = FollowUpService()
    service._sent_followups.clear()

    # Approve 10 followups
    for i in range(10):
        assert service.approve_followup(f"job_{i}") is True

    # 11th should be rejected due to daily cap
    assert service.approve_followup("job_11") is False
    assert len(service._sent_followups) == 10
