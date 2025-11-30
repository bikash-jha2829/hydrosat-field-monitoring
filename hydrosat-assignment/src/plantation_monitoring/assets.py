"""Dagster assets for plantation monitoring pipeline."""

import os
from collections.abc import Callable
from typing import Any

from dagster import (
    AssetExecutionContext,
    AutoMaterializePolicy,
    DailyPartitionsDefinition,
    DynamicPartitionsDefinition,
    MultiPartitionsDefinition,
    Output,
    asset,
)
from dagster_aws.s3 import S3Resource
from shapely.geometry import mapping, shape

from plantation_monitoring.config.constants import (
    AWS_S3_PIPELINE_STATICDATA_BBOX_FALLBACK_KEY,
    AWS_S3_PIPELINE_STATICDATA_BBOX_PENDING_KEY,
    AWS_S3_PIPELINE_STATICDATA_BBOX_PROCESSED_KEY,
    AWS_S3_PIPELINE_STATICDATA_FIELDS_PENDING_KEY,
    AWS_S3_PIPELINE_STATICDATA_FIELDS_PROCESSED_KEY,
    DEFAULT_PARTITION_START_DATE,
    NDMI_BAND_PREFERENCES,
    NDVI_BAND_PREFERENCES,
)
from plantation_monitoring.connectors.settings import SettingsResource
from plantation_monitoring.connectors.stac_client import STACResource
from plantation_monitoring.geospatial.raster_ops import (
    compute_ndmi_from_cog_urls,
    compute_ndvi_from_cog_urls,
)
from plantation_monitoring.geospatial.stac_ops import (
    search_first_sentinel_item,
    select_and_sign_band_urls,
)
from plantation_monitoring.models.models import NDMI, NDVI, Bbox, Field
from plantation_monitoring.storage import (
    load_fields_from_s3,
    load_geojson_from_s3,
    publish_spectral_index_to_stac,
    save_spectral_index_to_s3,
)

daily_partitions = DailyPartitionsDefinition(
    start_date=os.getenv("DAGSTER_PARTITION_START_DATE", DEFAULT_PARTITION_START_DATE)
)
field_partitions = DynamicPartitionsDefinition(name="field_id")
multi_partitions = MultiPartitionsDefinition(
    {
        "date": daily_partitions,
        "field_id": field_partitions,
    }
)


@asset(auto_materialize_policy=AutoMaterializePolicy.eager())
def bbox(context: AssetExecutionContext, s3: S3Resource, settings: SettingsResource) -> Bbox:
    """Load bounding box from S3 raw catalog.

    Searches processed, then staging, then config fallback.

    :param context: Dagster context
    :param s3: S3 resource
    :param settings: Settings resource
    :returns: Bbox instance
    """
    bbox_gdf = load_geojson_from_s3(
        context,
        s3,
        settings,
        AWS_S3_PIPELINE_STATICDATA_BBOX_PROCESSED_KEY,
        AWS_S3_PIPELINE_STATICDATA_BBOX_PENDING_KEY,
        fallback_key=AWS_S3_PIPELINE_STATICDATA_BBOX_FALLBACK_KEY,
    )

    if bbox_gdf is None:
        raise ValueError("No bbox found in processed, staging, or config locations")

    return Bbox.from_geodataframe(bbox_gdf)


@asset(auto_materialize_policy=AutoMaterializePolicy.eager())
def fields(context: AssetExecutionContext, s3: S3Resource, settings: SettingsResource) -> Output[list[Field]]:
    """Load fields from S3 and register new fields as dynamic partitions.

    :param context: Dagster context
    :param s3: S3 resource
    :param settings: Settings resource
    :returns: Output with list of fields
    """
    all_fields, new_field_ids = load_fields_from_s3(
        context,
        s3,
        settings,
        AWS_S3_PIPELINE_STATICDATA_FIELDS_PROCESSED_KEY,
        AWS_S3_PIPELINE_STATICDATA_FIELDS_PENDING_KEY,
    )

    if new_field_ids:
        instance = context.instance
        instance.add_dynamic_partitions(partitions_def_name="field_id", partition_keys=list(new_field_ids))
        context.log.info(f"Added {len(new_field_ids)} dynamic partitions for field_id.")

    return Output(
        all_fields,
        metadata={
            "field_ids": ", ".join(f.id for f in all_fields),
            "total_fields": len(all_fields),
            "new_fields_added": len(new_field_ids),
        },
    )


