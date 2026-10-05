"""Security testing basics: authentication, hardening headers, injection handling."""
import pytest

from testdata.factory import SubmissionFactory
from tests.ui.pages.submission_page import SubmissionPage

pytestmark = [pytest.mark.security, pytest.mark.regression]

PROTECTED = [("get", "/api/submissions"), ("post", "/api/submissions"), ("get", "/api/submissions/x"), ("delete", "/api/submissions/x")]


@pytest.mark.parametrize("method, path", PROTECTED)
def test_endpoints_reject_missing_api_key(anon, base_url, method, path):
    resp = getattr(anon, method)(f"{base_url}{path}", json={})
    assert resp.status_code == 401
    assert resp.json() == {"error": "unauthorized"}


def test_wrong_api_key_is_rejected(anon, base_url):
    resp = anon.get(f"{base_url}/api/submissions", headers={"X-API-Key": "wrong"})
    assert resp.status_code == 401


@pytest.mark.parametrize(
    "header, expected",
    [
        ("X-Content-Type-Options", "nosniff"),
        ("X-Frame-Options", "DENY"),
        ("Content-Security-Policy", "default-src 'self'"),
        ("Referrer-Policy", "no-referrer"),
    ],
)
def test_hardening_headers_present(anon, base_url, header, expected):
    resp = anon.get(f"{base_url}/")
    assert resp.headers.get(header) == expected


INJECTION_PAYLOADS = [
    "<script>alert('xss')</script>",
    "' OR 1=1 --",
    "{{ 7 * 7 }}",
    "../../etc/passwd",
    "\u0000null byte",
]


@pytest.mark.parametrize("payload", INJECTION_PAYLOADS)
def test_injection_payloads_are_stored_verbatim_not_executed(api, base_url, payload):
    body = api.post(f"{base_url}/api/submissions", json=SubmissionFactory.build(title=payload)).json()
    assert body["title"] == payload
    api.delete(f"{base_url}/api/submissions/{body['id']}")


def test_script_in_title_is_escaped_in_ui(page, clean_store):
    xss = "<script>window.__pwned=true</script>"
    home = SubmissionPage(page).open().submit(title=xss, author="Mallory", text="x" * 30)
    assert page.evaluate("window.__pwned") is None
    assert home.row_for_title("script").is_visible()
    assert "&lt;script&gt;" in page.content()
