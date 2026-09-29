import pytest
from unittest.mock import AsyncMock, patch

from app.models.fact_ledger import (
    CandidateFact,
    FactCategory,
    FactLedger,
    VerificationStatus,
    VerificationResult,
)
from app.models.job import ResumeProfile, QAVault, WorkExperience, Education
from app.services.fact_ledger import FactLedgerService
from app.services.claim_verifier import ClaimVerifier
from app.services.screening_service import (
    screening_service,
    ScreeningQuestionRequest,
    AnswerProvenance,
)


@pytest.fixture
def sample_profile():
    return ResumeProfile(
        full_name="Alex Morgan",
        email="alex@example.com",
        phone="+1234567890",
        location="San Francisco, CA",
        years_of_experience=3.0,
        summary="Experienced Full Stack Developer building React and Python microservices.",
        skills=["Python", "FastAPI", "React", "TypeScript", "PostgreSQL"],
        work_experience=[
            WorkExperience(
                company="Nexus Systems",
                title="Full Stack Engineer",
                start_date="2021",
                end_date="Present",
                location="San Francisco",
                description="Engineered core backend APIs with FastAPI and React dashboards.",
            )
        ],
        education=[
            Education(
                institution="University of California",
                degree="B.S.",
                field="Computer Science",
                graduation_year="2021",
            )
        ],
        qa_vault=QAVault(
            work_authorization="Yes",
            require_sponsorship="No",
            willing_to_relocate="Yes",
            notice_period_days=14,
            notice_period="2 weeks",
            expected_ctc_lpa=12.0,
            current_ctc_lpa=9.0,
            custom_qa={"clearance": "None"},
        ),
    )


def test_fact_ledger_extraction(sample_profile):
    """Verify that atomic facts are accurately extracted from ResumeProfile."""
    service = FactLedgerService()
    ledger = service.build_from_profile(sample_profile)

    # 1. Total Experience Fact
    exp_fact = ledger.get_fact("total_experience_years", category=FactCategory.WORK_EXPERIENCE)
    assert exp_fact is not None
    assert exp_fact.numeric_value == 3.0
    assert exp_fact.is_verified()

    # 2. Skill Facts
    python_fact = service.query_skill("Python")
    assert python_fact is not None
    assert python_fact.category == FactCategory.TECHNICAL_SKILL

    react_fact = service.query_skill("React")
    assert react_fact is not None

    # Skill not in resume
    ruby_fact = service.query_skill("Ruby on Rails")
    assert ruby_fact is None

    # 3. QA Vault Facts
    auth_fact = ledger.get_fact("work_authorization", category=FactCategory.AUTHORIZATION)
    assert auth_fact is not None
    assert auth_fact.value == "Yes"

    spons_fact = ledger.get_fact("require_sponsorship", category=FactCategory.AUTHORIZATION)
    assert spons_fact is not None
    assert spons_fact.value == "No"


def test_claim_verifier_valid_claims(sample_profile):
    """Verify that grounded, honest claims pass verification."""
    service = FactLedgerService()
    ledger = service.build_from_profile(sample_profile)
    verifier = ClaimVerifier(ledger)

    # Valid experience claim
    res = verifier.verify_answer(
        question="How many years of professional experience do you have with Python?",
        proposed_answer="I have 3 years of experience building Python and FastAPI applications.",
    )
    assert res.is_valid is True
    assert res.requires_human_review is False

    # Valid work authorization claim
    res_auth = verifier.verify_answer(
        question="Are you authorized to work in the United States?",
        proposed_answer="Yes, I am fully authorized to work.",
    )
    assert res_auth.is_valid is True
    assert res_auth.requires_human_review is False


def test_claim_verifier_catches_inflated_experience(sample_profile):
    """Verify that inflated claims (e.g. 7 years when verified is 3) are blocked."""
    service = FactLedgerService()
    ledger = service.build_from_profile(sample_profile)
    verifier = ClaimVerifier(ledger)

    # Candidate has 3.0 years verified total experience.
    # LLM attempts to claim 7 years:
    res = verifier.verify_answer(
        question="How many years of experience do you have with software engineering?",
        proposed_answer="I have 7 years of deep software engineering experience.",
    )
    assert res.is_valid is False
    assert res.requires_human_review is True
    assert "exceeding candidate's total verified experience" in res.reason
    assert "3" in res.suggested_answer


def test_claim_verifier_catches_work_auth_contradiction(sample_profile):
    """Verify that contradictions to candidate's verified legal authorization are blocked."""
    service = FactLedgerService()
    ledger = service.build_from_profile(sample_profile)
    verifier = ClaimVerifier(ledger)

    # Candidate has work_authorization='Yes', but answer says 'No'
    res = verifier.verify_answer(
        question="Are you legally authorized to work in this location?",
        proposed_answer="No, I am not currently authorized.",
    )
    assert res.is_valid is False
    assert res.requires_human_review is True
    assert "contradicts verified work authorization" in res.reason
    assert res.suggested_answer == "Yes"


@pytest.mark.asyncio
async def test_screening_service_blocks_inflated_claim(sample_profile):
    """Integration test: ScreeningService flags answer for review if LLM hallucinates inflated numbers."""
    mock_hallucinated_response = {
        "answer": "Yes, I have over 10 years of experience with distributed Python architectures.",
        "reason": "Sounds senior and competitive.",
    }

    with patch("app.core.llm.llm_client.generate_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_hallucinated_response

        req = ScreeningQuestionRequest(
            question="What distributed Python architectures have you designed and led in production?",
            job_context={"title": "Principal Architect", "company": "Enterprise Corp"},
        )
        ans = await screening_service.answer_question(req, profile=sample_profile)

        # The claim verifier should have caught the 10 years > 3 years limit!
        assert ans.requires_human_intervention is True
        assert "Claim Verification" in ans.reason
        assert "3" in ans.answer or "3" in ans.reason
