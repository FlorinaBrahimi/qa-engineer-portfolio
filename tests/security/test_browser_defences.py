"""Cross-site request forgery and clickjacking (OWASP ASVS V4.2, V14.4)."""
import pytest

pytestmark = [pytest.mark.security, pytest.mark.regression]

FORM = {"title": "Forged", "author": "Attacker", "text": "This form post was triggered by another website."}


def test_cross_site_form_post_is_refused(anon, base_url, api):
    resp = anon.post(f"{base_url}/submit", data=FORM, headers={"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"}, allow_redirects=False)
    assert resp.status_code == 403
    titles = [i["title"] for i in api.get(f"{base_url}/api/submissions").json()["items"]]
    assert "Forged" not in titles, "the forged submission must not be stored"


def test_same_site_subdomain_form_post_is_refused(anon, base_url):
    """same-site is not same-origin: a sibling subdomain must not be trusted either."""
    resp = anon.post(f"{base_url}/submit", data=FORM, headers={"Sec-Fetch-Site": "same-site"}, allow_redirects=False)
    assert resp.status_code == 403


def test_legacy_browser_with_foreign_origin_is_refused(anon, base_url):
    """Browsers without Fetch Metadata fall back to the Origin check."""
    resp = anon.post(f"{base_url}/submit", data=FORM, headers={"Origin": "https://evil.example"}, allow_redirects=False)
    assert resp.status_code == 403


def test_same_origin_form_post_is_accepted(anon, base_url, api):
    resp = anon.post(f"{base_url}/submit", data={**FORM, "title": "Legitimate form post"}, headers={"Sec-Fetch-Site": "same-origin"}, allow_redirects=False)
    assert resp.status_code == 302
    for item in api.get(f"{base_url}/api/submissions").json()["items"]:
        if item["title"] == "Legitimate form post":
            api.delete(f"{base_url}/api/submissions/{item['id']}")


def test_page_cannot_be_framed_by_another_site(anon, base_url):
    headers = anon.get(f"{base_url}/").headers
    assert headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
