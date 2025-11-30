import json
from types import SimpleNamespace

import pytest

from plantation_monitoring.triggers import s3_file_sensor


class FakeContext:
    def __init__(self, cursor=None):
        self.cursor = cursor
        self.updated_cursor = None
        self.logs = []

    def update_cursor(self, cursor):
        self.updated_cursor = cursor

    @property
    def log(self):
        return SimpleNamespace(info=lambda *args, **kwargs: self.logs.append(("info", args, kwargs)))


class FakeS3Client:
    def __init__(self, keys):
        self.keys = keys

    def list_objects_v2(self, Bucket, Prefix):
        return {"Contents": [{"Key": k} for k in self.keys if k.startswith(Prefix)]}


class FakeS3Resource:
    def __init__(self, keys):
        self.client = FakeS3Client(keys)

    def get_client(self):
        return self.client


@pytest.fixture
def fake_settings() -> SimpleNamespace:
    return SimpleNamespace(aws_s3_pipeline_bucket_name="test-bucket")


def test_detect_new_s3_files_emits_run_requests(fake_settings: SimpleNamespace) -> None:
    """
    Test that new S3 files trigger run requests.

    When files are detected in S3 that weren't in the previous cursor,
    the sensor should emit RunRequests for each new file.
    """
    context = FakeContext(cursor=None)
    s3 = FakeS3Resource(keys=["raw_catalog/fields/staging/file1.geojson", "raw_catalog/fields/staging/file2.geojson"])
    run_requests = list(
        s3_file_sensor._detect_new_s3_files(
            context=context,
            s3=s3,
            settings=fake_settings,
            prefix="raw_catalog/fields/staging",
        )
    )

    assert len(run_requests) == 2
    assert {r.run_key for r in run_requests} == {
        "raw_catalog/fields/staging/file1.geojson",
        "raw_catalog/fields/staging/file2.geojson",
    }
    assert json.loads(context.updated_cursor) == [
        "raw_catalog/fields/staging/file1.geojson",
        "raw_catalog/fields/staging/file2.geojson",
    ]


def test_detect_new_s3_files_skips_when_no_new_files(fake_settings: SimpleNamespace) -> None:
    """
    Test that no run requests are emitted when files already exist in cursor.

    When all files in S3 are already tracked in the cursor,
    the sensor should not emit any RunRequests.
    """
    existing = ["raw_catalog/bbox/staging/bbox1.geojson"]
    context = FakeContext(cursor=json.dumps(existing))
    s3 = FakeS3Resource(keys=existing)

    run_requests = list(
        s3_file_sensor._detect_new_s3_files(
            context=context,
            s3=s3,
            settings=fake_settings,
            prefix="raw_catalog/bbox/staging",
        )
    )

    assert run_requests == []
    assert json.loads(context.updated_cursor) == existing
