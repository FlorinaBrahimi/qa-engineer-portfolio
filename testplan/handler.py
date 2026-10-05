"""Test plan web app for AWS Lambda (Function URL) backed by DynamoDB.

AWS has no managed test-plan service, so this provides one from AWS building blocks:

    GET  /                      the plan: summary, manual cases, automated cases by suite
    GET  /case/<id>             one case: steps, expected results, latest result, history
    POST /case/<id>/result      record a manual result (needs the tester key)
    GET  /api/cases             every case as JSON
    GET  /static.css            stylesheet

Reading is public so the plan can be shown; recording a result needs TESTPLAN_KEY.
Standard library and boto3 only, so the deployment package is this one file.
"""
from __future__ import annotations

import base64
import hmac
import html
import json
import os
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import parse_qs, quote

TABLE = os.environ.get("TESTPLAN_TABLE", "qa-test-plan-cases")
KEY = os.environ.get("TESTPLAN_KEY", "")
PLAN_NAME = os.environ.get("TESTPLAN_NAME", "Submission Service v1.1")
STATUSES = ["passed", "failed", "blocked", "skipped", "not_run"]
_table = None

HEADERS = {
    "Content-Security-Policy": "default-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
    "Cache-Control": "no-store",
}

CSS = """
:root{--navy:#0f1f3d;--line:#e2e6ec;--muted:#5b6676;--page:#f4f6f9}
*{box-sizing:border-box}body{margin:0;font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;color:#1c2430;background:var(--page);line-height:1.5}
header{background:var(--navy);color:#fff;padding:1rem}header a{color:#fff;text-decoration:none;font-weight:700}
header span{opacity:.8;margin-left:.6rem;font-size:.9rem}
main{max-width:70rem;margin:0 auto;padding:1rem}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:1.2rem;margin-bottom:1rem}
h1{margin:.2rem 0 .6rem;font-size:1.5rem}h2{margin:0 0 .6rem;font-size:1.15rem}h3{font-size:1rem;margin:1rem 0 .3rem}
.muted{color:var(--muted);font-size:.9rem}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(8rem,1fr));gap:.6rem}
.stat{border:1px solid var(--line);border-radius:8px;padding:.7rem;background:var(--page)}.stat b{display:block;font-size:1.5rem}
table{width:100%;border-collapse:collapse;font-size:.93rem}th,td{text-align:left;padding:.5rem;border-bottom:1px solid var(--line);vertical-align:top}
th{font-size:.76rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted)}
.wrap{overflow-x:auto}
.pill{display:inline-block;border-radius:999px;padding:.1rem .6rem;font-size:.8rem;font-weight:600;border:1px solid transparent}
.passed{background:#e6f4ea;color:#14532d}.failed{background:#fdecef;color:#a30d2d}.blocked{background:#fff4e0;color:#8a4b00}
.skipped,.not_run{background:#eef1f5;color:#3b4656}
details{border:1px solid var(--line);border-radius:8px;margin:.5rem 0;background:#fff}summary{cursor:pointer;padding:.6rem .8rem;font-weight:600}
details .wrap{padding:0 .8rem .6rem}
a{color:#0b4a99}label{display:block;font-weight:600;margin-top:.7rem}
input,select,textarea{font:inherit;padding:.5rem;border:1px solid #cfd6df;border-radius:6px;width:100%;max-width:32rem}
button{font:inherit;font-weight:600;margin-top:1rem;padding:.6rem 1.2rem;border:0;border-radius:8px;background:#b80f33;color:#fff;cursor:pointer}
.msg{border:2px solid #a30d2d;border-radius:8px;padding:.6rem .8rem;margin-bottom:1rem;background:#fff}
ol{padding-left:1.2rem}code{font-size:.85rem;word-break:break-all}
"""


def table():
    global _table
    if _table is None:
        import boto3

        _table = boto3.resource("dynamodb").Table(TABLE)
    return _table


def _plain(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, list):
        return [_plain(v) for v in value]
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    return value


def all_cases() -> list[dict]:
    items, kwargs = [], {}
    while True:
        page = table().scan(**kwargs)
        items.extend(_plain(i) for i in page.get("Items", []))
        if "LastEvaluatedKey" not in page:
            return sorted(items, key=lambda c: c["id"])
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def get_case(case_id: str) -> dict | None:
    item = table().get_item(Key={"id": case_id}).get("Item")
    return _plain(item) if item else None


def record_result(case_id: str, status: str, tester: str, notes: str) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry = {"status": status, "by": tester, "at": now, "notes": notes}
    table().update_item(
        Key={"id": case_id},
        UpdateExpression="SET #s = :s, last_run_at = :t, last_run_by = :b, notes = :n, history = list_append(if_not_exists(history, :empty), :h)",
        ConditionExpression="attribute_exists(id) AND #ty = :manual",
        ExpressionAttributeNames={"#s": "status", "#ty": "type"},
        ExpressionAttributeValues={":s": status, ":t": now, ":b": tester, ":n": notes, ":h": [entry], ":empty": [], ":manual": "manual"},
    )


# ---------- rendering ----------

e = html.escape