@asset(
    partitions_def=multi_partitions,
    auto_materialize_policy=AutoMaterializePolicy.eager(),
    deps=[fields, bbox],
)
def field_ndvi(
    context: AssetExecutionContext,
    s3: S3Resource,
    stac: STACResource,
    settings: SettingsResource,
    bbox: Bbox,
    fields: list[Field],
) -> Output[Field]:
    """Compute NDVI for field on specific date.

    Uses Sentinel-2 red (B04) and near-infrared (B08) bands.

    :param context: Dagster context
    :param s3: S3 resource
    :param stac: STAC resource
    :param settings: Settings resource
    :param bbox: Bounding box
    :param fields: List of fields
    :returns: Output with computed NDVI
    """
    return _materialize_spectral_index(
        context=context,
        s3=s3,
        stac=stac,
        settings=settings,
        bbox=bbox,
        fields=fields,
        index_name="ndvi",
        band_preferences=NDVI_BAND_PREFERENCES,
        compute_fn=compute_ndvi_from_cog_urls,
        index_model_class=NDVI,
    )


@asset(
    partitions_def=multi_partitions,
    auto_materialize_policy=AutoMaterializePolicy.eager(),
    deps=[fields, bbox],
)
def field_ndmi(
    context: AssetExecutionContext,
    s3: S3Resource,
    stac: STACResource,
    settings: SettingsResource,
    bbox: Bbox,
    fields: list[Field],
) -> Output[Field]:
    """Compute NDMI for field on specific date.

    Uses Sentinel-2 near-infrared (B08) and shortwave infrared (B11/B12) bands.

    :param context: Dagster context
    :param s3: S3 resource
    :param stac: STAC resource
    :param settings: Settings resource
    :param bbox: Bounding box
    :param fields: List of fields
    :returns: Output with computed NDMI
    """
    return _materialize_spectral_index(
        context=context,
        s3=s3,
        stac=stac,
        settings=settings,
        bbox=bbox,
        fields=fields,
        index_name="ndmi",
        band_preferences=NDMI_BAND_PREFERENCES,
        compute_fn=compute_ndmi_from_cog_urls,
        index_model_class=NDMI,
    )


def _extract_partition_keys(context: AssetExecutionContext) -> tuple[str, str]:
    """Extract date and field_id from partition key.

    :param context: Dagster context
    :returns: Tuple of (date_str, field_id)
    """
    partition_key = context.partition_key
    date_str = partition_key.keys_by_dimension["date"]
    field_id = partition_key.keys_by_dimension["field_id"]
    return date_str, field_id


def _find_field_by_id(fields: list[Field], field_id: str) -> Field | None:
    """Find field by ID.

    :param fields: List of fields
    :param field_id: Field ID to find
    :returns: Field if found, None otherwise
    """
    return next((f for f in fields if f.id == field_id), None)


def _check_field_eligibility(
    context: AssetExecutionContext,
    field: Field,
    date_str: str,
    index_name: str,
) -> Output[Field] | None:
    """Check if field is eligible for spectral index computation.

    :param context: Dagster context
    :param field: Field to check
    :param date_str: Date string
    :param index_name: Index name
    :returns: None if eligible, Output[Field] with error if not eligible
    """
    if date_str < field.plant_date:
        context.log.info(f"Field {field.id} not planted yet on {date_str}. Skipping {index_name.upper()} computation.")
        return _create_error_output(
            field=field,
            index_name=index_name,
            error=f"Field {field.id} not planted yet on {date_str}",
        )
    return None


