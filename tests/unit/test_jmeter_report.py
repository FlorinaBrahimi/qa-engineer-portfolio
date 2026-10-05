"""Unit tests for the JMeter results converter: stats, thresholds, JUnit and Markdown output."""
from pathlib import Path

import pytest

from tools.jmeter_report import load, main, percentile, to_junit, to_markdown

HEADER = "timeStamp,elapsed,label,responseCode,responseMessage,threadName,dataType,success,failureMessage,bytes,sentBytes,grpThreads,allThreads,URL,Latency,IdleTime,Connect\n"


def _jtl(tmp_path: Path, rows: list[tuple[int, int, str, bool]]) -> Path:
    path = tmp_path / "run.jtl"
    body = "".join(f"{ts},{ms},{label},200,OK,t,text,{str(ok).lower()},,1,1,1,1,http://x,1,0,1\n" for ts, ms, label, ok in rows)
    path.write_text(HEADER + body)
    return path


@pytest.mark.parametrize("values, pct, expected", [([], 95, 0), ([7], 95, 7), (list(range(1, 101)), 95, 95), (list(range(1, 21)), 95, 19)])
def test_percentile_uses_nearest_rank(values, pct, expected):
    assert percentile(values, pct) == expected


def test_stats_are_grouped_per_request_type(tmp_path):
    stats = {s.label: s for s in load(_jtl(tmp_path, [(0, 10, "GET a", True), (100, 30, "GET a", True), (200, 50, "POST b", False)]))}
    assert stats["GET a"].count == 2 and stats["GET a"].avg_ms == 20 and stats["GET a"].errors == 0
    assert stats["POST b"].error_pct == 100.0


def test_slow_p95_is_reported_as_a_junit_failure(tmp_path):
    stats = load(_jtl(tmp_path, [(i * 10, 900, "GET slow", True) for i in range(20)]))
    root = to_junit(stats, max_p95_ms=500, max_error_pct=0.5).getroot()
    assert root.get("failures") == "1"
    assert "p95 900 ms exceeds 500 ms" in root.find("testcase/failure").get("message")


def test_fast_clean_run_has_no_failures_and_says_pass(tmp_path):
    stats = load(_jtl(tmp_path, [(i * 10, 5, "GET fast", True) for i in range(20)]))
    assert to_junit(stats, 500, 0.5).getroot().get("failures") == "0"
    assert "| pass | `GET fast` | 20 |" in to_markdown(stats, 500, 0.5)


def test_exit_code_fails_the_run_on_errors_and_writes_outputs(tmp_path):
    jtl = _jtl(tmp_path, [(0, 5, "GET x", True), (10, 5, "GET x", False)])
    junit, md = tmp_path / "perf.xml", tmp_path / "perf.md"
    assert main([str(jtl), "--junit", str(junit), "--markdown", str(md)]) == 1
    assert junit.exists() and "FAIL" in md.read_text()


def test_empty_results_file_fails_rather_than_passing_silently(tmp_path):
    empty = tmp_path / "empty.jtl"
    empty.write_text(HEADER)
    assert main([str(empty)]) == 1