def pill(status: str) -> str:
    status = status if status in STATUSES else "not_run"
    return f'<span class="pill {status}">{e(status.replace("_", " "))}</span>'


def page(title: str, body: str, status: int = 200) -> dict:
    doc = (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
        f'<title>{e(title)}</title><link rel="stylesheet" href="/static.css"></head><body>'
        f'<header><a href="/">QA Test Plan</a><span>{e(PLAN_NAME)}</span></header><main>{body}</main></body></html>'
    )
    return {"statusCode": status, "headers": {**HEADERS, "Content-Type": "text/html; charset=utf-8"}, "body": doc}


def counts(cases: list[dict]) -> dict:
    out = {s: 0 for s in STATUSES}
    for c in cases:
        out[c.get("status") if c.get("status") in STATUSES else "not_run"] += 1
    return out


def render_plan(cases: list[dict]) -> dict:
    manual = [c for c in cases if c.get("type") == "manual"]
    auto = [c for c in cases if c.get("type") == "automated"]
    total = counts(cases)
    executed = len(cases) - total["not_run"]
    rate = f"{100 * total['passed'] / executed:.1f}%" if executed else "n/a"
    stats = "".join(f'<div class="stat"><b>{v}</b>{e(k)}</div>' for k, v in [
        ("test cases", len(cases)), ("manual", len(manual)), ("automated", len(auto)),
        ("passed", total["passed"]), ("failed", total["failed"]), ("blocked", total["blocked"]),
        ("not run", total["not_run"]), ("pass rate of executed", rate)])

    rows = "".join(
        f'<tr><td><a href="/case/{quote(c["id"])}">{e(c["id"])}</a></td><td>{e(c.get("title", ""))}</td><td>{e(c.get("area", ""))}</td>'
        f'<td>{e(c.get("priority", ""))}</td><td>{pill(c.get("status", "not_run"))}</td>'
        f'<td class="muted">{e(c.get("last_run_by", ""))} {e(c.get("last_run_at", "")[:16].replace("T", " "))}</td></tr>'
        for c in manual) or '<tr><td colspan="6" class="muted">No manual cases loaded.</td></tr>'

    suites: dict[str, list[dict]] = {}
    for c in auto:
        suites.setdefault(c.get("suite", "other"), []).append(c)
    blocks = []
    for name in sorted(suites):
        group = suites[name]
        n = counts(group)
        flag = f' · <span class="pill failed">{n["failed"]} failed</span>' if n["failed"] else ""
        lines = "".join(
            f'<tr><td><a href="/case/{quote(c["id"])}">{e(c.get("title", ""))}</a></td><td>{pill(c.get("status", "not_run"))}</td>'
            f'<td class="muted">{e(str(c.get("duration_s", "")))}</td></tr>' for c in group)
        blocks.append(
            f'<details{" open" if n["failed"] else ""}><summary>{e(name)} <span class="muted">· {len(group)} cases · {n["passed"]} passed{", " + str(n["skipped"]) + " skipped" if n["skipped"] else ""}</span>{flag}</summary>'
            f'<div class="wrap"><table><thead><tr><th scope="col">Test</th><th scope="col">Result</th><th scope="col">Seconds</th></tr></thead><tbody>{lines}</tbody></table></div></details>')
    source = next((c.get("source", "") for c in auto if c.get("source")), "")
    synced = max((c.get("last_run_at", "") for c in auto), default="")

    body = (
        f'<div class="card"><h1>Test plan: {e(PLAN_NAME)}</h1><p class="muted">Manual cases are executed and recorded here. '
        f'Automated cases are loaded from pipeline results after each run.</p><div class="stats">{stats}</div></div>'
        f'<div class="card"><h2>Manual test cases</h2><div class="wrap"><table><thead><tr><th scope="col">ID</th><th scope="col">Title</th>'
        f'<th scope="col">Area</th><th scope="col">Priority</th><th scope="col">Result</th><th scope="col">Last run</th></tr></thead><tbody>{rows}</tbody></table></div></div>'
        f'<div class="card"><h2>Automated test cases</h2><p class="muted">{len(auto)} cases in {len(suites)} suites. '
        f'Latest results from {e(source or "no run yet")} at {e(synced[:16].replace("T", " "))} UTC.</p>{"".join(blocks)}</div>')
    return page("QA Test Plan", body)


