"""Turn a JMeter results file into artefacts that link the load test to the pipeline run.

From one JTL (CSV) file it produces:

* a JUnit XML file, one test case per request type, so performance results appear in the
  same test report as the functional tests (GitHub, Jenkins, any JUnit viewer);
* a Markdown summary for the pipeline's run page;
* a non-zero exit code when a threshold is breached, so the run fails.

    python -m tools.jmeter_report reports/perf.jtl --junit reports/perf.xml --markdown reports/perf.md
    python -m tools.jmeter_report reports/perf.jtl --max-p95-ms 500 --max-error-pct 0.5
"""
from __future__ import annotations

import argparse
import csv
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SamplerStats:
    label: str
    count: int
    errors: int
    avg_ms: float
    p95_ms: int
    max_ms: int
    duration_s: float

    @property
    def error_pct(self) -> float:
        return 100.0 * self.errors / self.count if self.count else 0.0

    @property
    def throughput(self) -> float:
        return self.count / self.duration_s if self.duration_s > 0 else 0.0

    def breaches(self, max_p95_ms: int, max_error_pct: float) -> list[str]:
        problems = []
        if self.p95_ms > max_p95_ms:
            problems.append(f"p95 {self.p95_ms} ms exceeds {max_p95_ms} ms")
        if self.error_pct > max_error_pct:
            problems.append(f"error rate {self.error_pct:.2f}% exceeds {max_error_pct}%")
        return problems


def percentile(sorted_values: list[int], pct: float) -> int:
    """Nearest-rank percentile, the method JMeter's own report uses."""
    if not sorted_values:
        return 0
    rank = max(1, -(-len(sorted_values) * pct // 100))  # ceil without importing math
    return sorted_values[int(rank) - 1]


def load(path: Path) -> list[SamplerStats]:
    by_label: dict[str, list[dict]] = {}
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            by_label.setdefault(row["label"], []).append(row)

    all_rows = [r for rows in by_label.values() for r in rows]
    if not all_rows:
        return []
    start = min(int(r["timeStamp"]) for r in all_rows)
    end = max(int(r["timeStamp"]) + int(r["elapsed"]) for r in all_rows)
    duration_s = max((end - start) / 1000.0, 0.001)

    stats = []
    for label, rows in by_label.items():
        elapsed = sorted(int(r["elapsed"]) for r in rows)
        stats.append(
            SamplerStats(
                label=label,
                count=len(rows),
                errors=sum(1 for r in rows if r["success"].lower() != "true"),
                avg_ms=sum(elapsed) / len(elapsed),
                p95_ms=percentile(elapsed, 95),
                max_ms=elapsed[-1],
                duration_s=duration_s,
            )
        )
    return stats


def to_markdown(stats: list[SamplerStats], max_p95_ms: int, max_error_pct: float) -> str:
    lines = [
        "### JMeter load test",
        "",
        f"Thresholds: p95 at most {max_p95_ms} ms, error rate at most {max_error_pct}%.",
        "",
        "| Result | Request | Samples | Errors | Avg | p95 | Max | Req/s |",
        "|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for s in stats:
        verdict = "FAIL" if s.breaches(max_p95_ms, max_error_pct) else "pass"
        lines.append(
            f"| {verdict} | `{s.label}` | {s.count} | {s.error_pct:.2f}% | {s.avg_ms:.0f} ms | {s.p95_ms} ms | {s.max_ms} ms | {s.throughput:.1f} |"
        )
    total = sum(s.count for s in stats)
    lines += ["", f"{total} requests in {stats[0].duration_s:.0f} s." if stats else "No samples recorded."]
    return "\n".join(lines) + "\n"


def to_junit(stats: list[SamplerStats], max_p95_ms: int, max_error_pct: float) -> ET.ElementTree:
    failures = sum(1 for s in stats if s.breaches(max_p95_ms, max_error_pct))
    suite = ET.Element(
        "testsuite",
        name="performance.jmeter",
        tests=str(len(stats)),
        failures=str(failures),
        errors="0",
        time=f"{stats[0].duration_s:.3f}" if stats else "0",
    )
    for s in stats:
        case = ET.SubElement(suite, "testcase", classname="performance.jmeter", name=s.label, time=f"{s.avg_ms / 1000:.3f}")
        detail = f"samples={s.count} errors={s.error_pct:.2f}% avg={s.avg_ms:.0f}ms p95={s.p95_ms}ms max={s.max_ms}ms throughput={s.throughput:.1f}/s"
        problems = s.breaches(max_p95_ms, max_error_pct)
        if problems:
            ET.SubElement(case, "failure", message="; ".join(problems)).text = detail
        ET.SubElement(case, "system-out").text = detail
    return ET.ElementTree(suite)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("jtl", type=Path)
    parser.add_argument("--junit", type=Path, help="write JUnit XML here")
    parser.add_argument("--markdown", type=Path, help="write a Markdown summary here")
    parser.add_argument("--max-p95-ms", type=int, default=500)
    parser.add_argument("--max-error-pct", type=float, default=0.5)
    args = parser.parse_args(argv)

    stats = load(args.jtl)
    if not stats:
        print("No samples in the results file; treating as a failed run.")
        return 1

    summary = to_markdown(stats, args.max_p95_ms, args.max_error_pct)
    print(summary)
    if args.markdown:
        args.markdown.write_text(summary)
    if args.junit:
        to_junit(stats, args.max_p95_ms, args.max_error_pct).write(args.junit, encoding="utf-8", xml_declaration=True)

    breached = [f"{s.label}: {p}" for s in stats for p in s.breaches(args.max_p95_ms, args.max_error_pct)]
    for line in breached:
        print(f"THRESHOLD BREACHED  {line}")
    return 1 if breached else 0


if __name__ == "__main__":
    sys.exit(main())
