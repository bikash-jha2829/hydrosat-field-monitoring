"""Storage operations for S3 and STAC catalog I/O."""

import io
import json
import os
from collections.abc import Generator
from typing import Any

import geopandas as gpd
from dagster import AssetExecutionContext, OpExecutionContext
from dagster_aws.s3 import S3PickleIOManager, S3Resource as DagsterS3Resource
from jsonpath_ng.ext import parse
from shapely.geometry import shape

from plantation_monitoring.connectors.s3_client import S3Resource
from plantation_monitoring.connectors.settings import SettingsResource
from plantation_monitoring.geospatial.stac_publisher import (
    add_stac_links,
    create_stac_item_json,
    ensure_catalog_structure,
    publish_stac_item_idempotent,
)
from plantation_monitoring.models.models import Field


def move_s3_files(
    context: OpExecutionContext,
    s3: S3Resource,
    settings: SettingsResource,
    source_prefix: str,
    dest_prefix: str,
) -> None:
    """Move S3 files from source to destination prefix.

    :param context: Dagster context
    :param s3: S3 resource
    :param settings: Settings resource
    :param source_prefix: Source prefix
    :param dest_prefix: Destination prefix
    """
    bucket = settings.aws_s3_pipeline_bucket_name
    s3_client = s3.get_client()

    paginator = s3_client.get_paginator("list_objects_v2")
    page_iterator = paginator.paginate(Bucket=bucket, Prefix=source_prefix)

    context.log.debug(f"Moving files from {source_prefix} to {dest_prefix}")

    for page in page_iterator:
        for obj in page.get("Contents", []):
            source_key = obj["Key"]
            dest_key = source_key.replace(source_prefix, dest_prefix, 1)

            s3_client.copy_object(
                Bucket=bucket,
                CopySource={"Bucket": bucket, "Key": source_key},
                Key=dest_key,
            )
            s3_client.delete_object(Bucket=bucket, Key=source_key)

    context.log.debug(f"Moved files from {source_prefix} to {dest_prefix}")


def list_geojson_files(
    context: OpExecutionContext,
    s3: S3Resource,
    settings: SettingsResource,
    prefix: str,
) -> Generator[tuple[str, dict[str, Any]], None, None]:
    """List and yield GeoJSON files from S3 prefix.

    :param context: Dagster context
    :param s3: S3 resource
    :param settings: Settings resource
    :param prefix: S3 prefix
    :yields: Tuple of (s3_key, geojson_content)
    """
    bucket = settings.aws_s3_pipeline_bucket_name
    s3_client = s3.get_client()
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)

    if "Contents" not in response:
        context.log.warning(f"No files found in {bucket}/{prefix}")
        return

    for obj in response.get("Contents", []):
        key = obj["Key"]
        if not key.endswith(".geojson"):
            continue

        context.log.debug(f"Loading {key}")
        try:
            s3_object = s3_client.get_object(Bucket=bucket, Key=key)
            content = json.loads(s3_object["Body"].read().decode("utf-8"))
            yield key, content
        except Exception as e:
            context.log.error(f"Error processing {key}: {e}")


def extract_fields_from_geojson(geojson_content: dict[str, Any]) -> Generator[tuple[str, dict[str, Any]], None, None]:
    """Extract field features from GeoJSON using JSONPath.

    :param geojson_content: GeoJSON dictionary
    :yields: Tuple of (field_id, field_feature)
    """
    jsonpath_expr = parse('$.features[?(@.properties["object-type"] == "field")]')
    for match in jsonpath_expr.find(geojson_content):
        field_id = str(match.value["properties"]["object-id"])
        yield field_id, match.value