def render_case(c: dict, message: str = "", status: int = 200) -> dict:
    steps = "".join(f'<li>{e(s.get("action", ""))}<br><span class="muted">Expected: {e(s.get("expected", ""))}</span></li>' for s in c.get("steps", []))
    history = "".join(
        f'<tr><td>{pill(h.get("status", ""))}</td><td>{e(h.get("by", ""))}</td><td>{e(h.get("at", "")[:16].replace("T", " "))}</td><td>{e(h.get("notes", ""))}</td></tr>'
        for h in reversed(c.get("history", [])))
    parts = [f'<p><a href="/">Back to plan</a></p>']
    if message:
        parts.append(f'<div class="msg" role="alert">{e(message)}</div>')
    parts.append(
        f'<div class="card"><p class="muted">{e(c["id"])} · {e(c.get("type", ""))} · {e(c.get("area") or c.get("suite", ""))}'
        f'{" · priority " + e(c["priority"]) if c.get("priority") else ""}</p><h1>{e(c.get("title", ""))}</h1><p>{pill(c.get("status", "not_run"))} '
        f'<span class="muted">{e(c.get("last_run_by", ""))} {e(c.get("last_run_at", "")[:16].replace("T", " "))}</span></p>')
    if c.get("objective"):
        parts.append(f'<h3>Objective</h3><p>{e(c["objective"])}</p>')
    if c.get("preconditions"):
        parts.append(f'<h3>Preconditions</h3><p>{e(c["preconditions"])}</p>')
    if steps:
        parts.append(f'<h3>Steps</h3><ol>{steps}</ol>')
    if c.get("automation"):
        parts.append(f'<h3>Automation</h3><p><code>{e(c["automation"])}</code></p>')
    if c.get("source"):
        parts.append(f'<p class="muted">Result reported by {e(c["source"])}.</p>')
    if c.get("failure"):
        parts.append(f'<h3>Failure detail</h3><p><code>{e(c["failure"])}</code></p>')
    if c.get("standard"):
        parts.append(f'<h3>Standard</h3><p>{e(c["standard"])}</p>')
    if c.get("defects"):
        parts.append(f'<h3>Linked defects</h3><p>{e(", ".join(c["defects"]))}</p>')
    if c.get("notes"):
        parts.append(f'<h3>Latest notes</h3><p>{e(c["notes"])}</p>')
    parts.append("</div>")
    if c.get("type") == "manual":
        options = "".join(f'<option value="{s}">{s.replace("_", " ")}</option>' for s in STATUSES if s != "not_run")
        parts.append(
            f'<div class="card"><h2>Record a result</h2><form method="post" action="/case/{quote(c["id"])}/result">'
            f'<label for="status">Result</label><select id="status" name="status">{options}</select>'
            f'<label for="tester">Tester</label><input id="tester" name="tester" maxlength="60" required>'
            f'<label for="notes">Notes</label><textarea id="notes" name="notes" rows="3" maxlength="1000"></textarea>'
            f'<label for="key">Tester key</label><input id="key" name="key" type="password" autocomplete="off" required>'
            f'<button type="submit">Save result</button></form></div>')
        if history:
            parts.append(f'<div class="card"><h2>History</h2><div class="wrap"><table><thead><tr><th scope="col">Result</th><th scope="col">Tester</th><th scope="col">When (UTC)</th><th scope="col">Notes</th></tr></thead><tbody>{history}</tbody></table></div></div>')
    return page(f'{c["id"]} - QA Test Plan', "".join(parts), status)


# ---------- routing ----------

def _json(status: int, payload) -> dict:
    return {"statusCode": status, "headers": {**HEADERS, "Content-Type": "application/json"}, "body": json.dumps(payload)}


def handler(event, context=None):
    http = event.get("requestContext", {}).get("http", {})
    method, path = http.get("method", "GET"), event.get("rawPath", "/")
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    try:
        if method == "GET" and path == "/static.css":
            return {"statusCode": 200, "headers": {**HEADERS, "Content-Type": "text/css; charset=utf-8", "Cache-Control": "max-age=300"}, "body": CSS}
        if method == "GET" and path == "/":
            return render_plan(all_cases())
        if method == "GET" and path == "/api/cases":
            return _json(200, {"plan": PLAN_NAME, "cases": all_cases()})
        if path.startswith("/case/"):
            rest = path[len("/case/"):]
            if method == "GET" and "/" not in rest:
                case = get_case(rest)
                return render_case(case) if case else page("Not found", "<p>No such test case.</p>", 404)
            if method == "POST" and rest.endswith("/result"):
                case = get_case(rest[: -len("/result")])
                if not case:
                    return page("Not found", "<p>No such test case.</p>", 404)
                if headers.get("sec-fetch-site") not in (None, "same-origin", "none"):
                    return page("Refused", "<p>Cross-site submission refused.</p>", 403)
                raw = event.get("body") or ""
                if event.get("isBase64Encoded"):
                    raw = base64.b64decode(raw).decode("utf-8", "replace")
                form = {k: v[0] for k, v in parse_qs(raw[:8000]).items()}
                if not KEY or not hmac.compare_digest(form.get("key", "").encode(), KEY.encode()):
                    return render_case(case, "That tester key is not correct. Nothing was saved.", 401)
                status = form.get("status", "")
                tester = form.get("tester", "").strip()[:60]
                if case.get("type") != "manual" or status not in STATUSES or status == "not_run" or not tester:
                    return render_case(case, "Choose a result and enter your name.", 400)
                record_result(case["id"], status, tester, form.get("notes", "").strip()[:1000])
                return {"statusCode": 303, "headers": {**HEADERS, "Location": f'/case/{quote(case["id"])}'}, "body": ""}
        return page("Not found", "<p>Page not found.</p>", 404)
    except Exception:  # fail safely: detail goes to CloudWatch, not to the browser
        import traceback

        traceback.print_exc()
        return page("Error", "<p>Something went wrong.</p>", 500)
