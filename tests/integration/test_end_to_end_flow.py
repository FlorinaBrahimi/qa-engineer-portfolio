"""Integration: a record created through the UI is visible through the API and vice versa,
and the archived S3 object matches what the API returns.
"""
import boto3
import pytest
from moto import mock_aws

from aws.archive import archive_submission
from testdata.factory import SubmissionFactory
from tests.ui.pages.submission_page import SubmissionPage

pytestmark = [pytest.mark.integration, pytest.mark.regression]


def test_ui_submission_is_readable_via_api(page, api, base_url, clean_store):
    data = SubmissionFactory.build()
    SubmissionPage(page).open().submit(**data)

    items = api.get(f"{base_url}/api/submissions").json()["items"]
    match = [i for i in items if i["title"] == data["title"]]
    assert len(match) == 1
    assert match[0]["author"] == data["author"]


def test_api_submission_is_visible_in_ui(page, created_submission):
    home = SubmissionPage(page).open()
    assert home.row_for_title(created_submission["title"]).is_visible()


@mock_aws
def test_api_record_round_trips_through_s3_archive(api, base_url, created_submission):
    s3 = boto3.client("s3", region_name="us-east-1")
    s3.create_bucket(Bucket="submissions-archive")

    key = archive_submission("submissions-archive", created_submission, s3_client=s3)

    stored = s3.get_object(Bucket="submissions-archive", Key=key)["Body"].read()
    fetched = api.get(f"{base_url}/api/submissions/{created_submission['id']}").json()
    import json
    assert json.loads(stored) == fetched
