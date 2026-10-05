"""Unit tests for the predictive-analysis script (the tooling gets tested too)."""
from pathlib import Path

import pytest

from ai_testing.predict_flaky import analyse, load_history, render_markdown

HISTORY = Path(__file__).parent / "test_history.csv"


def _by_name(stats):
    return {s.name.split("::")[-1]: s for s in stats}


def test_flaky_test_is_ranked_above_stable_test():
    stats = _by_name(analyse(load_history(HISTORY)))
    assert stats["test_submitting_original_paper_shows_clear_status"].risk_score > stats["test_create_submission_returns_201_with_expected_shape"].risk_score


def test_verdicts_classify_each_pattern():
    stats = _by_name(analyse(load_history(HISTORY)))
    assert stats["test_create_submission_returns_201_with_expected_shape"].verdict == "stable"
    assert stats["test_submitting_original_paper_shows_clear_status"].verdict.startswith("FLAKY")
    assert stats["test_concurrent_creates_all_succeed_with_unique_ids"].verdict.startswith("REGRESSING")
    assert stats["test_api_record_round_trips_through_s3_archive"].verdict.startswith("BROKEN")


def test_markdown_has_one_row_per_test():
    stats = analyse(load_history(HISTORY))
    rendered = render_markdown(stats)
    assert rendered.count("\n") == len(stats) + 2


@pytest.mark.parametrize("recent", [1, 3, 10])
def test_recent_window_is_respected(recent):
    for s in analyse(load_history(HISTORY), recent=recent):
        assert 0.0 <= s.recent_failure_rate <= 1.0
