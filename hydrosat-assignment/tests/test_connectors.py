from types import SimpleNamespace
from typing import Any

import pytest

from plantation_monitoring.connectors.s3_client import S3Resource
from plantation_monitoring.connectors.settings import SettingsResource
from plantation_monitoring.connectors.stac_client import STACResource


def test_settings_create_from_env_uses_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test that SettingsResource correctly loads from environment variables.

    Verifies that all settings are correctly read from environment
    and defaults are applied where appropriate.
    """
    monkeypatch.delenv("AWS_PROFILE", raising=False)
    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    monkeypatch.setenv("AWS_S3_ENDPOINT", "http://localhost:9000")
    monkeypatch.setenv("AWS_S3_PIPELINE_BUCKET_NAME", "bucket")
    monkeypatch.setenv("AWS_S3_USE_SSL", "false")
    monkeypatch.setenv("TMP_DIR", "/tmp")
    monkeypatch.setenv("STAC_API_URL", "http://stac")

    settings = SettingsResource.create_from_env()
    assert settings.aws_region == "eu-west-1"
    assert settings.aws_s3_endpoint == "http://localhost:9000"
    assert settings.aws_s3_pipeline_bucket_name == "bucket"
    assert settings.aws_s3_use_ssl is False
    assert settings.tmp_dir == "/tmp"
    assert settings.stac_api_url == "http://stac"
    assert settings.aws_profile is None


def test_minio_s3_resource_creates_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test that S3Resource creates a boto3 S3 client with correct parameters.

    Verifies that the resource correctly passes settings to boto3 Session
    and creates an S3 client with the right endpoint and SSL settings.
    """
    calls: dict[str, Any] = {}

    class FakeSession:
        def __init__(self, profile_name: str, region_name: str) -> None:
            calls["session"] = (profile_name, region_name)

        def client(self, service: str, endpoint_url: str | None = None, use_ssl: bool | None = None) -> Any:
            calls["client"] = (service, endpoint_url, use_ssl)
            return SimpleNamespace()

    monkeypatch.setattr("boto3.Session", FakeSession)

    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    monkeypatch.setenv("AWS_S3_ENDPOINT", "http://localhost:9000")
    monkeypatch.setenv("AWS_S3_PIPELINE_BUCKET_NAME", "bucket")
    monkeypatch.setenv("AWS_S3_USE_SSL", "false")
    monkeypatch.setenv("TMP_DIR", "/tmp")
    monkeypatch.setenv("STAC_API_URL", "http://stac")
    monkeypatch.setenv("AWS_PROFILE", "minio")

    settings = SettingsResource.create(swallow_errors=True)
    resource = S3Resource(settings=settings)
    client = resource.create_client()
    assert client is not None
    assert calls["session"] == ("minio", "eu-west-1")
    assert calls["client"] == ("s3", "http://localhost:9000", False)


def test_stac_resource_creates_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Test that STACResource creates a STAC client with correct URL.

    Verifies that the resource correctly initializes the STAC client
    with the configured API URL.
    """
    created = {}

    class FakeClient:
        @staticmethod
        def open(url: str) -> str:
            created["url"] = url
            return "fake-client"

    monkeypatch.setattr("plantation_monitoring.connectors.stac_client.Client", FakeClient)

    monkeypatch.setenv("AWS_REGION", "eu-west-1")
    monkeypatch.setenv("AWS_S3_ENDPOINT", "http://localhost:9000")
    monkeypatch.setenv("AWS_S3_PIPELINE_BUCKET_NAME", "bucket")
    monkeypatch.setenv("AWS_S3_USE_SSL", "false")
    monkeypatch.setenv("TMP_DIR", "/tmp")
    monkeypatch.setenv("STAC_API_URL", "http://stac")

    settings = SettingsResource.create(swallow_errors=True)
    resource = STACResource(settings=settings)
    client = resource.create_client()
    assert client == "fake-client"
    assert created["url"] == "http://stac"
