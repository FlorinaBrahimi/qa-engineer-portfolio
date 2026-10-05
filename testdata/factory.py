"""Test data management.

Two sources of data are used across the suites:

* Static fixtures in ``submissions.json`` for scenarios whose exact outcome matters
  (e.g. a text that is 100% in the corpus must be flagged).
* ``SubmissionFactory`` for everything else, generating unique, non-colliding records so
  tests can run in parallel (``pytest -n auto``) without sharing state.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path

_FIXTURES = json.loads((Path(__file__).parent / "submissions.json").read_text())


def fixture(name: str) -> dict:
    """Return a copy of a named static fixture."""
    return dict(_FIXTURES[name])


class SubmissionFactory:
    _counter = 0

    @classmethod
    def build(cls, **overrides) -> dict:
        cls._counter += 1
        unique = uuid.uuid4().hex[:8]
        data = {
            "title": f"Generated paper {cls._counter}-{unique}",
            "author": f"author-{unique}",
            "text": f"Original sentence number {unique} written specifically for test run {cls._counter} "
                    "so that it shares no five-word shingle with the known corpus.",
        }
        data.update(overrides)
        return data

    @classmethod
    def build_many(cls, n: int, **overrides) -> list[dict]:
        return [cls.build(**overrides) for _ in range(n)]
