"""S3 client connector for MinIO operations."""

import os
from typing import Any

import boto3
from dagster import ConfigurableResource

from plantation_monitoring.connectors.settings import SettingsResource


class S3Resource(ConfigurableResource[Any]):
    """S3 resource for creating boto3 S3 clients."""

    settings: SettingsResource

    def create_client(self) -> Any:
        """Create S3 client.

        :returns: Configured S3 client
        """
        aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("MINIO_ROOT_USER")
        aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY") or os.environ.get("MINIO_ROOT_PASSWORD")

        return boto3.client(
            "s3",
            endpoint_url=self.settings.aws_s3_endpoint,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=self.settings.aws_region,
            use_ssl=self.settings.aws_s3_use_ssl,
        )

    def get_client(self) -> Any:
        """Get S3 client instance.

        :returns: Configured S3 client
        """
        return self.create_client()
