"""Settings resource for managing configuration from environment variables."""

import os
from pathlib import Path
from typing import Any, Union, get_args, get_origin, get_type_hints

from dagster import ConfigurableResource, EnvVar

from plantation_monitoring.config.constants import (
    DEFAULT_CLOUD_COVER_THRESHOLD,
    DEFAULT_PARTITION_START_DATE,
    DEFAULT_TMP_DIR,
)


class SettingsResource(ConfigurableResource[Any]):
    """Settings resource using EnvVar for runtime resolution in Dagster."""

    aws_region: str = EnvVar("AWS_REGION")
    aws_s3_endpoint: str = EnvVar("AWS_S3_ENDPOINT")
    aws_s3_pipeline_bucket_name: str = EnvVar("AWS_S3_PIPELINE_BUCKET_NAME")
    aws_s3_use_ssl: bool = False
    tmp_dir: str = EnvVar("TMP_DIR")
    stac_api_url: str = EnvVar("STAC_API_URL")
    partition_start_date: str = EnvVar("DAGSTER_PARTITION_START_DATE")
    cloud_cover_threshold: int = EnvVar("CLOUD_COVER_THRESHOLD")  # type: ignore[assignment]

    @staticmethod
    def create(swallow_errors: bool = False) -> "SettingsResource":
        """Create SettingsResource from environment variables.

        :param swallow_errors: If True, ignore validation errors
        :returns: SettingsResource instance
        """
        env_values: dict[str, Any] = {}
        for attr_name, attr_type in get_type_hints(SettingsResource).items():
            raw = os.environ.get(attr_name.upper())
            if raw is None:
                if attr_name == "tmp_dir":
                    env_values[attr_name] = DEFAULT_TMP_DIR
                elif attr_name == "partition_start_date":
                    env_values[attr_name] = DEFAULT_PARTITION_START_DATE
                elif attr_name == "cloud_cover_threshold":
                    env_values[attr_name] = DEFAULT_CLOUD_COVER_THRESHOLD
                else:
                    env_values[attr_name] = None
            elif attr_type is bool:
                env_values[attr_name] = raw.strip().lower() in ("true", "1", "yes", "y", "on")
            elif attr_type is int:
                env_values[attr_name] = int(raw) if raw else None
            else:
                env_values[attr_name] = raw

        settings = SettingsResource(**env_values)
        try:
            settings._post_init()
        except (TypeError, ValueError):
            if not swallow_errors:
                raise
        return settings

    def create_tmp_dir(self) -> None:
        """Create temporary directory if missing."""
        tmp_dir_value = self.tmp_dir.get_value() if isinstance(self.tmp_dir, EnvVar) else self.tmp_dir
        if tmp_dir_value:
            Path(tmp_dir_value).mkdir(parents=True, exist_ok=True)

    def get_cloud_cover_threshold(self) -> int:
        """Get cloud cover threshold, resolving EnvVar if needed.

        :returns: Cloud cover threshold as integer
        """
        threshold = self.cloud_cover_threshold
        if isinstance(threshold, EnvVar):
            value = threshold.get_value()
            return int(value) if value else DEFAULT_CLOUD_COVER_THRESHOLD
        if threshold is None:
            return DEFAULT_CLOUD_COVER_THRESHOLD
        return int(threshold)

    def validate_settings(self) -> None:
        """Validate all required settings are present."""
        missing_vars = []
        for attr_name, attr_type in get_type_hints(self.__class__).items():
            attr_value = getattr(self, attr_name, None)
            if isinstance(attr_value, EnvVar):
                is_optional = get_origin(attr_type) is Union and type(None) in get_args(attr_type)
                if not is_optional and attr_value.get_value() is None:
                    missing_vars.append(attr_value.env_var_name)
        if missing_vars:
            raise ValueError(f"Missing mandatory environment variables: {', '.join(missing_vars)}")

    def _post_init(self) -> None:
        self.create_tmp_dir()
        self.validate_settings()
