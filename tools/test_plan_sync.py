"""Load the test plan into the AWS test plan app (DynamoDB).

    python -m tools.test_plan_sync --manual testdata/test_plan_manual.json
    python -m tools.test_plan_sync --junit reports/pytest.xml java-api-tests/target/surefire-reports/*.xml --source "Jenkins build 14"

Manual cases: definitions (title, steps, expected results) are created or updated, but a
recorded result and its history are never overwritten.
Automated cases: one per JUnit test case, replaced with the latest result on each sync.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

TABLE = os.environ.get("TESTPLAN_TABLE", "qa-test-plan-cases")
DEFINITION_FIELDS = ["title", "area", "priority", "objective", "preconditions", "steps", "standard", "defects"]


def suite_name(classname: str) -> str:
    """tests.security.test_owasp_api_top10 -> 'security / owasp_api_top10'; Java class -> 'java / Class'."""
    parts = classname.split(".")
    if classname.startswith("com."):
        return f"java / {parts[-1]}"
    if parts[0] == "tests" and len(parts) >= 3:
        return f"{parts[1]} / {parts[-1].removeprefix('test_')}"
    if parts[0] == "ai_testing":
        return f"tooling / {parts[-1].removeprefix('test_')}"
    return classname


def parse_junit(paths: list[str], source: str, now: str) -> list[dict]:
    cases: dict[str, dict] = {}
    for path in paths:
        for tc in ET.parse(path).getroot().iter("testcase"):
            classname, name = tc.get("classname", ""), tc.get("name", "")
            failure = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
            status = "failed" if failure is not None else "skipped" if tc.find("skipped") is not None else "passed"
            key = f"{classname}::{name}"
            item = {
                "id": "AUTO-" + hashlib.sha1(key.encode()).hexdigest()[:12],
                "type": "automated",
                "suite": suite_name(classname),
                "title": name[:200],
                "automation": key[:400],
                "status": status,
                "duration_s": Decimal(str(round(float(tc.get("time", 0) or 0), 3))),
                "last_run_at": now,
                "last_run_by": "pipeline",
                "source": source,
            }
            if failure is not None:
                item["failure"] = (failure.get("message") or failure.text or "")[:600]
            cases[item["id"]] = item
    return list(cases.values())


def load_manual(path: Path) -> list[dict]:
    cases = json.loads(path.read_text())
    ids = [c["id"] for c in cases]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate ids in the manual test case file")
    return cases


def sync_manual(table, cases: list[dict]) -> int:
    for c in cases:
        names = {f"#f{i}": f for i, f in enumerate(DEFINITION_FIELDS)}
        values = {f":f{i}": c.get(f, [] if f in ("steps", "defects") else "") for i, f in enumerate(DEFINITION_FIELDS)}
        sets = ", ".join(f"#f{i} = :f{i}" for i in range(len(DEFINITION_FIELDS)))
        table.update_item(
            Key={"id": c["id"]},
            # Definition is refreshed; status and history are only initialised, never reset.
            UpdateExpression=f"SET {sets}, #ty = :manual, #st = if_not_exists(#st, :notrun)",
            ExpressionAttributeNames={**names, "#ty": "type", "#st": "status"},
            ExpressionAttributeValues={**values, ":manual": "manual", ":notrun": "not_run"},
        )
    return len(cases)


def sync_automated(table, cases: list[dict]) -> int:
    with table.batch_writer(overwrite_by_pkeys=["id"]) as batch:
        for c in cases:
            batch.put_item(Item=c)
    return len(cases)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--manual", type=Path)
    parser.add_argument("--junit", nargs="*", default=[])
    parser.add_argument("--source", default="local run")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    manual = load_manual(args.manual) if args.manual else []
    files = sorted({f for pattern in args.junit for f in glob.glob(pattern)})
    automated = parse_junit(files, args.source, now) if files else []
    if args.junit and not files:
        print("no JUnit files matched; nothing to sync for automated cases")

    if args.dry_run:
        failed = sum(1 for c in automated if c["status"] == "failed")
        print(f"would sync {len(manual)} manual and {len(automated)} automated cases ({failed} failed) from {len(files)} files")
        return 0

    import boto3

    table = boto3.resource("dynamodb").Table(TABLE)
    print(f"synced {sync_manual(table, manual)} manual and {sync_automated(table, automated)} automated cases to {TABLE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
