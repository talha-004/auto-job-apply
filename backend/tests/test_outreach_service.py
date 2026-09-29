import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.job import (
    RecruiterContact,
    OutreachChannel,
    OutreachStatus,
    OutreachMessage,
    ResumeProfile,
    QAVault
)
from app.services.contact_extractor import contact_extractor_service
from app.services.email_outreach_service import email_outreach_service
from app.core.config import settings


@pytest.fixture
def mock_candidate():
    return ResumeProfile(
        full_name="Syed Talha Ahmed",
        email="syed@example.com",
        phone="+91 98765 43210",
        location="Bengaluru, India",
        years_of_experience=2.5,
        summary="Experienced Full Stack Developer.",
        skills=["Python", "FastAPI", "React", "Docker"],
        linkedin_url="https://linkedin.com/in/syedtalha",
        qa_vault=QAVault(notice_period="Immediate")
    )


def test_contact_extractor_emails_and_names():
    """Verify contact extraction of recruiter email and name while filtering blacklisted addresses."""
    jd_text = """
    We are looking for a Senior Software Engineer.
    Please share your updated resume at careers@techcorp.com or priya.sharma@techcorp.com.
    For technical support email support@techcorp.com (do not send resumes here).
    """
    recruiter_text = "Posted by: Priya Sharma (Lead Technical Recruiter) at TechCorp"

    contacts = contact_extractor_service.extract_contacts(jd_text, recruiter_text, company="TechCorp")
    assert len(contacts) >= 2

    emails = [c.email for c in contacts]
    assert "careers@techcorp.com" in emails
    assert "priya.sharma@techcorp.com" in emails
    assert "support@techcorp.com" not in emails  # Filtered out

    priya = next(c for c in contacts if c.email == "priya.sharma@techcorp.com")
    assert priya.name == "Priya Sharma"
    assert priya.confidence in ["high", "medium"]


def test_contact_extractor_phone_and_whatsapp():
    """Verify phone extraction and E.164 normalization for WhatsApp."""
    jd_text = """
    Immediate requirement! Call or WhatsApp HR at +91 98765-43210 or connect directly.
    """
    phones = contact_extractor_service.extract_phone_numbers(jd_text)
    assert len(phones) == 1
    display_phone, e164_wa = phones[0]
    assert display_phone == "+91 98765 43210"
    assert e164_wa == "919876543210"


def test_contact_extractor_linkedin_url():
    """Verify extraction of recruiter LinkedIn profile."""
    text = "Connect with the hiring manager on LinkedIn: https://www.linkedin.com/in/alex-johnson-recruiter/"
    url = contact_extractor_service.extract_linkedin_url(text)
    assert url == "https://www.linkedin.com/in/alex-johnson-recruiter"


def test_whatsapp_url_generation():
    """Verify official WhatsApp click-to-chat URL formatting."""
    phone = "+91 98765 43210"
    message = "Hello! I am applying for the Python Engineer role."
    url = email_outreach_service.generate_whatsapp_url(phone, message)
    assert url.startswith("https://wa.me/919876543210?text=")
    assert "Python%20Engineer" in url
    assert "+" not in url.split("?")[0]  # E.164 path must not contain plus sign


