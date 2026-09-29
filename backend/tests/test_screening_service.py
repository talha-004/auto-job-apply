import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.models.job import ResumeProfile, QAVault, WorkExperience, Education
from app.services.screening_service import (
    screening_service,
    ScreeningQuestionRequest,
    AnswerProvenance
)
from app.core.llm import UnifiedLLMClient, OllamaLLMClient, GeminiLLMClient


@pytest.fixture
def mock_candidate_profile():
    return ResumeProfile(
        full_name="Syed Talha Ahmed",
        email="syed@example.com",
        phone="+919876543210",
        location="Bengaluru, India",
        years_of_experience=2.5,
        summary="Full Stack Software Engineer specializing in Python, FastAPI, React, and automated testing.",
        skills=["Python", "FastAPI", "React", "TypeScript", "Docker", "PostgreSQL"],
        work_experience=[
            WorkExperience(
                company="Tech Solutions Inc",
                title="Software Engineer",
                start_date="2022",
                end_date="Present",
                location="Bengaluru",
                description="Designed and deployed automated REST APIs with FastAPI and React."
            )
        ],
        education=[
            Education(
                institution="State University",
                degree="Bachelor of Technology",
                field="Computer Science",
                graduation_year="2022",
                grade_or_gpa="8.5"
            )
        ],
        certifications=["AWS Certified Solutions Architect"],
        qa_vault=QAVault(
            full_name="Syed Talha Ahmed",
            email="syed@example.com",
            phone="+919876543210",
            notice_period="Immediate",
            availability="Immediate",
            experience_years=2.5,
            relevant_experience_years=2.5,
            current_ctc_lpa=3.5,
            expected_ctc_lpa=5.0,
            work_authorization="Yes",
            require_sponsorship="No",
            willing_to_relocate="Yes",
            remote_preference="Yes",
            custom_qa={
                "favorite_ide": "VS Code"
            }
        )
    )


@pytest.mark.asyncio
async def test_exact_vault_matches(mock_candidate_profile):
    """Test deterministic retrieval from QA Vault without hallucinations."""
    # 1. Notice Period
    req = ScreeningQuestionRequest(question="What is your current official notice period?")
    ans = await screening_service.answer_question(req, profile=mock_candidate_profile)
    assert ans.provenance == AnswerProvenance.EXACT_VAULT
    assert ans.confidence >= 0.8
    assert not ans.requires_human_intervention
    assert "Immediate" in ans.answer

    # 2. Sponsorship
    req_sponsor = ScreeningQuestionRequest(question="Will you require visa sponsorship now or in the future?")
    ans_sponsor = await screening_service.answer_question(req_sponsor, profile=mock_candidate_profile)
    assert ans_sponsor.provenance == AnswerProvenance.EXACT_VAULT
    assert ans_sponsor.answer == "No"

    # 3. Work Authorization
    req_auth = ScreeningQuestionRequest(question="Are you legally authorized to work in this country?")
    ans_auth = await screening_service.answer_question(req_auth, profile=mock_candidate_profile)
    assert ans_auth.provenance == AnswerProvenance.EXACT_VAULT
    assert ans_auth.answer == "Yes"

    # 4. Salary expectations
    req_salary = ScreeningQuestionRequest(question="What is your expected salary / CTC?")
    ans_salary = await screening_service.answer_question(req_salary, profile=mock_candidate_profile)
    assert ans_salary.provenance == AnswerProvenance.EXACT_VAULT
    assert ans_salary.answer == "5.0"


@pytest.mark.asyncio
async def test_options_alignment_with_vault(mock_candidate_profile):
    """Verify that answers strictly conform to the available options provided."""
    req = ScreeningQuestionRequest(
        question="What is your visa status and work eligibility?",
        options=["I am legally authorized to work without restriction", "I require employer sponsorship", "Other"]
    )
    ans = await screening_service.answer_question(req, profile=mock_candidate_profile)
    assert ans.provenance == AnswerProvenance.EXACT_VAULT
    assert ans.answer == "I am legally authorized to work without restriction"


@pytest.mark.asyncio
async def test_sensitive_clearance_triggers_unknown(mock_candidate_profile):
    """Verify security clearances and sensitive unverified requirements fail-safe to UNKNOWN."""
    req_clearance = ScreeningQuestionRequest(
        question="Do you possess an active Top Secret / SCI security clearance?"
    )
    ans = await screening_service.answer_question(req_clearance, profile=mock_candidate_profile)
    assert ans.provenance == AnswerProvenance.UNKNOWN
    assert ans.requires_human_intervention is True
    assert ans.confidence == 0.0
    assert "security clearance" in ans.reason.lower()


