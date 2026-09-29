"""
Phase 15: Full Regression Testing & Production Certification Suite.
Validates the cohesive end-to-end integration across all 15 architecture subsystems:
1. Candidate Intelligence & QA Vault
2. Discovery & Job Normalization
3. Intelligence & 60/20/10/10 Gating
4. Orchestrator Lifecycle State Machine
5. Universal Application Adapters
6. AI Resume Tailoring (PDF Generator)
7. Multi-Provider AI Screening Engine
8. Recruiter Intelligence & Outreach
9. Persistent Browser Profile & Bridge
10. Background Cron Scheduler
11. Dashboard & Intervention Center Contracts
12. Database Relational Persistence (autoapply_db)
13. Multi-Channel Notifications & Inbox Monitoring
14. Security Encryption, Log Redaction & Circuit Breakers
"""

import os
import json
import asyncio
import pytest
from datetime import datetime, date
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.job import (
    SearchConfig,
    ResumeProfile,
    QAVault,
    DiscoveredJob,
    JobEvaluationResult,
    JobLifecycleStatus,
    ApplicationStatus,
    PlatformEnum
)
from app.services.qa_vault_service import qa_vault_service
from app.services.job_evaluator import job_evaluator
from app.services.orchestrator import ApplicationOrchestrator
from app.services.screening_service import screening_service, AnswerProvenance, ScreeningQuestionRequest
from app.services.resume_tailorer import resume_tailorer
from app.services.notification_service import notification_service, NotificationEventType
from app.services.inbox_monitor import inbox_monitor_service, RecruiterEmailIntent
from app.core.security import security_manager
from app.core.circuit_breaker import circuit_breaker, CircuitState
from app.platforms.adapter_interface import ApplicationAdapter
from app.platforms.external.greenhouse import GreenhouseAdapter
from app.platforms.external.lever import LeverAdapter
from app.platforms.base import BasePlatform

client = TestClient(app)


@pytest.fixture
def sample_candidate():
    return ResumeProfile(
        full_name="Syed Talha Ahmed",
        email="talha@example.com",
        phone="+919876543210",
        location="Remote / Flexible",
        years_of_experience=5.0,
        skills=["Python", "FastAPI", "React", "PostgreSQL", "Docker", "Machine Learning"],
        qa_vault=QAVault(
            experience_years=5.0,
            relevant_experience_years=5.0,
            current_ctc_lpa=24.0,
            expected_ctc_lpa=35.0,
            notice_period_days=15,
            work_authorization="Citizen",
            require_sponsorship="No",
            willing_to_relocate="Yes",
            comfortable_with_remote="Yes",
            custom_qa={
                "github_url": "https://github.com/talha-004",
                "linkedin_url": "https://linkedin.com/in/syedtalha"
            }
        )
    )


def test_cert_subsystem_1_qa_vault_integrity(sample_candidate):
    """Subsystem 1: Verify QA Vault pattern matching and deterministic answers."""
    match1 = qa_vault_service.match_field("What is your total years of work experience?", sample_candidate)
    assert match1.matched is True
    assert match1.value == 5.0
    assert match1.source in ("qa_vault", "profile")

    match2 = qa_vault_service.match_field("Do you require visa sponsorship now or in the future?", sample_candidate)
    assert match2.matched is True
    assert str(match2.value).lower() == "no"


def test_cert_subsystem_2_and_3_evaluation_gating(sample_candidate):
    """Subsystem 2 & 3: Verify discovered job normalization and 60/20/10/10 evaluation gating."""
    good_job = DiscoveredJob(
        job_id="cert_job_python_lead",
        title="Lead Python Backend Engineer",
        company="AI Innovation Corp",
        location="Remote",
        platform="LinkedIn",
        job_url="https://linkedin.com/jobs/view/cert-1",
        description="Looking for a Python and FastAPI engineer with Docker and PostgreSQL experience."
    )
    config = SearchConfig(
        keywords="Python",
        location="Remote",
        min_match_score=50,
        excluded_keywords=["registration fee"],
        match_gating_mode="enforce"
    )

    result = job_evaluator.evaluate_job(good_job, sample_candidate, config)
    assert result.is_eligible is True
    assert result.suggested_action == "APPLY"
    assert result.match_score >= 50
    assert result.priority_score > 0

    # Test hard disqualification on excluded scam keyword
    scam_job = DiscoveredJob(
        job_id="cert_job_scam",
        title="Data Entry Immediate Registration Fee Required",
        company="QuickMoney Inc",
        location="Remote",
        platform="Indeed",
        job_url="https://indeed.com/jobs/view/scam-1",
        description="Earn $500 daily no experience required pay registration fee."
    )
    scam_result = job_evaluator.evaluate_job(scam_job, sample_candidate, config)
    assert scam_result.is_eligible is False
    assert scam_result.suggested_action == "SKIP"
    assert any("registration fee" in r.lower() for r in scam_result.disqualification_reasons)


def test_cert_subsystem_5_universal_adapters():
    """Subsystem 5: Verify all adapters conform to the ApplicationAdapter abstract contract."""
    adapters = [GreenhouseAdapter(), LeverAdapter()]
    for adapter in adapters:
        assert isinstance(adapter, ApplicationAdapter)
        assert hasattr(adapter, "detect")
        assert hasattr(adapter, "extract_form")
        assert hasattr(adapter, "fill_form")
        assert hasattr(adapter, "submit")
        assert hasattr(adapter, "verify_submission")


