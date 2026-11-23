"""Offline-only checks of the optional real-model acceptance runner."""
from pathlib import Path

from echoloom.config import Settings
from conftest import FakeText
from scripts.marketplace_live_smoke import RUBRIC, run_acceptance


def test_live_qa_runner_uses_isolated_db_and_proves_the_full_flow(tmp_path):
    untouched = tmp_path / "production.db"
    settings = Settings(
        _env_file=None,
        llm_api_key="",
        llm_model="",
        database_url="sqlite:///" + str(untouched),
    )
    report = run_acceptance(settings, text_provider=FakeText(), timeout_seconds=30)
    assert report["mode"] == "FAKE_TEST_PROVIDER"
    assert report["status"] == "AUTOMATED_PASS"
    assert len(report["generated"]) == 2
    assert all(report["checks"].values())
    assert len(report["manual_quality_review"]) == len(RUBRIC)
    assert all(item["score_1_to_5"] is None
               for item in report["manual_quality_review"])
    assert "SECRET_QA_FIELD_MUST_NOT_ENTER_PUBLIC_SCENES" not in str(report)
    assert not untouched.exists()


def test_offline_qa_records_both_separate_generation_segments():
    result = run_acceptance(
        Settings(_env_file=None, llm_api_key="", llm_model=""),
        text_provider=FakeText(),
        timeout_seconds=30,
    )
    assert [item["kind"] for item in result["generated"]] == [
        "continue", "direction"
    ]
    assert all(item["saved_block_count"] > 0 for item in result["generated"])
    assert all(item["text"] for item in result["generated"])
    assert result["checks"]["41st_sentence_requires_unlock"]
    assert result["checks"]["saved_story_reopens_unchanged"]
