"""Dagster definitions for the plantation monitoring pipeline."""

from dagster import Definitions, load_assets_from_modules

from plantation_monitoring import assets  # noqa: TID252
from plantation_monitoring.connectors.s3_client import S3Resource
from plantation_monitoring.connectors.settings import SettingsResource
from plantation_monitoring.connectors.stac_client import STACResource
from plantation_monitoring.storage import create_s3_io_manager
from plantation_monitoring.triggers.jobs import bbox_job, fields_job
from plantation_monitoring.triggers.s3_file_sensor import s3_bbox_sensor, s3_fields_sensor

all_assets = load_assets_from_modules([assets])

settings = SettingsResource.create(swallow_errors=True)
s3 = S3Resource(settings=settings)

s3_io_manager = create_s3_io_manager(settings)

defs = Definitions(
    assets=all_assets,
    jobs=[fields_job, bbox_job],
    sensors=[s3_fields_sensor, s3_bbox_sensor],
    resources={
        "s3": s3,
        "stac": STACResource(settings=settings),
        "settings": settings,
        "io_manager": s3_io_manager,
    },
)
