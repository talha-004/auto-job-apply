import pytest
from pathlib import Path
from app.services.naukri_booster import NaukriBoosterService


@pytest.fixture
def tmp_booster(tmp_path):
    history_file = tmp_path / "test_naukri_boost.json"
    return NaukriBoosterService(history_file=history_file)


def test_generate_refreshed_headline(tmp_booster):
    # Tests subtle dot toggling
    h1 = "Full Stack Engineer"
    h1_refreshed = tmp_booster.generate_refreshed_headline(h1)
    assert h1_refreshed == "Full Stack Engineer."

    h2 = "Full Stack Engineer."
    h2_refreshed = tmp_booster.generate_refreshed_headline(h2)
    assert h2_refreshed == "Full Stack Engineer"


@pytest.mark.asyncio
async def test_boost_profile_dry_run_and_history(tmp_booster):
    assert tmp_booster.should_boost_today() is True

    res = await tmp_booster.boost_profile(headline_override="Senior Lead Python Developer", dry_run=True)
    assert res["status"] == "SUCCESS"
    assert res["updated_headline"] == "Senior Lead Python Developer"
    assert "Active Today" in res["recruiter_reach_multiplier"]

    # History saved
    history = tmp_booster.get_boost_history()
    assert len(history) == 1
    assert history[0]["updated_headline"] == "Senior Lead Python Developer"

    # Should not need another boost immediately
    assert tmp_booster.should_boost_today() is False
    assert tmp_booster.get_last_boost_time() is not None
