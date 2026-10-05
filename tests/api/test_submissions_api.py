"""API automation: functional + regression coverage of /api/submissions.

Maps to test cases TC-API-001 .. TC-API-012 in docs/03_test_cases.md.
"""
import pytest

from testdata.factory import SubmissionFactory

pytestmark = [pytest.mark.api, pytest.mark.regression]


@pytest.mark.smoke
def test_health_endpoint_is_up(api, base_url):
    resp = api.get(f"{base_url}/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.smoke
def test_create_submission_returns_201_with_expected_shape(api, base_url, submission_payload):
    resp = api.post(f"{base_url}/api/submissions", json=submission_payload)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert set(body) >= {"id", "title", "author", "word_count", "similarity_score", "status", "created_at"}
    assert body["title"] == submission_payload["title"]
    assert body["author"] == submission_payload["author"]
    assert 0.0 <= body["similarity_score"] <= 100.0
    api.delete(f"{base_url}/api/submissions/{body['id']}")


def test_fully_copied_text_is_flagged(api, base_url, fixtures):
    resp = api.post(f"{base_url}/api/submissions", json=fixtures("plagiarised_paper"))
    assert resp.status_code == 201
    body = resp.json()
    assert body["similarity_score"] == 100.0
    assert body["status"] == "flagged"


def test_original_text_is_clear(api, base_url, fixtures):
    resp = api.post(f"{base_url}/api/submissions", json=fixtures("clean_paper"))
    assert resp.status_code == 201
    body = resp.json()
    assert body["similarity_score"] == 0.0
    assert body["status"] == "clear"


def test_partial_overlap_scores_between_bounds(api, base_url, fixtures):
    body = api.post(f"{base_url}/api/submissions", json=fixtures("partial_overlap_paper")).json()
    assert 0.0 < body["similarity_score"] < 100.0


def test_word_count_is_accurate(api, base_url):
    payload = SubmissionFactory.build(text="one two three four five six seven eight nine ten eleven twelve")
    body = api.post(f"{base_url}/api/submissions", json=payload).json()
    assert body["word_count"] == 12


def test_get_submission_by_id(api, base_url, created_submission):
    resp = api.get(f"{base_url}/api/submissions/{created_submission['id']}")
    assert resp.status_code == 200
    assert resp.json() == created_submission


def test_list_contains_created_submission(api, base_url, created_submission):
    items = api.get(f"{base_url}/api/submissions").json()["items"]
    assert any(i["id"] == created_submission["id"] for i in items)


def test_delete_then_get_returns_404(api, base_url, submission_payload):
    created = api.post(f"{base_url}/api/submissions", json=submission_payload).json()
    assert api.delete(f"{base_url}/api/submissions/{created['id']}").status_code == 204
    assert api.get(f"{base_url}/api/submissions/{created['id']}").status_code == 404


def test_unknown_id_returns_404(api, base_url):
    assert api.get(f"{base_url}/api/submissions/does-not-exist").status_code == 404
    assert api.delete(f"{base_url}/api/submissions/does-not-exist").status_code == 404


@pytest.mark.parametrize(
    "fixture_name, bad_field",
    [("invalid_missing_title", "title"), ("invalid_short_text", "text")],
)
def test_validation_errors_name_the_field(api, base_url, fixtures, fixture_name, bad_field):
    resp = api.post(f"{base_url}/api/submissions", json=fixtures(fixture_name))
    assert resp.status_code == 400
    body = resp.json()
    assert body["error"] == "validation_failed"
    assert bad_field in body["fields"]


@pytest.mark.parametrize("payload", [None, [], "string", 42])
def test_non_object_body_is_rejected(api, base_url, payload):
    resp = api.post(f"{base_url}/api/submissions", json=payload)
    assert resp.status_code == 400


def test_title_boundary_200_chars_accepted_201_rejected(api, base_url):
    ok = api.post(f"{base_url}/api/submissions", json=SubmissionFactory.build(title="t" * 200))
    too_long = api.post(f"{base_url}/api/submissions", json=SubmissionFactory.build(title="t" * 201))
    assert ok.status_code == 201
    assert too_long.status_code == 400
