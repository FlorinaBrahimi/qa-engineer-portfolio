"""OWASP Top 10 Security Logging and Alerting Failures; ASVS V7.

These reach inside the app to capture its logs, so they use the in-process test client.
"""
import logging

import pytest

pytestmark = [pytest.mark.security, pytest.mark.regression]


def test_failed_authentication_is_logged_with_context(client, caplog):
    with caplog.at_level(logging.WARNING, logger="submission_service.audit"):
        client.get("/api/submissions", headers={"X-API-Key": "guess-123", "X-Forwarded-For": "203.0.113.9"})
    record = "\n".join(caplog.messages)
    assert "auth_failed" in record
    assert "method=GET" in record and "path=/api/submissions" in record and "ip=203.0.113.9" in record


def test_supplied_key_is_never_written_to_the_log(client, caplog):
    """Logs are widely readable; a near-miss key in a log is a credential leak (CWE-532)."""
    with caplog.at_level(logging.DEBUG):
        client.get("/api/submissions", headers={"X-API-Key": "almost-the-real-key-9f3a"})
    assert "almost-the-real-key-9f3a" not in caplog.text
    assert "key_supplied=True" in caplog.text


def test_blocked_cross_site_post_is_logged(client, caplog):
    with caplog.at_level(logging.WARNING, logger="submission_service.audit"):
        client.post("/submit", data={"title": "t"}, headers={"Sec-Fetch-Site": "cross-site", "Origin": "https://evil.example"})
    assert "cross_site_form_post_blocked" in caplog.text and "evil.example" in caplog.text


def test_successful_requests_do_not_log_submission_content(client, caplog):
    from app import server

    with caplog.at_level(logging.DEBUG):
        resp = client.post("/api/submissions", headers={"X-API-Key": server.API_KEY},
                           json={"title": "Private thesis title", "author": "Private Name", "text": "Confidential body text of the paper."})
    assert resp.status_code == 201
    server.store.delete(resp.get_json()["id"])
    assert "Confidential body text" not in caplog.text and "Private Name" not in caplog.text
