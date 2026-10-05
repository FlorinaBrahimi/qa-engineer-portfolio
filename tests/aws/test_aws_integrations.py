"""AWS tests using moto, so they run offline and in CI with no credentials."""
import json

import boto3
import pytest
from moto import mock_aws

from aws.archive import archive_submission, publish_similarity_metric
from aws.lambda_handler import handler

pytestmark = [pytest.mark.aws]

REGION = "us-east-1"
SUBMISSION = {
    "id": "abc-123",
    "title": "t",
    "author": "a",
    "word_count": 10,
    "similarity_score": 42.0,
    "status": "flagged",
    "created_at": "2026-10-05T10:00:00+00:00",
}


@pytest.fixture
def aws():
    with mock_aws():
        s3 = boto3.client("s3", region_name=REGION)
        s3.create_bucket(Bucket="archive")
        cw = boto3.client("cloudwatch", region_name=REGION)
        yield s3, cw


def test_archive_writes_json_under_dated_prefix(aws):
    s3, _ = aws
    key = archive_submission("archive", SUBMISSION, s3_client=s3)
    assert key == "submissions/2026-10-05/abc-123.json"
    obj = s3.get_object(Bucket="archive", Key=key)
    assert obj["ContentType"] == "application/json"
    assert json.loads(obj["Body"].read()) == SUBMISSION


def test_metric_is_published_with_status_dimension(aws):
    _, cw = aws
    publish_similarity_metric(SUBMISSION, cloudwatch_client=cw)
    metrics = cw.list_metrics(Namespace="SubmissionService")["Metrics"]
    assert any(m["MetricName"] == "SimilarityScore" and {"Name": "Status", "Value": "flagged"} in m["Dimensions"] for m in metrics)


def test_lambda_processes_valid_and_rejects_malformed_objects(aws):
    s3, cw = aws
    good_key = archive_submission("archive", SUBMISSION, s3_client=s3)
    s3.put_object(Bucket="archive", Key="submissions/bad.json", Body=b'{"id": "no-score"}')

    event = {
        "Records": [
            {"s3": {"bucket": {"name": "archive"}, "object": {"key": good_key}}},
            {"s3": {"bucket": {"name": "archive"}, "object": {"key": "submissions/bad.json"}}},
        ]
    }
    result = handler(event, s3_client=s3, cloudwatch_client=cw)
    assert result == {"statusCode": 200, "processed": 1, "rejected": 1}