@pytest.mark.asyncio
async def test_draft_email_outreach_grounded_llm(mock_candidate):
    """Verify email draft generation with candidate profile grounding via LLM."""
    mock_llm_res = {
        "subject": "Application: Full Stack Engineer - Syed Talha Ahmed",
        "body": "Dear Alex Smith,\n\nI am excited to apply for the Full Stack Engineer role at Company XYZ with 2.5 years of Python experience.\n\nBest regards,\nSyed Talha Ahmed"
    }
    with patch("app.core.llm.llm_client.generate_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = mock_llm_res
        recipient = RecruiterContact(
            name="Alex Smith",
            email="alex@company.com",
            contact_type="recruiter"
        )

        msg = await email_outreach_service.draft_outreach(
            job_id="job_123",
            job_title="Full Stack Engineer",
            company="Company XYZ",
            recipient=recipient,
            candidate_profile=mock_candidate,
            channel=OutreachChannel.EMAIL
        )

        assert msg.status == OutreachStatus.DRAFTED
        assert msg.requires_approval is True
        assert "Full Stack Engineer" in msg.subject
        assert "Alex Smith" in msg.body_text
        assert "Python" in msg.body_text


@pytest.mark.asyncio
async def test_draft_email_outreach_fallback_template(mock_candidate):
    """Verify email draft deterministic fallback when LLM is unreachable."""
    with patch("app.core.llm.llm_client.generate_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {}  # LLM offline
        recipient = RecruiterContact(
            name="Sarah Connor",
            email="sarah@skynet.com",
            contact_type="recruiter"
        )

        msg = await email_outreach_service.draft_outreach(
            job_id="job_fallback",
            job_title="Security Engineer",
            company="Skynet Systems",
            recipient=recipient,
            candidate_profile=mock_candidate,
            channel=OutreachChannel.EMAIL
        )

        assert msg.status == OutreachStatus.DRAFTED
        assert "Security Engineer" in msg.subject
        assert "Sarah Connor" in msg.body_text
        assert "Python" in msg.body_text
        assert "immediate" in msg.body_text.lower()


@pytest.mark.asyncio
async def test_draft_whatsapp_outreach(mock_candidate):
    """Verify WhatsApp draft generation with click-to-chat URL."""
    recipient = RecruiterContact(
        name="Neha Verma",
        phone="+91 98765 43210",
        whatsapp_number="919876543210",
        contact_type="hr"
    )

    msg = await email_outreach_service.draft_outreach(
        job_id="job_456",
        job_title="Backend Developer",
        company="FastScale",
        recipient=recipient,
        candidate_profile=mock_candidate,
        channel=OutreachChannel.WHATSAPP
    )

    assert msg.channel == OutreachChannel.WHATSAPP
    assert msg.whatsapp_url is not None
    assert "https://wa.me/919876543210" in msg.whatsapp_url
    assert "Neha Verma" in msg.body_text


@pytest.mark.asyncio
async def test_email_sending_approval_guard(mock_candidate):
    """Verify safety guard prevents sending unapproved drafts."""
    with patch("app.core.llm.llm_client.generate_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {}
        recipient = RecruiterContact(name="Recruiter", email="hr@test.com")
        msg = await email_outreach_service.draft_outreach(
            job_id="job_789",
            job_title="DevOps Engineer",
            company="CloudCorp",
            recipient=recipient,
            candidate_profile=mock_candidate
        )

        # Sending without force_send must raise PermissionError
        with pytest.raises(PermissionError, match="requires human approval"):
            email_outreach_service.send_email(msg.id, force_send=False)


def test_email_sending_with_mock_smtp(mock_candidate, tmp_path):
    """Verify SMTP email delivery and attachment handling with mocked smtplib."""
    dummy_pdf = tmp_path / "resume.pdf"
    dummy_pdf.write_text("%PDF-1.4 mock resume content")

    recipient = RecruiterContact(name="Hiring Lead", email="hiring@scale.com")
    msg = OutreachMessage(
        job_id="job_999",
        job_title="Software Architect",
        company="Scale Corp",
        recipient=recipient,
        subject="Application for Software Architect",
        body_text="Please find my attached resume.",
        attachment_path=str(dummy_pdf),
        requires_approval=True
    )
    email_outreach_service._save_outreach(msg)

    # Mock smtplib.SMTP
    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_server = MagicMock()
        mock_smtp_class.return_value = mock_server

        with patch.object(settings, "SMTP_HOST", "smtp.example.com"), \
             patch.object(settings, "SMTP_USER", "user@example.com"), \
             patch.object(settings, "SMTP_PASSWORD", "secret"), \
             patch.object(settings, "SENDER_EMAIL", "sender@example.com"):

            sent = email_outreach_service.send_email(msg.id, force_send=True)
            assert sent.status == OutreachStatus.SENT
            assert sent.sent_at is not None

            # Verify SMTP interactions
            mock_smtp_class.assert_called_once_with("smtp.example.com", 587, timeout=15)
            mock_server.starttls.assert_called_once()
            mock_server.login.assert_called_once_with("user@example.com", "secret")
            mock_server.send_message.assert_called_once()
            mock_server.quit.assert_called_once()


def test_outreach_rest_api_endpoints(mock_candidate):
    """Verify FastAPI REST API endpoints for recruiter outreach."""
    client = TestClient(app)

    with patch("app.core.llm.llm_client.generate_json", new_callable=AsyncMock) as mock_llm:
        mock_llm.return_value = {}

        # 1. Extract contacts
        res_extract = client.post("/api/outreach/extract-contacts", json={
            "jd_text": "Send resume to hr@hiringnow.com or call +91 98765 11111",
            "company": "HiringNow"
        })
        assert res_extract.status_code == 200
        contacts_data = res_extract.json()
        assert len(contacts_data) >= 1
        assert contacts_data[0]["email"] == "hr@hiringnow.com"

        # 2. Draft message
        res_draft = client.post("/api/outreach/draft", json={
            "job_id": "api_job_1",
            "job_title": "Python Lead",
            "company": "Tech Innovators",
            "recipient": {
                "name": "Arun Kumar",
                "email": "arun@techinnovators.com",
                "contact_type": "recruiter"
            },
            "channel": "EMAIL"
        })
        assert res_draft.status_code == 200
        draft_data = res_draft.json()
        outreach_id = draft_data["id"]
        assert draft_data["status"] == "DRAFTED"
        assert "Python Lead" in draft_data["subject"]

        # 3. List messages
        res_list = client.get("/api/outreach/messages")
        assert res_list.status_code == 200
        messages = res_list.json()
        assert any(m["id"] == outreach_id for m in messages)

        # 4. WhatsApp URL generator
        res_wa = client.get("/api/outreach/whatsapp-url?phone=+919876543210&message=Hello")
        assert res_wa.status_code == 200
        assert "https://wa.me/919876543210?text=Hello" in res_wa.json()["whatsapp_url"]

        # 5. Decline outreach message
        res_decline = client.post(f"/api/outreach/decline/{outreach_id}")
        assert res_decline.status_code == 200
        assert res_decline.json()["success"] is True

        res_check = client.get(f"/api/outreach/messages/{outreach_id}")
        assert res_check.status_code == 200
        assert res_check.json()["status"] == "DECLINED"

