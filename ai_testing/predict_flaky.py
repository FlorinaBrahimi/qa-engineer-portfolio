"""Predictive analysis over test execution history.

Given a CSV of past runs (one row per test per run), compute for each test:

* pass rate
* flakiness: how often the outcome flips between consecutive runs
* recent failure trend: failure rate over the last N runs vs. overall
* a risk score that ranks which tests deserve attention first

Output is a Markdown table so it can be posted to a PR, a Slack channel or a job summary.
The same scoring is what an "AI-driven" test selection step would use to pick which
regression tests to run first on a given change.

    python ai_testing/predict_flaky.py ai_testing/test_history.csv [--recent 5] [--out report.md]
"""
from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestStats:
    name: str
    runs: int
    pass_rate: float
    flakiness: float
    recent_failure_rate: float
    mean_duration_ms: float

    @property
    def risk_score(self) -> float:
        """0-100. Flakiness and recent failures dominate; slow tests get a small penalty."""
        score = 50 * self.flakiness + 40 * self.recent_failure_rate + 10 * min(self.mean_duration_ms / 5000, 1.0)
        return round(min(score, 100.0), 1)

    @property
    def verdict(self) -> str:
        if self.flakiness >= 0.3:
            return "FLAKY - quarantine and fix"
        if self.recent_failure_rate >= 0.5 and self.pass_rate > 0.7:
            return "REGRESSING - investigate recent change"
        if self.pass_rate < 0.5:
            return "BROKEN - consistently failing"
        return "stable"


def load_history(path: Path) -> dict[str, list[dict]]:
    by_test: dict[str, list[dict]] = defaultdict(list)
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            by_test[row["test"]].append(row)
    for rows in by_test.values():
        rows.sort(key=lambda r: int(r["run"]))
    return by_test


def analyse(by_test: dict[str, list[dict]], recent: int = 5) -> list[TestStats]:
    stats = []
    for name, rows in by_test.items():
        outcomes = [r["outcome"] == "pass" for r in rows]
        flips = sum(1 for a, b in zip(outcomes, outcomes[1:]) if a != b)
        flakiness = flips / (len(outcomes) - 1) if len(outcomes) > 1 else 0.0
        recent_outcomes = outcomes[-recent:]
        stats.append(
            TestStats(
                name=name,
                runs=len(rows),
                pass_rate=sum(outcomes) / len(outcomes),
                flakiness=round(flakiness, 2),
                recent_failure_rate=round(1 - sum(recent_outcomes) / len(recent_outcomes), 2),
                mean_duration_ms=sum(float(r["duration_ms"]) for r in rows) / len(rows),
            )
        )
    return sorted(stats, key=lambda s: s.risk_score, reverse=True)


def render_markdown(stats: list[TestStats]) -> str:
    lines = [
        "| Risk | Test | Runs | Pass rate | Flakiness | Recent fail rate | Verdict |",
        "|---:|---|---:|---:|---:|---:|---|",
    ]
    for s in stats:
        lines.append(
            f"| {s.risk_score} | `{s.name}` | {s.runs} | {s.pass_rate:.0%} | {s.flakiness:.0%} | {s.recent_failure_rate:.0%} | {s.verdict} |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("history", type=Path)
    parser.add_argument("--recent", type=int, default=5)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)

    report = render_markdown(analyse(load_history(args.history), args.recent))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(report)
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
