"""Lambda: triggered by S3 ObjectCreated events, re-validates archived submissions and
publishes a CloudWatch metric. Pure function so it is unit-testable without AWS.
"""
from __future__ import annotations

import json

import boto3

from aws.archive import publish_similarity_metric


def handler(event: dict, context=None, s3_client=None, cloudwatch_client=None) -> dict:
    s3 = s3_client or boto3.client("s3")
    processed, rejected = 0, 0
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = record["s3"]["object"]["key"]
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        submission = json.loads(body)
        if not {"id", "similarity_score", "status"} <= submission.keys():
            rejected += 1
            continue
        publish_similarity_metric(submission, cloudwatch_client=cloudwatch_client)
        processed += 1
    return {"statusCode": 200, "processed": processed, "rejected": rejected}