@pytest.mark.asyncio
async def test_sensitive_license_triggers_unknown(mock_candidate_profile):
    """Verify unverified specialized licenses (bar, medical, etc.) trigger human review."""
    req_bar = ScreeningQuestionRequest(
        question="Are you a member in good standing of the California Bar Admission?"
    )
    ans = await screening_service.answer_question(req_bar, profile=mock_candidate_profile)
    assert ans.provenance == AnswerProvenance.UNKNOWN
    assert ans.requires_human_intervention is True
    assert ans.confidence == 0.0


@pytest.mark.asyncio
async def test_derived_open_ended_question(mock_candidate_profile):
    """Verify open-ended questions use grounded candidate information via LLM."""
    mock_response = {
        "answer": "With over 2 years of experience in Python and FastAPI, I am excited to contribute to Stripe's payment infrastructure.",
        "reason": "Referenced candidate's primary skills and experience."
    }
    with patch("app.core.llm.llm_client.generate_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response
        req = ScreeningQuestionRequest(
            question="Why are you interested in this software engineer role?",
            job_context={"title": "Senior Python Engineer", "company": "Stripe"}
        )
        ans = await screening_service.answer_question(req, profile=mock_candidate_profile)
        assert ans.provenance == AnswerProvenance.DERIVED
        assert ans.requires_human_intervention is False
        assert ans.confidence >= 0.7
        assert "FastAPI" in ans.answer


@pytest.mark.asyncio
async def test_derived_fallback_when_llm_offline(mock_candidate_profile):
    """Verify grounded heuristic fallback is triggered if LLM is unreachable."""
    with patch("app.core.llm.llm_client.generate_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {}  # LLM unreachable / empty
        req = ScreeningQuestionRequest(
            question="Why are you interested in this position?",
            job_context={"title": "Backend Engineer", "company": "Google"}
        )
        ans = await screening_service.answer_question(req, profile=mock_candidate_profile)
        assert ans.provenance == AnswerProvenance.DERIVED
        assert ans.requires_human_intervention is False
        assert ans.confidence == 0.70
        assert "experience" in ans.answer.lower()


@pytest.mark.asyncio
async def test_batch_answering(mock_candidate_profile):
    """Test answering a batch of questions containing mixed provenances."""
    mock_response = {
        "answer": "I have extensive experience deploying PostgreSQL and Docker containers in production.",
        "reason": "Verified from profile skills."
    }
    with patch("app.core.llm.llm_client.generate_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_response
        questions = [
            ScreeningQuestionRequest(question="Are you authorized to work?"),
            ScreeningQuestionRequest(question="Do you have an active polygraph security clearance?"),
            ScreeningQuestionRequest(question="Describe a complex software engineering challenge you solved recently.")
        ]
        results = await screening_service.answer_batch(questions, profile=mock_candidate_profile)
        assert len(results) == 3
        assert results[0].provenance == AnswerProvenance.EXACT_VAULT
        assert results[1].provenance == AnswerProvenance.UNKNOWN
        assert results[1].requires_human_intervention is True
        assert results[2].provenance == AnswerProvenance.DERIVED


def test_screening_api_endpoints():
    """Test FastAPI REST endpoints for screening questions."""
    client = TestClient(app)

    # 1. Provider health
    res_providers = client.get("/api/screening/providers")
    assert res_providers.status_code == 200
    data_prov = res_providers.json()
    assert "providers" in data_prov

    # 2. Single answer
    res_answer = client.post("/api/screening/answer", json={
        "question": "What is your official notice period?",
        "options": ["Immediate", "30 Days", "60 Days"]
    })
    assert res_answer.status_code == 200
    data_ans = res_answer.json()
    assert data_ans["provenance"] == "EXACT_VAULT"
    assert data_ans["answer"] in ["Immediate", "30 Days", "60 Days"]

    # 3. Batch answer
    res_batch = client.post("/api/screening/batch", json={
        "questions": [
            {"question": "Are you willing to relocate?", "options": ["Yes", "No"]},
            {"question": "Do you hold a TS/SCI security clearance?"}
        ]
    })
    assert res_batch.status_code == 200
    data_batch = res_batch.json()
    assert len(data_batch) == 2
    assert data_batch[0]["provenance"] == "EXACT_VAULT"
    assert data_batch[1]["provenance"] == "UNKNOWN"
    assert data_batch[1]["requires_human_intervention"] is True