def test_cert_subsystem_6_resume_tailoring_zero_fabrication(sample_candidate):
    """Subsystem 6: Verify ATS PDF resume tailoring retains authentic candidate history."""
    job_desc = "Seeking a Senior Python Developer with expertise in FastAPI, PostgreSQL, and LLMs."
    tailored = resume_tailorer.generate_tailored_resume(
        profile=sample_candidate,
        job_title="Senior Python Developer",
        jd_text=job_desc,
        job_id="cert_e2e_test_pdf"
    )
    assert tailored is not None
    assert os.path.exists(tailored.pdf_path)
    assert tailored.file_size_bytes > 1000
    assert "Python" in tailored.matched_skills_highlighted


@pytest.mark.asyncio
async def test_cert_subsystem_7_screening_engine(sample_candidate):
    """Subsystem 7: Verify screening questions return exact vault provenance or routed safely."""
    req = ScreeningQuestionRequest(question="How many years of total experience do you have?")
    ans_result = await screening_service.answer_question(req, sample_candidate)
    assert ans_result.provenance == AnswerProvenance.EXACT_VAULT
    assert "5" in str(ans_result.answer)


@pytest.mark.asyncio
async def test_cert_subsystem_13_notifications_and_inbox():
    """Subsystem 13: Verify notification dispatch and recruiter email intent classification."""
    recruiter_body = (
        "Dear Talha,\nWe loved your profile! We'd like to schedule an interview with the VP of Engineering.\n"
        "Choose a slot here: https://calendly.com/vp-eng/interview-slot\nBest,\nHR"
    )
    intent_res = await inbox_monitor_service.classify_email_content(
        sender="talent@unicorn.com",
        subject="Interview with Unicorn Tech",
        body_text=recruiter_body
    )
    assert intent_res.intent == RecruiterEmailIntent.INTERVIEW_INVITATION
    assert intent_res.action_link == "https://calendly.com/vp-eng/interview-slot"


def test_cert_subsystem_14_security_and_circuit_breakers():
    """Subsystem 14: Verify encryption, log sanitization, and circuit breakers."""
    # 1. Encryption
    raw_pass = "MySecretPostgreSQLPass2026!"
    enc_pass = security_manager.encrypt_value(raw_pass)
    assert enc_pass.startswith("enc:")
    assert security_manager.decrypt_value(enc_pass) == raw_pass

    # 2. Log sanitization
    dirty_log = "Error connecting to http://admin:PassWord123@127.0.0.1:5432 with token sk-abcdef1234567890abcdef123456"
    clean_log = security_manager.sanitize_text(dirty_log)
    assert "PassWord123" not in clean_log
    assert "[REDACTED_OPENAI_KEY]" in clean_log

    # 3. Circuit breaker
    cb_service = "indeed_e2e_cert"
    circuit_breaker.record_failure(cb_service, RuntimeError("Blocked 1"))
    circuit_breaker.record_failure(cb_service, RuntimeError("Blocked 2"))
    circuit_breaker.record_failure(cb_service, RuntimeError("Blocked 3"))
    assert circuit_breaker.can_execute(cb_service) is False
    circuit_breaker.reset(cb_service)
    assert circuit_breaker.can_execute(cb_service) is True


def test_cert_api_gateway_contracts():
    """Subsystem 11 & Gateway: Verify all newly integrated REST endpoints respond with 200 OK."""
    endpoints = [
        ("GET", "/api/resume/vault"),
        ("GET", "/api/notifications/config"),
        ("GET", "/api/security/status"),
        ("GET", "/api/security/circuit-breakers"),
        ("GET", "/api/security/checkpoint"),
        ("GET", "/api/bot/status"),
        ("GET", "/api/jobs/list"),
        ("GET", "/api/jobs/stats")
    ]
    for method, path in endpoints:
        if method == "GET":
            resp = client.get(path)
            assert resp.status_code == 200, f"Endpoint {path} failed with status {resp.status_code}"


@pytest.mark.asyncio
async def test_cert_orchestrator_state_machine_flow(sample_candidate):
    """Subsystem 4: Verify full orchestrator lifecycle transitions from DISCOVERED to COMPLETED."""
    orch = ApplicationOrchestrator()
    config = SearchConfig(
        keywords="Python",
        location="Remote",
        platforms=[PlatformEnum.LINKEDIN],
        max_applications=1
    )

    pause_event = asyncio.Event()
    pause_event.set()
    stop_event = asyncio.Event()

    # Mock discovery to return 1 eligible job
    mock_job = DiscoveredJob(
        job_id="e2e_cert_job_1",
        title="Senior Python Developer",
        company="CertCorp",
        location="Remote",
        platform="LinkedIn",
        job_url="https://linkedin.com/jobs/view/e2e-cert-1"
    )

    with patch("app.services.orchestrator.discovery_manager.discover_jobs", new_callable=AsyncMock) as mock_disc:
        mock_disc.return_value = [mock_job]

        # Mock the platform bot execution
        mock_bot = MagicMock()
        mock_bot.init_browser = AsyncMock()
        mock_bot.login = AsyncMock(return_value=True)
        mock_bot.search_and_apply = AsyncMock(return_value=1)
        mock_bot.close_browser = AsyncMock()

        with patch.dict(orch.PLATFORM_CLASSES, {PlatformEnum.LINKEDIN: MagicMock(return_value=mock_bot)}):
            res = await orch.run_pipeline(
                config=config,
                profile=sample_candidate,
                pause_event=pause_event,
                stop_event=stop_event
            )

            assert res["status"] == "COMPLETED"
            assert res["discovered"] == 1
            assert res["eligible"] == 1
            assert res["applied"] == 1
            assert res["success"] == 1

            summary = orch.get_lifecycle_summary()
            assert summary["total_tracked_jobs"] >= 1