def _create_error_output(
    field: Field,
    index_name: str,
    error: str,
) -> Output[Field]:
    """Create error Output for field computation failure.

    :param field: Field instance
    :param index_name: Index name
    :param error: Error message
    :returns: Output with error metadata
    """
    return Output(
        field,
        metadata={
            "success": False,
            "error": error,
            f"{index_name}_computed": False,
        },
    )


def _create_success_output(
    field: Field,
    index_name: str,
    s3_key: str,
    bucket_name: str,
    stac_key: str | None = None,
) -> Output[Field]:
    """Create success Output for field computation.

    :param field: Field instance
    :param index_name: Index name
    :param s3_key: S3 key
    :param bucket_name: Bucket name
    :param stac_key: Optional STAC key
    :returns: Output with success metadata
    """
    return Output(
        field,
        metadata={
            "success": True,
            "error": None,
            f"{index_name}_computed": True,
            "s3_key": s3_key,
            "s3_path": f"s3://{bucket_name}/{s3_key}",
            "stac_key": stac_key,
        },
    )


def _fetch_sentinel2_data(
    context: AssetExecutionContext,
    stac_client: Any,
    field_geometry: dict[str, Any],
    date_str: str,
    field: Field,
    index_name: str,
    cloud_cover_threshold: int,
) -> tuple[dict[str, Any] | None, Output[Field] | None]:
    """Search for Sentinel-2 items covering field.

    :param context: Dagster context
    :param stac_client: STAC client
    :param field_geometry: Field geometry dictionary
    :param date_str: Date string
    :param field: Field instance
    :param index_name: Index name
    :param cloud_cover_threshold: Maximum cloud cover percentage
    :returns: Tuple of (item or None, error_output or None)
    """
    item, available_assets = search_first_sentinel_item(
        context, stac_client, field_geometry, date_str, cloud_cover_lt=cloud_cover_threshold
    )

    if item is None:
        error_output = _create_error_output(
            field=field,
            index_name=index_name,
            error=f"No Sentinel-2 items found for {date_str}",
        )
        return None, error_output

    return item, None


def _prepare_band_urls(
    context: AssetExecutionContext,
    item: dict[str, Any],
    band_preferences: dict[str, list[str]],
    field: Field,
    index_name: str,
) -> tuple[dict[str, str] | None, Output[Field] | None]:
    """Select and sign band URLs from STAC item.

    :param context: Dagster context
    :param item: STAC item
    :param band_preferences: Band preference mapping
    :param field: Field instance
    :param index_name: Index name
    :returns: Tuple of (band_urls or None, error_output or None)
    """
    band_urls, available_assets, missing = select_and_sign_band_urls(item, band_preferences)

    if band_urls is None:
        context.log.error(f"Could not find required bands {missing}. Available: {available_assets}")
        error_output = _create_error_output(
            field=field,
            index_name=index_name,
            error=f"Could not find required bands {missing}. Available assets: {available_assets}",
        )
        return None, error_output

    return band_urls, None


def _compute_index_array(
    compute_fn: Callable[..., Any],
    band_urls: dict[str, str],
    field_geometry: Any,
) -> Any:
    """Compute spectral index array from band URLs.

    :param compute_fn: Compute function
    :param band_urls: Band URL mapping
    :param field_geometry: Shapely geometry or dict
    :returns: Computed index array
    """
    compute_kwargs: dict[str, Any] = {}
    for band_key, url in band_urls.items():
        compute_kwargs[f"{band_key}_url"] = url
    compute_kwargs["bbox_geom"] = field_geometry
    return compute_fn(**compute_kwargs)


