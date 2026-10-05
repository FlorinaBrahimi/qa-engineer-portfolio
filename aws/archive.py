"""Archive submissions to S3 and emit CloudWatch metrics.

Production code lives here so the AWS tests have something real to exercise.
"""
from __future__ import annotations

import json

import boto3


def archive_submission(bucket: str, submission: dict, s3_client=None) -> str:
    s3 = s3_client or boto3.client("s3")
    key = f"submissions/{submission['created_at'][:10]}/{submission['id']}.json"
    s3.put_object(Bucket=bucket, Key=key, Body=json.dumps(submission).encode(), ContentType="application/json")
    return key


def publish_similarity_metric(submission: dict, cloudwatch_client=None, namespace: str = "SubmissionService") -> None:
    cw = cloudwatch_client or boto3.client("cloudwatch")
    cw.put_metric_data(
        Namespace=namespace,
        MetricData=[
            {
                "MetricName": "SimilarityScore",
                "Dimensions": [{"Name": "Status", "Value": submission["status"]}],
                "Value": submission["similarity_score"],
                "Unit": "Percent",
            }
        ],
    )
