import pytest
from fastapi.testclient import TestClient
from pathlib import Path

from app.main import app
from app.models.job import QAVault, ResumeProfile
from app.services.qa_vault_service import qa_vault_service, VaultMatchResult
from app.services.resume_parser import resume_parser_service


def test_qa_vault_model_defaults():
    """Verify default values and types in QAVault."""
    vault = QAVault()
    assert vault.experience_years == 2.0
    assert vault.notice_period_days == 15
    assert vault.notice_period == "Immediate"
    assert vault.current_ctc_lpa == 2.4
    assert vault.expected_ctc_lpa == 3.5
    assert vault.work_authorization == "Yes"
    assert vault.require_sponsorship == "No"
    assert vault.willing_to_relocate == "Yes"
    assert vault.remote_preference == "Yes"
    assert vault.gender == "Decline to specify"
    assert vault.driving_license == "Yes"
    assert isinstance(vault.custom_qa, dict)


def test_resume_profile_incorporates_qa_vault():
    """Verify ResumeProfile properly embeds QAVault."""
    profile = ResumeProfile(
        full_name="Syed Talha Ahmed",
        email="syedtalhaahmed004@gmail.com",
        skills=["React", "Python", "FastAPI"],
        qa_vault=QAVault(notice_period="Immediate", expected_ctc_lpa=3.5)
    )
    assert profile.qa_vault.notice_period == "Immediate"
    assert profile.qa_vault.expected_ctc_lpa == 3.5
    data = profile.model_dump()
    assert "qa_vault" in data
    assert data["qa_vault"]["notice_period"] == "Immediate"


def test_qa_vault_service_contact_matching():
    """Verify contact info field matching."""
    profile = ResumeProfile(
        full_name="Syed Talha Ahmed",
        email="syedtalhaahmed004@gmail.com",
        phone="+91 8143923984",
        linkedin_url="https://linkedin.com/in/talha004",
        github_url="https://github.com/talha-004",
        portfolio_url="https://talha004.vercel.app"
    )

    res_email = qa_vault_service.match_field("Your Active Email Address", profile)
    assert res_email.matched is True
    assert res_email.value == "syedtalhaahmed004@gmail.com"

    res_phone = qa_vault_service.match_field("Mobile / Cell Contact Number", profile)
    assert res_phone.matched is True
    assert res_phone.value == "+91 8143923984"

    res_li = qa_vault_service.match_field("LinkedIn Profile URL", profile)
    assert res_li.matched is True
    assert "linkedin.com/in/talha004" in res_li.value


def test_qa_vault_service_ats_questions():
    """Verify standard ATS screening questions."""
    profile = ResumeProfile(
        full_name="Syed Talha Ahmed",
        skills=["React", "Node.js", "Python"],
        years_of_experience=2.0,
        qa_vault=QAVault(
            notice_period_days=15,
            notice_period="Immediate",
            current_ctc_lpa=2.4,
            expected_ctc_lpa=3.5,
            work_authorization="Yes",
            require_sponsorship="No",
            willing_to_relocate="Yes"
        )
    )

    # Notice period
    res_np = qa_vault_service.match_field("What is your official notice period?", profile)
    assert res_np.matched is True
    assert res_np.value == "Immediate"

    # Notice period in days
    res_np_days = qa_vault_service.match_field("Notice period in days", profile)
    assert res_np_days.matched is True
    assert res_np_days.value == 15 or res_np_days.value == 0

    # CTC
    res_c_ctc = qa_vault_service.match_field("What is your current CTC (in LPA)?", profile)
    assert res_c_ctc.matched is True
    assert res_c_ctc.value == 2.4

    res_e_ctc = qa_vault_service.match_field("Expected salary / CTC expectations", profile)
    assert res_e_ctc.matched is True
    assert res_e_ctc.value == 3.5

    # Authorization & Sponsorship
    res_auth = qa_vault_service.match_field("Are you legally authorized to work in this location?", profile)
    assert res_auth.matched is True
    assert res_auth.value == "Yes"

    res_spon = qa_vault_service.match_field("Will you now or in the future require visa sponsorship?", profile)
    assert res_spon.matched is True
    assert res_spon.value == "No"

    # Relocation
    res_reloc = qa_vault_service.match_field("Are you open to relocation?", profile)
    assert res_reloc.matched is True
    assert res_reloc.value == "Yes"


def test_qa_vault_service_option_alignment():
    """Verify selecting closest option from radio/dropdown choices."""
    profile = ResumeProfile(
        qa_vault=QAVault(work_authorization="Yes", require_sponsorship="No")
    )

    # Yes/No with descriptive choices
    opts1 = ["Yes, I am eligible to work without restriction", "No, I am not eligible"]
    res1 = qa_vault_service.match_field("Work authorization status", profile, options=opts1)
    assert res1.matched is True
    assert res1.value == "Yes, I am eligible to work without restriction"

    opts2 = ["I require sponsorship", "No, I do not require sponsorship"]
    res2 = qa_vault_service.match_field("Do you require sponsorship?", profile, options=opts2)
    assert res2.matched is True
    assert res2.value == "No, I do not require sponsorship"


def test_qa_vault_service_custom_qa_override():
    """Verify custom_qa overrides take highest priority."""
    profile = ResumeProfile(
        qa_vault=QAVault(
            custom_qa={
                "favorite framework": "Next.js and FastAPI",
                "security clearance": "Confidential"
            }
        )
    )

    res = qa_vault_service.match_field("Do you have a security clearance?", profile)
    assert res.matched is True
    assert res.value == "Confidential"
    assert res.source == "custom_qa"
    assert res.confidence == 1.0


def test_resume_vault_api_endpoints(monkeypatch, tmp_path: Path):
    """Verify REST API GET and PUT /api/resume/vault."""
    test_profile = ResumeProfile(
        full_name="Syed Talha Ahmed",
        email="test@candidate.com",
        qa_vault=QAVault(notice_period="Immediate", expected_ctc_lpa=3.5)
    )
    # Mock load and save profile
    monkeypatch.setattr(resume_parser_service, "load_profile", lambda: test_profile)
    monkeypatch.setattr(resume_parser_service, "save_profile", lambda p: None)

    client = TestClient(app)

    # 1. GET /api/resume/vault
    response = client.get("/api/resume/vault")
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["vault"]["notice_period"] == "Immediate"
    assert data["vault"]["expected_ctc_lpa"] == 3.5

    # 2. PUT /api/resume/vault
    updated_payload = {
        "experience_years": 3.0,
        "notice_period_days": 30,
        "notice_period": "1 Month",
        "current_ctc_lpa": 3.0,
        "expected_ctc_lpa": 5.0,
        "work_authorization": "Yes",
        "require_sponsorship": "No",
        "willing_to_relocate": "Yes",
        "remote_preference": "Yes",
        "gender": "Decline to specify",
        "veteran_status": "No",
        "disability_status": "No",
        "availability": "1 Month",
        "driving_license": "Yes",
        "highest_education": "Master of Business Administration – Information Technology",
        "currency": "INR",
        "custom_qa": {}
    }
    put_response = client.put("/api/resume/vault", json=updated_payload)
    assert put_response.status_code == 200
    put_data = put_response.json()
    assert put_data["success"] is True
    assert put_data["vault"]["expected_ctc_lpa"] == 5.0
    assert put_data["vault"]["notice_period"] == "1 Month"
