"""The DynamoDB storage backend and the Lambda handler, exercised with moto so they run
offline. This is the same code path the deployed stack uses."""
import json

import boto3
import pytest
from moto import mock_aws

from app.storage import DynamoStore

pytestmark = [pytest.mark.aws]

REGION = "eu-west-2"
TABLE = "test-submissions"


def _create_table(ddb):
    ddb.create_table(
        TableName=TABLE,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[{"AttributeName": "id", "AttributeType": "S"}],
        KeySchema=[{"AttributeName": "id", "KeyType": "HASH"}],
    )


@pytest.fixture
def dynamo_store():
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name=REGION)
        _create_table(ddb)
        yield DynamoStore(TABLE, dynamodb_resource=ddb)


SUBMISSION = {
    "id": "s-1",
    "title": "t",
    "author": "a",
    "word_count": 12,
    "similarity_score": 33.3,
    "status": "flagged",
    "created_at": "2026-10-05T10:00:00+00:00",
}


def test_put_get_round_trip_preserves_types(dynamo_store):
    dynamo_store.put(SUBMISSION)
    fetched = dynamo_store.get("s-1")
    assert fetched == SUBMISSION
    assert isinstance(fetched["similarity_score"], float)
    assert isinstance(fetched["word_count"], int)


def test_delete_reports_whether_item_existed(dynamo_store):
    dynamo_store.put(SUBMISSION)
    assert dynamo_store.delete("s-1") is True
    assert dynamo_store.delete("s-1") is False
    assert dynamo_store.get("s-1") is None


def test_list_is_newest_first(dynamo_store):
    dynamo_store.put({**SUBMISSION, "id": "old", "created_at": "2026-01-01T00:00:00+00:00"})
    dynamo_store.put({**SUBMISSION, "id": "new", "created_at": "2026-02-01T00:00:00+00:00"})
    assert [s["id"] for s in dynamo_store.list()] == ["new", "old"]
    assert dynamo_store.count() == 2


@pytest.fixture
def lambda_handler(monkeypatch):
    """The real Lambda handler, with the Flask app's store swapped for a mocked DynamoDB
    table. Monkeypatching (rather than reloading the module) keeps the session-wide test
    server untouched."""
    with mock_aws():
        ddb = boto3.resource("dynamodb", region_name=REGION)
        _create_table(ddb)
        import app.server as server
        from aws.app_handler import handler

        monkeypatch.setattr(server, "store", DynamoStore(TABLE, dynamodb_resource=ddb))
        monkeypatch.setattr(server, "API_KEY", "lambda-key")
        yield handler


def _function_url_event(method: str, path: str, body: dict | None = None, api_key: str | None = "lambda-key") -> dict:
    headers = {"content-type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": "",
        "headers": headers,
        "requestContext": {"http": {"method": method, "path": path, "protocol": "HTTP/1.1", "sourceIp": "127.0.0.1", "userAgent": "pytest"}},
        "body": json.dumps(body) if body is not None else None,
        "isBase64Encoded": False,
    }


def test_lambda_handler_serves_health_with_dynamo_backend(lambda_handler):
    resp = lambda_handler(_function_url_event("GET", "/health"), None)
    assert resp["statusCode"] == 200
    assert json.loads(resp["body"])["backend"] == "DynamoStore"


def test_lambda_handler_create_then_get_persists_in_dynamo(lambda_handler):
    payload = {"title": "Lambda paper", "author": "cloud", "text": "x" * 40}
    created = lambda_handler(_function_url_event("POST", "/api/submissions", payload), None)
    assert created["statusCode"] == 201
    sid = json.loads(created["body"])["id"]

    fetched = lambda_handler(_function_url_event("GET", f"/api/submissions/{sid}"), None)
    assert fetched["statusCode"] == 200
    assert json.loads(fetched["body"])["title"] == "Lambda paper"


def test_lambda_handler_enforces_api_key(lambda_handler):
    resp = lambda_handler(_function_url_event("GET", "/api/submissions", api_key=None), None)
    assert resp["statusCode"] == 401


def test_lambda_handler_renders_html_ui(lambda_handler):
    event = _function_url_event("GET", "/", api_key=None)
    event["headers"] = {"accept": "text/html"}
    resp = lambda_handler(event, None)
    assert resp["statusCode"] == 200
    assert "<title>Submission Service</title>" in resp["body"]
