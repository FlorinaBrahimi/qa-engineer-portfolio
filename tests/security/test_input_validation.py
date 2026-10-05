"""OWASP ASVS V5 (Validation, Sanitization and Encoding) and Top 10 Injection."""
import pytest

from testdata.factory import SubmissionFactory
from tests.ui.pages.submission_page import SubmissionPage

pytestmark = [pytest.mark.security, pytest.mark.regression]

INJECTION_PAYLOADS = {
    "script-tag": "<script>alert('xss')</script>",
    "img-onerror": "<img src=x onerror=alert(1)>",
    "svg-onload": "<svg/onload=alert(1)>",
    "attribute-breakout": "\"><script>alert(1)</script>",
    "javascript-uri": "javascript:alert(1)",
    "sql": "' OR 1=1 --",
    "sql-stacked": "'; DROP TABLE submissions; --",
    "nosql-operator": "{\"$ne\": null}",
    "template": "{{ 7 * 7 }}",
    "template-config": "{{ config.items() }}",
    "path-traversal": "../../etc/passwd",
    "command": "; cat /etc/passwd #",
    "crlf": "line1\r\nSet-Cookie: injected=1",
    "null-byte": "\u0000null byte",
    "unicode-rtl": "‮gnp.exe",
}


@pytest.mark.parametrize("payload", INJECTION_PAYLOADS.values(), ids=INJECTION_PAYLOADS.keys())
def test_hostile_input_is_stored_as_inert_text(api, base_url, payload):
    """Stored verbatim, returned verbatim, never interpreted, never a 500."""
    resp = api.post(f"{base_url}/api/submissions", json=SubmissionFactory.build(title=payload, author=payload))
    assert resp.status_code == 201, resp.text
    body = resp.json()
    try:
        assert body["title"] == payload.strip() and body["author"] == payload.strip()
        assert "injected" not in resp.headers.get("Set-Cookie", "")
        assert api.get(f"{base_url}/api/submissions/{body['id']}").json()["title"] == payload.strip()
    finally:
        api.delete(f"{base_url}/api/submissions/{body['id']}")


def test_template_expressions_are_not_evaluated(api, base_url):
    body = api.post(f"{base_url}/api/submissions", json=SubmissionFactory.build(title="{{ 7 * 7 }}")).json()
    try:
        assert body["title"] == "{{ 7 * 7 }}" and "49" not in body["title"]
    finally:
        api.delete(f"{base_url}/api/submissions/{body['id']}")


@pytest.mark.parametrize("bad_id", ["../../etc/passwd", "..%2f..%2fetc%2fpasswd", "%00", "' OR '1'='1", "<script>", "a" * 5000])
def test_hostile_object_ids_return_404_not_an_error(api, base_url, bad_id):
    for method in ("get", "delete"):
        resp = getattr(api, method)(f"{base_url}/api/submissions/{bad_id}")
        assert resp.status_code in (404, 400, 414), f"{method} gave {resp.status_code}"
        assert "Traceback" not in resp.text


def test_only_well_formed_uuids_reach_storage(client, monkeypatch):
    """Ids that cannot be valid are answered without a storage call (found live: DEF-115)."""
    from app import server

    calls = []
    monkeypatch.setattr(server.store, "get", lambda i: calls.append(i))
    for bad in ("x", "a" * 5000, "123", "not-a-uuid", "00000000-0000-0000-0000-00000000000g"):
        assert client.get(f"/api/submissions/{bad}", headers={"X-API-Key": server.API_KEY}).status_code == 404
    assert calls == []


@pytest.mark.parametrize("content_type", ["text/plain", "application/xml", "application/x-www-form-urlencoded", "multipart/form-data"])
def test_api_only_accepts_json(api, base_url, content_type):
    resp = api.post(f"{base_url}/api/submissions", data='{"title": "a"}', headers={"Content-Type": content_type})
    assert resp.status_code == 415
    assert resp.json() == {"error": "unsupported_media_type"}


@pytest.mark.parametrize("body", ["{bad", "", "null", "[]", "42", "\"text\"", "{\"title\": \"a\"" , "﻿{}"])
def test_malformed_or_non_object_json_is_rejected_cleanly(api, base_url, body):
    resp = api.post(f"{base_url}/api/submissions", data=body.encode())
    assert resp.status_code == 400
    assert resp.headers["Content-Type"].startswith("application/json")


@pytest.mark.parametrize("wrong", [123, 1.5, True, [], {}, ["a"]])
def test_wrong_json_types_are_rejected_not_coerced(api, base_url, wrong):
    resp = api.post(f"{base_url}/api/submissions", json=SubmissionFactory.build(title=wrong))
    assert resp.status_code == 400 and resp.json()["fields"]["title"] == "title must be a string"


# ---------- Output encoding in the browser ----------

XSS = "<script>window.__pwned=true</script><img src=x onerror=\"window.__pwned=true\">"


def test_stored_xss_is_escaped_in_the_results_table(page, clean_store):
    home = SubmissionPage(page).open().submit(title=XSS, author=XSS, text="x" * 30)
    home.row_for_title("script").wait_for()
    assert page.evaluate("window.__pwned") is None
    assert "&lt;script&gt;" in page.content()


def test_xss_is_escaped_in_the_success_message(page, clean_store):
    """The confirmation message echoes the title, so it is a second place to encode."""
    SubmissionPage(page).open().submit(title=XSS, author="Mallory", text="x" * 30)
    status = page.get_by_test_id("status-message")
    status.wait_for()
    assert "<script>" in status.inner_text(), "shown as text"
    assert page.evaluate("window.__pwned") is None
    assert status.locator("script, img").count() == 0


def test_reflected_xss_is_escaped_when_the_form_is_redisplayed(page):
    """A rejected submission is re-rendered with the user's input: reflected XSS territory."""
    SubmissionPage(page).open().submit(title=XSS, author="", text="x" * 30)
    page.get_by_test_id("error-summary").wait_for()
    assert page.evaluate("window.__pwned") is None
    assert page.locator("#title").input_value() == XSS


def test_inline_script_injected_into_the_page_is_blocked_by_csp(page):
    """Defence in depth: even if encoding failed, the CSP refuses inline script."""
    SubmissionPage(page).open()
    page.evaluate("() => { const s = document.createElement('script'); s.textContent = 'window.__inline = true'; document.body.appendChild(s); }")
    assert page.evaluate("window.__inline") is None


def test_added_query_parameter_cannot_inject_content(anon, base_url):
    resp = anon.get(f"{base_url}/", params={"added": "<script>alert(1)</script>"})
    assert resp.status_code == 200 and "<script>alert(1)</script>" not in resp.text
