"""The AWS test plan app and its sync tool, exercised against a mocked DynamoDB table."""
import json
from pathlib import Path
from urllib.parse import urlencode

import boto3
import pytest
from moto import mock_aws

from tools import test_plan_sync as sync

KEY = "tester-key-for-unit-tests-0001"
MANUAL = Path(__file__).resolve().parents[2] / "testdata" / "test_plan_manual.json"
JUNIT = """<testsuite><testcase classname="tests.security.test_owasp_api_top10" name="test_api2_wrong_key" time="0.01"/>
<testcase classname="tests.api.test_submissions_api" name="test_broken" time="0.2"><failure message="assert 500 == 400">trace</failure></testcase>
<testcase classname="com.turnitin.qa.HealthTest" name="healthIsOk" time="0.3"/>
<testcase classname="tests.mobile.test_mobile" name="test_appium" time="0"><skipped message="no server"/></testcase></testsuite>"""


@pytest.fixture
def app(monkeypatch, tmp_path):
    with mock_aws():
        monkeypatch.setenv("AWS_DEFAULT_REGION", "eu-west-2")
        ddb = boto3.resource("dynamodb", region_name="eu-west-2")
        table = ddb.create_table(TableName="qa-test-plan-cases", BillingMode="PAY_PER_REQUEST",
                                 AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
                                 KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}])
        from testplan import handler as h

        monkeypatch.setattr(h, "_table", table)
        monkeypatch.setattr(h, "KEY", KEY)
        junit = tmp_path / "r.xml"
        junit.write_text(JUNIT)
        sync.sync_manual(table, sync.load_manual(MANUAL))
        sync.sync_automated(table, sync.parse_junit([str(junit)], "unit test", "2026-10-05T12:00:00+00:00"))
        yield h, table


def call(h, method, path, form=None, headers=None):
    event = {"rawPath": path, "requestContext": {"http": {"method": method}}, "headers": headers or {},
             "body": urlencode(form) if form else None, "isBase64Encoded": False}
    return h.handler(event)


def test_plan_page_lists_manual_and_automated_cases_with_counts(app):
    h, _ = app
    resp = call(h, "GET", "/")
    assert resp["statusCode"] == 200
    body = resp["body"]
    assert "TC-MAN-001" in body and "Screen reader pass with VoiceOver" in body
    assert "security / owasp_api_top10" in body and "java / HealthTest" in body
    assert "1 failed" in body, "a suite with a failure is flagged"


def test_every_manual_case_starts_as_not_run(app):
    h, _ = app
    cases = json.loads(call(h, "GET", "/api/cases")["body"])["cases"]
    manual = [c for c in cases if c["type"] == "manual"]
    assert len(manual) == 12 and all(c["status"] == "not_run" for c in manual)
    assert all(c["steps"] and all(s["action"] and s["expected"] for s in c["steps"]) for c in manual)


def test_junit_results_map_to_statuses_and_suites(app):
    h, _ = app
    auto = {c["title"]: c for c in json.loads(call(h, "GET", "/api/cases")["body"])["cases"] if c["type"] == "automated"}
    assert auto["test_api2_wrong_key"]["status"] == "passed"
    assert auto["test_broken"]["status"] == "failed" and "assert 500 == 400" in auto["test_broken"]["failure"]
    assert auto["test_appium"]["status"] == "skipped"
    assert auto["healthIsOk"]["suite"] == "java / HealthTest"


def test_recording_a_result_requires_the_tester_key(app):
    h, _ = app
    resp = call(h, "POST", "/case/TC-MAN-003/result", {"status": "passed", "tester": "Flo", "key": "wrong"})
    assert resp["statusCode"] == 401 and "Nothing was saved" in resp["body"]
    assert h.get_case("TC-MAN-003")["status"] == "not_run"


def test_recording_a_result_updates_status_and_history(app):
    h, _ = app
    resp = call(h, "POST", "/case/TC-MAN-003/result", {"status": "failed", "tester": "Flo", "notes": "Badge misaligned in Safari", "key": KEY})
    assert resp["statusCode"] == 303 and resp["headers"]["Location"] == "/case/TC-MAN-003"
    call(h, "POST", "/case/TC-MAN-003/result", {"status": "passed", "tester": "Flo", "notes": "Retested", "key": KEY})
    case = h.get_case("TC-MAN-003")
    assert case["status"] == "passed" and case["last_run_by"] == "Flo"
    assert [e["status"] for e in case["history"]] == ["failed", "passed"]
    assert "Badge misaligned in Safari" in call(h, "GET", "/case/TC-MAN-003")["body"]


def test_resyncing_definitions_keeps_recorded_results(app):
    h, table = app
    call(h, "POST", "/case/TC-MAN-001/result", {"status": "blocked", "tester": "Flo", "key": KEY})
    sync.sync_manual(table, sync.load_manual(MANUAL))
    case = h.get_case("TC-MAN-001")
    assert case["status"] == "blocked" and len(case["history"]) == 1


def test_automated_cases_cannot_be_overridden_by_hand(app):
    h, _ = app
    auto_id = next(c["id"] for c in h.all_cases() if c["type"] == "automated")
    assert call(h, "POST", f"/case/{auto_id}/result", {"status": "passed", "tester": "Flo", "key": KEY})["statusCode"] == 400


@pytest.mark.parametrize("form", [{"status": "not_run", "tester": "Flo"}, {"status": "bogus", "tester": "Flo"}, {"status": "passed", "tester": " "}])
def test_invalid_results_are_rejected(app, form):
    h, _ = app
    assert call(h, "POST", "/case/TC-MAN-002/result", {**form, "key": KEY})["statusCode"] == 400


def test_cross_site_result_post_is_refused(app):
    h, _ = app
    resp = call(h, "POST", "/case/TC-MAN-002/result", {"status": "passed", "tester": "x", "key": KEY}, headers={"Sec-Fetch-Site": "cross-site"})
    assert resp["statusCode"] == 403


def test_tester_input_is_escaped(app):
    h, _ = app
    call(h, "POST", "/case/TC-MAN-002/result", {"status": "passed", "tester": "<script>alert(1)</script>", "notes": "<img src=x onerror=1>", "key": KEY})
    body = call(h, "GET", "/case/TC-MAN-002")["body"]
    assert "<script>alert(1)</script>" not in body and "&lt;script&gt;" in body
    assert "<img src=x" not in body


def test_unknown_case_and_route_return_404_with_security_headers(app):
    h, _ = app
    for path in ("/case/NOPE", "/admin"):
        resp = call(h, "GET", path)
        assert resp["statusCode"] == 404
        assert resp["headers"]["X-Frame-Options"] == "DENY" and "frame-ancestors 'none'" in resp["headers"]["Content-Security-Policy"]


def test_tester_key_never_appears_in_any_page(app):
    h, _ = app
    for path in ("/", "/case/TC-MAN-001", "/api/cases"):
        assert KEY not in call(h, "GET", path)["body"]
