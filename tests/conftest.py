"""Shared fixtures.

The Submission Service is started in-process on a free port for the whole session unless
``BASE_URL`` is set, in which case tests run against that deployed environment instead
(this is how the same suite targets local, Docker, staging and production-like stacks).
"""
from __future__ import annotations

import os
import socket
import threading

import pytest
import requests
from werkzeug.serving import make_server

from app import server as app_server
from testdata.factory import SubmissionFactory, fixture

API_KEY = os.environ.get("SUBMISSION_API_KEY", "qa-demo-key")


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def base_url() -> str:
    external = os.environ.get("BASE_URL")
    if external:
        yield external.rstrip("/")
        return

    port = _free_port()
    httpd = make_server("127.0.0.1", port, app_server.app, threaded=True)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        thread.join(timeout=5)


@pytest.fixture(scope="session")
def api(base_url: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"X-API-Key": API_KEY, "Content-Type": "application/json"})
    session.base_url = base_url  # type: ignore[attr-defined]
    return session


@pytest.fixture
def anon(base_url: str) -> requests.Session:
    """A client with no credentials, for negative auth tests."""
    session = requests.Session()
    session.base_url = base_url  # type: ignore[attr-defined]
    return session


@pytest.fixture
def clean_store(base_url: str):
    """Reset state before a test that asserts on list contents.

    Only works for the in-process server; against an external BASE_URL we delete via the
    API instead so the same test stays valid on a deployed environment.
    """
    if os.environ.get("BASE_URL"):
        s = requests.Session()
        s.headers["X-API-Key"] = API_KEY
        for item in s.get(f"{base_url}/api/submissions").json()["items"]:
            s.delete(f"{base_url}/api/submissions/{item['id']}")
    else:
        app_server.reset_store()
    yield


@pytest.fixture
def submission_payload() -> dict:
    return SubmissionFactory.build()


@pytest.fixture
def created_submission(api, base_url, submission_payload) -> dict:
    resp = api.post(f"{base_url}/api/submissions", json=submission_payload)
    assert resp.status_code == 201, resp.text
    data = resp.json()
    yield data
    api.delete(f"{base_url}/api/submissions/{data['id']}")


@pytest.fixture
def fixtures():
    return fixture


# ---------- Playwright ----------

@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=os.environ.get("HEADED") != "1")
        yield browser
        browser.close()


@pytest.fixture
def page(browser, base_url):
    context = browser.new_context(base_url=base_url)
    page = context.new_page()
    yield page
    context.close()


@pytest.fixture
def mobile_page(browser, base_url):
    """iPhone-sized viewport with touch enabled, for responsive checks without a device farm."""
    context = browser.new_context(
        base_url=base_url,
        viewport={"width": 390, "height": 844},
        device_scale_factor=3,
        is_mobile=True,
        has_touch=True,
        user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
    )
    page = context.new_page()
    yield page
    context.close()