def _save_and_publish_results(
    context: AssetExecutionContext,
    s3: S3Resource,
    s3_client: Any,
    settings: SettingsResource,
    field_with_index: Field,
    date_str: str,
    field_id: str,
    index_name: str,
    index_data: Any,
) -> tuple[str, str | None]:
    """Save spectral index to S3 and publish to STAC.

    :param context: Dagster context
    :param s3: S3 resource
    :param s3_client: S3 client
    :param settings: Settings resource
    :param field_with_index: Field with index data
    :param date_str: Date string
    :param field_id: Field ID
    :param index_name: Index name
    :param index_data: Index data
    :returns: Tuple of (s3_key, stac_key or None)
    """
    s3_key = save_spectral_index_to_s3(
        context=context,
        s3=s3,
        s3_client=s3_client,
        settings=settings,
        field=field_with_index,
        date_str=date_str,
        field_id=field_id,
        index_name=index_name,
        index_data=index_data,
    )

    stac_key = None
    try:
        stac_key = publish_spectral_index_to_stac(
            context=context,
            s3=s3,
            s3_client=s3_client,
            settings=settings,
            field=field_with_index,
            date_str=date_str,
            field_id=field_id,
            index_name=index_name,
            s3_key=s3_key,
        )
        context.log.info(
            f"Published {index_name.upper()} STAC item to S3: s3://{settings.aws_s3_pipeline_bucket_name}/{stac_key}"
        )
    except Exception as e:
        context.log.warning(f"Failed to publish {index_name.upper()} to STAC: {e}")

    return s3_key, stac_key


def _materialize_spectral_index(
    context: AssetExecutionContext,
    s3: S3Resource,
    stac: STACResource,
    settings: SettingsResource,
    bbox: Bbox,
    fields: list[Field],
    index_name: str,
    band_preferences: dict[str, list[str]],
    compute_fn: Callable[..., Any],
    index_model_class: type,
) -> Output[Field]:
    """Materialize spectral index for field.

    Validates eligibility, searches Sentinel-2 data, prepares band URLs,
    computes index, and saves to S3 and publishes to STAC.

    :param context: Dagster context
    :param s3: S3 resource
    :param stac: STAC resource
    :param settings: Settings resource
    :param bbox: Bounding box
    :param fields: List of fields
    :param index_name: Index name (e.g., "ndvi", "ndmi")
    :param band_preferences: Band preference mapping
    :param compute_fn: Compute function
    :param index_model_class: Index model class
    :returns: Output with computed index
    """
    date_str, field_id = _extract_partition_keys(context)

    field = _find_field_by_id(fields, field_id)
    if field is None:
        raise ValueError(f"Field {field_id} not found")

    error_output = _check_field_eligibility(context, field, date_str, index_name)
    if error_output is not None:
        return error_output

    context.log.info(
        f"Computing {index_name.upper()} for field {field_id} "
        f"(plant_date: {field.plant_date}, plant_type: {field.plant_type}) "
        f"on date {date_str}"
    )

    field_shape = shape(field.geom)
    bbox_shape = shape(bbox.geom)
    field_intersection = field_shape.intersection(bbox_shape)
    field_geometry_dict = mapping(field_intersection)

    stac_client = stac.create_client()
    s3_client = s3.get_client()

    cloud_cover_threshold = settings.get_cloud_cover_threshold()
    item, error_output = _fetch_sentinel2_data(
        context, stac_client, field_geometry_dict, date_str, field, index_name, cloud_cover_threshold=cloud_cover_threshold
    )
    if error_output is not None:
        return error_output

    assert item is not None, "Unexpected: item is None after successful fetch"

    band_urls, error_output = _prepare_band_urls(context, item, band_preferences, field, index_name)
    if error_output is not None:
        return error_output

    assert band_urls is not None, "Unexpected: band_urls is None after successful preparation"

    index_array = _compute_index_array(compute_fn, band_urls, field_intersection)
    context.log.info(f"{index_name.upper()} for {field_id} on {date_str} computed.")

    field_with_index = field.model_copy(
        update={index_name: index_model_class.from_array(index_array)}  # type: ignore
    )

    index_data = getattr(field_with_index, index_name)
    s3_key, stac_key = _save_and_publish_results(
        context=context,
        s3=s3,
        s3_client=s3_client,
        settings=settings,
        field_with_index=field_with_index,
        date_str=date_str,
        field_id=field_id,
        index_name=index_name,
        index_data=index_data,
    )

    return _create_success_output(
        field=field_with_index,
        index_name=index_name,
        s3_key=s3_key,
        bucket_name=settings.aws_s3_pipeline_bucket_name,
        stac_key=stac_key,
    )
