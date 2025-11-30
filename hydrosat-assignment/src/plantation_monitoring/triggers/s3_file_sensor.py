"""S3 file sensors for detecting new files and triggering jobs."""

import json
from collections.abc import Generator
from typing import Any

from dagster import (
    DefaultSensorStatus,
    RunRequest,
    SensorEvaluationContext,
    sensor,
)

from plantation_monitoring.config.constants import (
    AWS_S3_PIPELINE_STATICDATA_BBOX_PENDING_KEY,
    AWS_S3_PIPELINE_STATICDATA_FIELDS_PENDING_KEY,
)
from plantation_monitoring.connectors.s3_client import S3Resource
from plantation_monitoring.connectors.settings import SettingsResource
from plantation_monitoring.triggers.jobs import bbox_job, fields_job


def _detect_new_s3_files(
    context: SensorEvaluationContext,
    s3: S3Resource,
    settings: SettingsResource,
    prefix: str,
) -> Generator[RunRequest, None, None]:
    """Detect new files in S3 prefix by comparing with previous state.

    :param context: Sensor evaluation context
    :param s3: S3 resource
    :param settings: Settings resource
    :param prefix: S3 prefix to monitor
    :yields: RunRequest for each new file
    """
    s3_client = s3.get_client()
    bucket = settings.aws_s3_pipeline_bucket_name

    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
    all_files = [obj["Key"] for obj in response.get("Contents", [])]
    previous_files = json.loads(context.cursor) if context.cursor else []
    new_files = list(set(all_files) - set(previous_files))
    context.update_cursor(json.dumps(all_files))

    if new_files:
        context.log.info(f"Found {len(new_files)} new file(s) in {prefix}: {new_files}")
        for file_key in new_files:
            yield RunRequest(run_key=file_key)


def create_s3_file_sensor(job: Any, prefix: str, name: str) -> Any:
    """Create S3 file sensor.

    :param job: Asset job to trigger
    :param prefix: S3 prefix to watch
    :param name: Sensor name
    :returns: Configured sensor function
    """

    @sensor(job=job, minimum_interval_seconds=5, default_status=DefaultSensorStatus.RUNNING, name=name)
    def sensor_fn(
        context: SensorEvaluationContext, s3: S3Resource, settings: SettingsResource
    ) -> Generator[RunRequest, None, None]:
        yield from _detect_new_s3_files(context, s3, settings, prefix)

    return sensor_fn


s3_fields_sensor = create_s3_file_sensor(
    job=fields_job,
    prefix=AWS_S3_PIPELINE_STATICDATA_FIELDS_PENDING_KEY,
    name="s3_fields_sensor",
)

s3_bbox_sensor = create_s3_file_sensor(
    job=bbox_job,
    prefix=AWS_S3_PIPELINE_STATICDATA_BBOX_PENDING_KEY,
    name="s3_bbox_sensor",
)
