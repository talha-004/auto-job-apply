import pytest
from app.platforms.external.ats_detector import ats_detector, detect_ats
from app.platforms.external.workday import workday_adapter, WorkdayAdapter
from app.platforms.external.smartrecruiters import smartrecruiters_adapter, SmartRecruitersAdapter
from app.models.job import ResumeProfile, QAVault, ApplicationStatus, ReasonCode


def test_workday_detection():
    # URL detection
    assert workday_adapter.detect("https://google.myworkdayjobs.com/en-US/careers/job/123") is True
    assert workday_adapter.detect("https://walmart.wd5.myworkdayjobs.com/en-US/walmart/job/456") is True
    assert workday_adapter.detect("https://boards.greenhouse.io/stripe/jobs/123") is False

    # Page markup detection
    markup = '<div data-automation-id="workdayApplication">Workday Portal</div>'
    assert workday_adapter.detect("https://careers.company.com/job", page_content=markup) is True


def test_smartrecruiters_detection():
    # URL detection
    assert smartrecruiters_adapter.detect("https://jobs.smartrecruiters.com/BoschGroup/12345-software-engineer") is True
    assert smartrecruiters_adapter.detect("https://careers.smartrecruiters.com/visa/lead-dev") is True
    assert smartrecruiters_adapter.detect("https://jobs.lever.co/netflix/123") is False

    # Page markup detection
    markup = '<div data-qa="smartrecruiters-job-details">SmartRecruiters Application</div>'
    assert smartrecruiters_adapter.detect("https://company.com/careers/job", page_content=markup) is True


def test_ats_detector_routing():
    gh_adapter = detect_ats("https://boards.greenhouse.io/figma/jobs/123")
    assert gh_adapter is not None
    assert "Greenhouse" in gh_adapter.__class__.__name__

    lev_adapter = detect_ats("https://jobs.lever.co/spotify/123")
    assert lev_adapter is not None
    assert "Lever" in lev_adapter.__class__.__name__

    wd_adapter = detect_ats("https://target.myworkdayjobs.com/targetcareers/job/789")
    assert wd_adapter is not None
    assert "Workday" in wd_adapter.__class__.__name__

    sr_adapter = detect_ats("https://jobs.smartrecruiters.com/Acme/456")
    assert sr_adapter is not None
    assert "SmartRecruiters" in sr_adapter.__class__.__name__


@pytest.mark.asyncio
async def test_smartrecruiters_form_simulation():
    class DummyElement:
        async def fill(self, text):
            pass
        async def set_input_files(self, path):
            pass
        async def click(self):
            pass
        async def is_visible(self):
            return True

    class DummyPage:
        def __init__(self):
            self.url = "https://jobs.smartrecruiters.com/test/123"

        async def query_selector(self, selector):
            return DummyElement()

        async def query_selector_all(self, selector):
            return []

        async def evaluate(self, script, el):
            return "Test Label"

        async def inner_text(self, selector):
            return "Thank you for applying. Your application was successfully submitted."

        async def goto(self, url, **kwargs):
            pass

    page = DummyPage()
    profile = ResumeProfile(
        full_name="Talha Ahmed",
        email="talha@example.com",
        phone="+919876543210",
        location="Bengaluru, Karnataka, India",
        skills=["Python", "FastAPI", "React"]
    )
    vault = QAVault()

    result = await smartrecruiters_adapter.apply(page, "https://jobs.smartrecruiters.com/test/123", profile, vault)
    assert result.status == ApplicationStatus.SUCCESS
    assert result.reason_code == ReasonCode.SUBMISSION_CONFIRMED
    assert "SmartRecruiters" in result.message
    assert result.filled_fields["first_name"] == "Talha"
    assert result.filled_fields["last_name"] == "Ahmed"
    assert result.filled_fields["email"] == "talha@example.com"