def load_geojson_from_s3(
    context: OpExecutionContext,
    s3: S3Resource,
    settings: SettingsResource,
    processed_prefix: str,
    staging_prefix: str,
    fallback_key: str | None = None,
) -> gpd.GeoDataFrame | None:
    """Load GeoJSON from S3.

    Checks processed, then staging, then fallback. Moves staging files to processed.

    :param context: Dagster context
    :param s3: S3 resource
    :param settings: Settings resource
    :param processed_prefix: Processed prefix
    :param staging_prefix: Staging prefix
    :param fallback_key: Optional fallback key
    :returns: GeoDataFrame if found, None otherwise
    """
    gdf = None
    has_new_files = False

    for key, content in list_geojson_files(context, s3, settings, processed_prefix):
        gdf = gpd.GeoDataFrame.from_features(content.get("features", []), crs="EPSG:4326")
        break

    for key, content in list_geojson_files(context, s3, settings, staging_prefix):
        has_new_files = True
        gdf = gpd.GeoDataFrame.from_features(content.get("features", []), crs="EPSG:4326")
        break

    if has_new_files:
        move_s3_files(context, s3, settings, staging_prefix, processed_prefix)

    if gdf is None and fallback_key:
        try:
            s3_client = s3.get_client()
            bucket = settings.aws_s3_pipeline_bucket_name
            response = s3_client.get_object(Bucket=bucket, Key=fallback_key)
            content_bytes: bytes = response["Body"].read()
            gdf = gpd.read_file(io.BytesIO(content_bytes))
            context.log.info(f"Loaded from {fallback_key} (fallback)")
        except Exception as e:
            context.log.warning(f"Could not load from fallback {fallback_key}: {e}")

    return gdf


def load_fields_from_s3(
    context: OpExecutionContext,
    s3: S3Resource,
    settings: SettingsResource,
    processed_prefix: str,
    staging_prefix: str,
) -> tuple[list[Field], set[str]]:
    """Load fields from S3.

    Checks processed then staging. Moves staging files to processed.

    :param context: Dagster context
    :param s3: S3 resource
    :param settings: Settings resource
    :param processed_prefix: Processed prefix
    :param staging_prefix: Staging prefix
    :returns: Tuple of (all_fields, new_field_ids)
    """
    field_ids = set()
    all_fields = []
    has_new_files = False

    for _, content in list_geojson_files(context, s3, settings, processed_prefix):
        for field_id, field_feature in extract_fields_from_geojson(content):
            if field_id in field_ids:
                continue
            all_fields.append(_create_field_from_feature(field_id, field_feature))
            field_ids.add(field_id)

    new_field_ids = set()
    for _, content in list_geojson_files(context, s3, settings, staging_prefix):
        has_new_files = True
        for field_id, field_feature in extract_fields_from_geojson(content):
            if field_id not in field_ids:
                all_fields.append(_create_field_from_feature(field_id, field_feature))
                field_ids.add(field_id)
                new_field_ids.add(field_id)

    if has_new_files:
        move_s3_files(context, s3, settings, staging_prefix, processed_prefix)

    return all_fields, new_field_ids


def _create_field_from_feature(field_id: str, field_feature: dict[str, Any]) -> Field:
    """Create Field from GeoJSON feature.

    :param field_id: Field ID
    :param field_feature: GeoJSON feature dictionary
    :returns: Field instance
    """
    return Field(
        id=field_id,
        plant_type=field_feature["properties"]["plant-type"],
        plant_date=field_feature["properties"]["plant-date"],
        geom=field_feature["geometry"],
    )


