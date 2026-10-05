"""Fixtures for the security suite."""
import os

import pytest

FULL_FIELDS = {"id", "title", "author", "word_count", "similarity_score", "status", "created_at"}
PROTECTED = [("get", "/api/submissions"), ("post", "/api/submissions"), ("get", "/api/submissions/x"), ("delete", "/api/submissions/x")]
WCAG_NONE = None


@pytest.fixture
def client():
    """Flask's in-process test client. Used where a test needs to reach inside the app
    (log capture, forcing an internal error), which cannot be done over HTTP."""
    from app import server

    return server.app.test_client()


@pytest.fixture
def remote() -> bool:
    return bool(os.environ.get("BASE_URL"))
