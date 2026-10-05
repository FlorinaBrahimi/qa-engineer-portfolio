"""Scale testing: the service must stay correct and responsive under concurrent load.

This is a lightweight in-process check that runs in CI on every build. The heavier
JMeter plan in performance/ is for dedicated load runs against a deployed environment.
"""
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests

from testdata.factory import SubmissionFactory

pytestmark = [pytest.mark.scale]

CONCURRENCY = 25
REQUESTS = 100
P95_BUDGET_MS = 500


def _post(base_url: str, api_key: str, payload: dict) -> tuple[int, float, str]:
    started = time.perf_counter()
    resp = requests.post(f"{base_url}/api/submissions", json=payload, headers={"X-API-Key": api_key}, timeout=10)
    elapsed = (time.perf_counter() - started) * 1000
    return resp.status_code, elapsed, resp.json().get("id", "")


def test_concurrent_creates_all_succeed_with_unique_ids(api, base_url):
    payloads = SubmissionFactory.build_many(REQUESTS)
    api_key = api.headers["X-API-Key"]

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        results = list(pool.map(lambda p: _post(base_url, api_key, p), payloads))

    statuses = [r[0] for r in results]
    latencies = sorted(r[1] for r in results)
    ids = [r[2] for r in results]

    assert statuses.count(201) == REQUESTS, f"non-201 responses: {[s for s in statuses if s != 201]}"
    assert len(set(ids)) == REQUESTS, "duplicate IDs under concurrency"

    p95 = latencies[int(len(latencies) * 0.95) - 1]
    print(f"\nmedian={statistics.median(latencies):.1f}ms p95={p95:.1f}ms max={latencies[-1]:.1f}ms")
    assert p95 < P95_BUDGET_MS, f"p95 latency {p95:.1f}ms exceeds budget {P95_BUDGET_MS}ms"

    for sid in ids:
        api.delete(f"{base_url}/api/submissions/{sid}")


def test_list_endpoint_scales_with_store_size(api, base_url):
    created = [api.post(f"{base_url}/api/submissions", json=p).json()["id"] for p in SubmissionFactory.build_many(200)]
    started = time.perf_counter()
    resp = api.get(f"{base_url}/api/submissions")
    elapsed_ms = (time.perf_counter() - started) * 1000
    assert resp.status_code == 200
    assert resp.json()["count"] >= 200
    assert elapsed_ms < 1000
    for sid in created:
        api.delete(f"{base_url}/api/submissions/{sid}")
