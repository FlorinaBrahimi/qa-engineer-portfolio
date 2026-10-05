"""OWASP Secure Headers Project: required response headers, on every kind of response."""
import pytest

pytestmark = [pytest.mark.security, pytest.mark.regression]

REQUIRED = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains",
}
PATHS = ["/", "/accessibility", "/health", "/api/submissions", "/api/does-not-exist", "/static/style.css", "/no-such-page"]


@pytest.mark.parametrize("path", PATHS)
def test_required_headers_are_on_every_response_including_errors(anon, base_url, path):
    resp = anon.get(f"{base_url}{path}")
    for header, expected in REQUIRED.items():
        assert resp.headers.get(header) == expected, f"{header} on {path}"


def test_content_security_policy_is_restrictive(anon, base_url):
    csp = {d.split()[0]: d.split()[1:] for d in anon.get(f"{base_url}/").headers["Content-Security-Policy"].split("; ")}
    assert csp["default-src"] == ["'self'"]
    assert csp["object-src"] == ["'none'"]
    assert csp["frame-ancestors"] == ["'none'"], "clickjacking defence"
    assert csp["base-uri"] == ["'self'"] and csp["form-action"] == ["'self'"]
    flat = " ".join(sum(csp.values(), []))
    assert "'unsafe-inline'" not in flat and "'unsafe-eval'" not in flat and "*" not in flat


def test_permissions_policy_disables_unused_browser_features(anon, base_url):
    policy = anon.get(f"{base_url}/").headers["Permissions-Policy"]
    for feature in ("camera", "microphone", "geolocation", "payment"):
        assert f"{feature}=()" in policy


@pytest.mark.parametrize("path", ["/", "/health", "/api/submissions"])
def test_pages_and_api_responses_are_never_cached(anon, base_url, path):
    assert anon.get(f"{base_url}{path}").headers.get("Cache-Control") == "no-store"


def test_static_assets_are_not_marked_no_store(anon, base_url):
    assert anon.get(f"{base_url}/static/style.css").headers.get("Cache-Control") != "no-store"


def test_no_cookies_are_set(anon, base_url):
    """The service is stateless; a cookie would be an unreviewed session mechanism."""
    for path in ("/", "/health", "/api/submissions"):
        assert "Set-Cookie" not in anon.get(f"{base_url}{path}").headers