def save_spectral_index_to_s3(
    context: OpExecutionContext | AssetExecutionContext,
    s3: S3Resource,
    settings: SettingsResource,
    field: Field,
    date_str: str,
    field_id: str,
    index_name: str,
    index_data: Any,
    s3_client: Any | None = None,
) -> str:
    """Save spectral index data to S3 as GeoParquet.

    :param context: Dagster context
    :param s3: S3 resource
    :param settings: Settings resource
    :param field: Field with spectral index data
    :param date_str: Date string
    :param field_id: Field ID
    :param index_name: Index name (e.g., "ndvi", "ndmi")
    :param index_data: Index data with mean, std, min, max, valid_pixel_count
    :param s3_client: Optional S3 client
    :returns: S3 key where file was written
    """
    if index_data is None:
        raise ValueError(f"Field {field_id} does not have {index_name.upper()} data to write")

    gdf = gpd.GeoDataFrame(
        [
            {
                "field_id": field.id,
                "plant_type": field.plant_type,
                "plant_date": field.plant_date,
                f"{index_name}_mean": getattr(index_data, f"{index_name}_mean"),
                f"{index_name}_std": getattr(index_data, f"{index_name}_std"),
                f"{index_name}_min": getattr(index_data, f"{index_name}_min"),
                f"{index_name}_max": getattr(index_data, f"{index_name}_max"),
                f"{index_name}_valid_pixel_count": getattr(index_data, f"{index_name}_valid_pixel_count"),
                "geometry": shape(field.geom),
            }
        ],
        crs="EPSG:4326",
    )

    parquet_buffer = io.BytesIO()
    gdf.to_parquet(parquet_buffer, engine="pyarrow", index=False)
    parquet_buffer.seek(0)

    s3_key = f"pipeline-outputs/{field_id}/{index_name}/{date_str}.parquet"
    if s3_client is None:
        s3_client = s3.get_client()
    s3_client.upload_fileobj(
        parquet_buffer,
        Bucket=settings.aws_s3_pipeline_bucket_name,
        Key=s3_key,
        ExtraArgs={"ContentType": "application/parquet"},
    )

    context.log.info(f"Written {index_name.upper()} data to S3: s3://{settings.aws_s3_pipeline_bucket_name}/{s3_key}")
    return s3_key


def publish_spectral_index_to_stac(
    context: AssetExecutionContext,
    s3: S3Resource,
    settings: SettingsResource,
    field: Field,
    date_str: str,
    field_id: str,
    index_name: str,
    s3_key: str,
    s3_client: Any | None = None,
) -> str:
    """Publish spectral index result to STAC catalog.

    :param context: Dagster context
    :param s3: S3 resource
    :param settings: Settings resource
    :param field: Field with spectral index data
    :param date_str: Date string
    :param field_id: Field ID
    :param index_name: Index name (e.g., "ndvi", "ndmi")
    :param s3_key: GeoParquet file S3 key
    :param s3_client: Optional S3 client
    :returns: S3 key where STAC item was published
    """
    bucket = settings.aws_s3_pipeline_bucket_name

    ensure_catalog_structure(context, s3, settings, bucket, s3_client=s3_client)

    stac_item = create_stac_item_json(
        field=field,
        date_str=date_str,
        field_id=field_id,
        index_name=index_name,
        s3_key=s3_key,
        bucket_name=bucket,
    )

    add_stac_links(stac_item, bucket, field_id, index_name, date_str)

    result: str = publish_stac_item_idempotent(context, s3, settings, stac_item, s3_client=s3_client)
    return result


def create_s3_io_manager(settings_resource: SettingsResource) -> S3PickleIOManager:
    """Create S3PickleIOManager for MinIO or AWS S3.

    Stores asset outputs in S3 to persist across pod restarts.

    :param settings_resource: Settings resource with S3 configuration
    :returns: Configured S3PickleIOManager instance
    """
    aws_endpoint_url = settings_resource.aws_s3_endpoint
    aws_region = settings_resource.aws_region

    if aws_endpoint_url and not aws_endpoint_url.startswith("https://s3"):
        aws_access_key_id = os.environ.get("AWS_ACCESS_KEY_ID") or os.environ.get("MINIO_ROOT_USER")
        aws_secret_access_key = os.environ.get("AWS_SECRET_ACCESS_KEY") or os.environ.get("MINIO_ROOT_PASSWORD")

        s3_resource = DagsterS3Resource(
            region_name=aws_region,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            endpoint_url=aws_endpoint_url,
        )
    else:
        s3_resource = DagsterS3Resource(region_name=aws_region)

    return S3PickleIOManager(
        s3_resource=s3_resource,
        s3_bucket=settings_resource.aws_s3_pipeline_bucket_name,
        s3_prefix="dagster/storage",
    )
