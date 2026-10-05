"""OWASP API Security Top 10 (2023).

One section per risk. Each test names the risk it covers; risks that do not apply to this
service are recorded, with the reason, in docs/12_security.md rather than tested vacuously.
"""
import re
import uuid

import pytest
import requests

from testdata.factory import SubmissionFactory
from tests.security.conftest import FULL_FIELDS, PROTECTED

pytestmark = [pytest.mark.security, pytest.mark.regression]


# ---------- API1:2023 Broken Object Level Authorization ----------
# The service is single-tenant (one API key, no per-user ownership), so there is no other
# user's object to reach. What still matters is that object ids cannot be enumerated.

def test_api1_object_ids_are_random_uuids_not_sequential(api, base_url):
    ids = []
    for _ in range(5):
        body = api.post(f"{base_url}/api/submissions", json=SubmissionFactory.build()).json()
        ids.append(body["id"])
    try:
        for i in ids:
            assert uuid.UUID(i).version == 4
        assert len(set(ids)) == 5
        assert len({i[:8] for i in ids}) == 5, "ids share a prefix, which suggests a guessable sequence"
    finally:
        for i in ids:
            api.delete(f"{base_url}/api/submissions/{i}")


# ---------- API2:2023 Broken Authentication ----------

@pytest.mark.parametrize("method, path", PROTECTED)
def test_api2_every_endpoint_rejects_a_missing_key(anon, base_url, method, path):
    resp = getattr(anon, method)(f"{base_url}{path}", json={})
    assert resp.status_code == 401
    assert resp.json() == {"error": "unauthorized"}


@pytest.mark.parametrize(
    "bad_key",
    ["wrong", "", "qa demo key", "QA-DEMO-KEY", "qa-demo-key ", "null", "undefined", "' OR '1'='1", "qa-demo-ke", "*"],
    ids=["wrong", "empty", "embedded-spaces", "upper-cased-default", "trailing-space", "null", "undefined", "sql-ish", "truncated-default", "wildcard"],
)
def test_api2_invalid_keys_are_rejected(anon, base_url, bad_key, api):
    if bad_key == api.headers["X-API-Key"]:
        pytest.skip("this value is the configured key in this environment")
    resp = anon.get(f"{base_url}/api/submissions", headers={"X-API-Key": bad_key})
    assert resp.status_code == 401


def test_api2_key_is_only_accepted_in_the_header_never_the_url(anon, base_url, api):
    """Keys in URLs end up in logs, browser history and Referer headers."""
    key = api.headers["X-API-Key"]
    for param in ("api_key", "apikey", "key", "X-API-Key", "access_token"):
        assert anon.get(f"{base_url}/api/submissions", params={param: key}).status_code == 401


def test_api2_missing_and_wrong_key_are_indistinguishable(anon, base_url):
    """No oracle: the response must not reveal whether a key was close."""
    missing = anon.get(f"{base_url}/api/submissions")
    wrong = anon.get(f"{base_url}/api/submissions", headers={"X-API-Key": "x" * 50})
    assert (missing.status_code, missing.json()) == (wrong.status_code, wrong.json())


def test_api2_key_comparison_is_constant_time():
    """A plain == leaks, through timing, how many leading characters matched (CWE-208)."""
    import inspect
    from app import server

    source = inspect.getsource(server.require_api_key)
    assert "hmac.compare_digest" in source
    assert "!= API_KEY" not in source and "== API_KEY" not in source.replace("API_KEY == DEFAULT_API_KEY", "")


def test_api2_deployment_with_the_public_default_key_fails_closed(client, monkeypatch):
    """If a deployment ever ships with the well-known default, nobody gets in, including
    someone who knows that default (CWE-798, CWE-1188)."""
    from app import server

    monkeypatch.setattr(server, "ON_AWS", True)
    monkeypatch.setattr(server, "API_KEY", server.DEFAULT_API_KEY)
    resp = client.get("/api/submissions", headers={"X-API-Key": server.DEFAULT_API_KEY})
    assert resp.status_code == 401


# ---------- API3:2023 Broken Object Property Level Authorization ----------

def test_api3_client_cannot_set_server_owned_properties(api, base_url):
    """Mass assignment: id, score, status and timestamp are decided by the server."""
    payload = SubmissionFactory.build(text="The mitochondria is the powerhouse of the cell and produces energy through respiration")
    payload.update({"id": "attacker-chosen", "status": "clear", "similarity_score": 0, "word_count": 1, "created_at": "1999-01-01T00:00:00Z"})
    body = api.post(f"{base_url}/api/submissions", json=payload).json()
    try:
        assert body["id"] != "attacker-chosen"
        assert body["status"] == "flagged" and body["similarity_score"] == 100.0
        assert body["word_count"] == 13
        assert not body["created_at"].startswith("1999")
    finally:
        api.delete(f"{base_url}/api/submissions/{body['id']}")


def test_api3_responses_expose_only_documented_properties(api, base_url, created_submission):
    """Excessive data exposure: no internal fields (raw text, keys, table names) leak out."""
    one = api.get(f"{base_url}/api/submissions/{created_submission['id']}").json()
    assert set(one) == FULL_FIELDS
    assert "text" not in one, "the submitted paper text must not be echoed back"
    listed = api.get(f"{base_url}/api/submissions").json()
    assert set(listed) == {"items", "count", "total"}
    assert all(set(item) == FULL_FIELDS for item in listed["items"])


# ---------- API4:2023 Unrestricted Resource Consumption ----------

