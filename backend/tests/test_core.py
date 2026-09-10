import pytest
from pathlib import Path
from app.models.job import JobApplicationRecord, ApplicationStatus, ResumeProfile, SearchConfig, PlatformEnum
from app.services.excel_tracker import ExcelTracker
from app.core.llm import OllamaLLMClient

def test_resume_profile_schema():
    profile = ResumeProfile(
        full_name="Jane Doe",
        email="jane.doe@example.com",
        phone="+1 555-0199",
        location="San Francisco, CA",
        skills=["Python", "FastAPI", "React", "Docker"],
        years_of_experience=4.5
    )
    assert profile.full_name == "Jane Doe"
    assert len(profile.skills) == 4
    assert profile.custom_answers["notice_period_days"] is None

def test_search_config_defaults():
    config = SearchConfig()
    assert config.max_applications == 25
    assert config.headless is True
    assert config.dry_run is False
    assert PlatformEnum.LINKEDIN in config.platforms

def test_excel_tracker_isolated(tmp_path: Path):
    excel_path = tmp_path / "test_applications.xlsx"
    tracker = ExcelTracker(file_path=excel_path)
    
    # Test record logging
    record = JobApplicationRecord(
        platform="LinkedIn",
        job_title="Senior Python Engineer",
        company="AI Labs",
        job_url="https://www.linkedin.com/jobs/view/123456",
        status=ApplicationStatus.SUCCESS,
        notes="Applied with dry run"
    )
    tracker.log_application(record)

    # Test duplicate detection
    assert tracker.is_already_applied("https://www.linkedin.com/jobs/view/123456") is True
    assert tracker.is_already_applied("https://www.linkedin.com/jobs/view/789012") is False

    # Test stats
    stats = tracker.get_statistics()
    assert stats["total_applications"] == 1
    assert stats["success_count"] == 1
    assert stats["platform_breakdown"].get("LinkedIn") == 1

def test_llm_json_extraction_fallback():
    client = OllamaLLMClient()
    # Test direct JSON
    res1 = client._extract_json('{"key": "value"}')
    assert res1 == {"key": "value"}

    # Test markdown block
    res2 = client._extract_json('```json\n{"status": "ok", "count": 5}\n```')
    assert res2 == {"status": "ok", "count": 5}

    # Test bracket extraction from verbose text
    res3 = client._extract_json('Here is the parsed output:\n{"title": "Developer"}\nHope this helps!')
    assert res3 == {"title": "Developer"}