def test_api4_oversized_request_body_is_refused_before_processing(api, base_url):
    huge = SubmissionFactory.build(text="x" * 400_000)
    try:
        resp = api.post(f"{base_url}/api/submissions", json=huge)
    except requests.ConnectionError:
        return  # server closed the connection without reading the body: also a refusal
    assert resp.status_code == 413
    assert resp.json() == {"error": "payload_too_large"}


@pytest.mark.parametrize("field, limit", [("title", 200), ("author", 200), ("text", 20_000)])
def test_api4_every_text_field_has_an_enforced_maximum(api, base_url, field, limit):
    at_limit = api.post(f"{base_url}/api/submissions", json=SubmissionFactory.build(**{field: "y" * limit}))
    over = api.post(f"{base_url}/api/submissions", json=SubmissionFactory.build(**{field: "y" * (limit + 1)}))
    assert at_limit.status_code == 201
    api.delete(f"{base_url}/api/submissions/{at_limit.json()['id']}")
    assert over.status_code == 400 and field in over.json()["fields"]


def test_api4_list_size_is_bounded_and_limit_is_honoured(api, base_url):
    created = [api.post(f"{base_url}/api/submissions", json=p).json()["id"] for p in SubmissionFactory.build_many(3)]
    try:
        page = api.get(f"{base_url}/api/submissions", params={"limit": 2}).json()
        assert page["count"] == 2 and len(page["items"]) == 2 and page["total"] >= 3
    finally:
        for i in created:
            api.delete(f"{base_url}/api/submissions/{i}")


@pytest.mark.parametrize("limit", ["0", "-1", "501", "1000000", "abc", "1.5", "1 OR 1=1", ""])
def test_api4_out_of_range_limit_is_rejected(api, base_url, limit):
    resp = api.get(f"{base_url}/api/submissions", params={"limit": limit})
    assert resp.status_code == 400 and "limit" in resp.json()["fields"]


# ---------- API5:2023 Broken Function Level Authorization ----------
# One role only, so there is no privileged function to escalate to. The check that remains
# is that no administrative, debug or framework endpoint is reachable at all.

@pytest.mark.parametrize(
    "path",
    ["/admin", "/api/admin", "/debug", "/console", "/api/users", "/api/config", "/api/v1/submissions",
     "/.env", "/.git/config", "/server-status", "/actuator/health", "/swagger", "/api/docs", "/metrics", "/static/../app/server.py"],
)
def test_api5_no_admin_debug_or_hidden_endpoints_exist(api, base_url, path):
    resp = api.get(f"{base_url}{path}", allow_redirects=False)
    assert resp.status_code == 404
    assert "SUBMISSION_API_KEY" not in resp.text and "import " not in resp.text


# ---------- API8:2023 Security Misconfiguration ----------

@pytest.mark.parametrize("method", ["PUT", "PATCH", "TRACE", "CONNECT"])
def test_api8_unsupported_methods_are_refused_with_json(api, base_url, method):
    resp = api.request(method, f"{base_url}/api/submissions")
    assert resp.status_code in (405, 400, 501)
    if resp.status_code == 405:
        assert resp.json() == {"error": "method_not_allowed"}


def test_api8_api_errors_are_json_not_framework_pages(api, base_url):
    resp = api.get(f"{base_url}/api/does-not-exist")
    assert resp.status_code == 404
    assert resp.headers["Content-Type"].startswith("application/json")
    assert resp.json() == {"error": "not_found"}
    assert "<html" not in resp.text.lower()


def test_api8_no_cross_origin_access_is_granted(api, base_url):
    """No CORS headers means browsers on other sites cannot read API responses."""
    for method in ("get", "options"):
        resp = api.request(method, f"{base_url}/api/submissions", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
        assert "Access-Control-Allow-Origin" not in resp.headers
        assert "Access-Control-Allow-Credentials" not in resp.headers


def test_api8_static_directory_is_not_browsable(anon, base_url):
    assert anon.get(f"{base_url}/static/").status_code == 404


def test_api8_server_technology_is_not_disclosed(anon, base_url):
    for path in ("/", "/health", "/api/submissions", "/api/nope"):
        resp = anon.get(f"{base_url}{path}")
        blob = " ".join(f"{k}: {v}" for k, v in resp.headers.items()).lower()
        for marker in ("werkzeug", "python", "flask", "x-powered-by"):
            assert marker not in blob, f"{marker} disclosed on {path}"


def test_api8_internal_errors_reveal_nothing(client, monkeypatch):
    """Force a crash inside the app and check the client sees only a generic message."""
    from app import server

    def boom():
        raise RuntimeError("secret internal detail: table=prod-submissions")

    monkeypatch.setattr(server.store, "list", boom)
    resp = client.get("/api/submissions", headers={"X-API-Key": server.API_KEY})
    assert resp.status_code == 500
    assert resp.get_json() == {"error": "internal_error"}
    assert b"secret internal detail" not in resp.data and b"Traceback" not in resp.data


# ---------- API9:2023 Improper Inventory Management ----------

def test_api9_published_contract_matches_the_routes_that_exist():
    """Undocumented endpoints are the ones nobody tests or patches."""
    from app import server

    with server.app.test_client() as c:
        documented = set(c.get("/api/openapi.json").get_json()["paths"])
    actual = {re.sub(r"<[^>]+>", "{id}", r.rule) for r in server.app.url_map.iter_rules() if r.rule.startswith("/api/") and r.rule != "/api/openapi.json"}
    assert actual == documented
