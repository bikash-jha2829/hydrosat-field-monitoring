"""Helper functions to publish NDVI and NDMI results to STAC catalog."""

import io
import json
from datetime import datetime
from typing import Any

import geopandas as gpd
from botocore.exceptions import ClientError
from dagster import AssetExecutionContext, OpExecutionContext
from dagster_aws.s3 import S3Resource
from shapely.geometry import shape

from plantation_monitoring.connectors.settings import SettingsResource
from plantation_monitoring.models.models import Field


def create_stac_item_json(
    field: Field,
    date_str: str,
    field_id: str,
    index_name: str,
    s3_key: str,
    bucket_name: str,
) -> dict[str, Any]:
    """Create STAC Item JSON for a spectral index result.

    :param field: Field with spectral index data
    :param date_str: Date string
    :param field_id: Field ID
    :param index_name: Index name (e.g., "ndvi", "ndmi")
    :param s3_key: S3 key for GeoParquet file
    :param bucket_name: S3 bucket name
    :returns: STAC Item dictionary
    """
    index_data = getattr(field, index_name)
    if index_data is None:
        raise ValueError(f"Field {field_id} does not have {index_name.upper()} data")

    obs_date = datetime.strptime(date_str, "%Y-%m-%d")
    geom_shape = shape(field.geom)

    return {
        "type": "Feature",
        "stac_version": "1.0.0",
        "id": f"{field_id}-{index_name}-{date_str}",
        "geometry": field.geom,
        "bbox": list(geom_shape.bounds),
        "properties": {
            "datetime": obs_date.isoformat() + "Z",
            "field_id": field_id,
            "plant_type": field.plant_type,
            "plant_date": field.plant_date,
            "index_type": index_name.upper(),
            f"{index_name}_mean": getattr(index_data, f"{index_name}_mean"),
            f"{index_name}_std": getattr(index_data, f"{index_name}_std"),
            f"{index_name}_min": getattr(index_data, f"{index_name}_min"),
            f"{index_name}_max": getattr(index_data, f"{index_name}_max"),
            f"{index_name}_valid_pixel_count": getattr(index_data, f"{index_name}_valid_pixel_count"),
        },
        "assets": {
            "data": {
                "href": f"s3://{bucket_name}/{s3_key}",
                "type": "application/parquet",
                "title": f"{index_name.upper()} data for {field_id} on {date_str}",
            }
        },
    }


def _ensure_stac_object(
    context: OpExecutionContext | AssetExecutionContext,
    s3_client: Any,
    bucket_name: str,
    s3_key: str,
    stac_object: dict[str, Any],
    object_name: str,
) -> None:
    """Ensure STAC object exists in S3, creating if missing."""
    try:
        s3_client.head_object(Bucket=bucket_name, Key=s3_key)
        context.log.debug(f"{object_name} already exists at {s3_key}")
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "404":
            s3_client.put_object(
                Bucket=bucket_name,
                Key=s3_key,
                Body=json.dumps(stac_object, indent=2).encode("utf-8"),
                ContentType="application/json",
            )
            context.log.info(f"Created {object_name} at s3://{bucket_name}/{s3_key}")
        else:
            raise


def ensure_root_catalog(
    context: OpExecutionContext | AssetExecutionContext,
    s3: S3Resource,
    bucket_name: str,
    s3_client: Any | None = None,
) -> str:
    """Ensure root STAC catalog exists, creating if missing.

    :param context: Dagster context
    :param s3: S3 resource
    :param bucket_name: S3 bucket name
    :param s3_client: Optional S3 client
    :returns: Catalog S3 key
    """
    if s3_client is None:
        s3_client = s3.get_client()
    catalog_key = "catalog/catalog.json"
    root_catalog = {
        "type": "Catalog",
        "stac_version": "1.0.0",
        "id": "hydrosat-field-indices",
        "title": "Hydrosat Field Spectral Indices Catalog",
        "description": "STAC catalog for field spectral index computations (NDVI, NDMI)",
        "links": [
            {"rel": "self", "href": f"s3://{bucket_name}/{catalog_key}", "type": "application/json"},
            {"rel": "root", "href": f"s3://{bucket_name}/{catalog_key}", "type": "application/json"},
            {"rel": "collection", "href": f"s3://{bucket_name}/catalog/collection.json", "type": "application/json"},
        ],
    }
    _ensure_stac_object(context, s3_client, bucket_name, catalog_key, root_catalog, "Root catalog")
    return catalog_key


def ensure_collection(
    context: OpExecutionContext | AssetExecutionContext,
    s3: S3Resource,
    bucket_name: str,
    s3_client: Any | None = None,
) -> str:
    """Ensure STAC collection exists, creating if missing.

    :param context: Dagster context
    :param s3: S3 resource
    :param bucket_name: S3 bucket name
    :param s3_client: Optional S3 client
    :returns: Collection S3 key
    """
    if s3_client is None:
        s3_client = s3.get_client()
    collection_key = "catalog/collection.json"
    collection = {
        "type": "Collection",
        "stac_version": "1.0.0",
        "id": "field-indices",
        "title": "Field Spectral Indices",
        "description": "Collection of spectral index computations (NDVI, NDMI) for agricultural fields",
        "license": "proprietary",
        "extent": {
            "spatial": {"bbox": [[-180, -90, 180, 90]]},
            "temporal": {"interval": [["2024-01-01T00:00:00Z", None]]},
        },
        "links": [
            {"rel": "self", "href": f"s3://{bucket_name}/{collection_key}", "type": "application/json"},
            {"rel": "root", "href": f"s3://{bucket_name}/catalog/catalog.json", "type": "application/json"},
            {"rel": "parent", "href": f"s3://{bucket_name}/catalog/catalog.json", "type": "application/json"},
            {"rel": "items", "href": f"s3://{bucket_name}/catalog/items/", "type": "application/json"},
        ],
    }
    _ensure_stac_object(context, s3_client, bucket_name, collection_key, collection, "Collection")
    return collection_key


def ensure_catalog_structure(
    context: OpExecutionContext | AssetExecutionContext,
    s3: S3Resource,
    settings: SettingsResource,
    bucket_name: str,
    s3_client: Any | None = None,
) -> None:
    """Ensure root catalog and collection exist.

    :param context: Dagster context
    :param s3: S3 resource
    :param settings: Settings resource
    :param bucket_name: S3 bucket name
    :param s3_client: Optional S3 client
    """
    if s3_client is None:
        s3_client = s3.get_client()
    ensure_root_catalog(context, s3, bucket_name, s3_client=s3_client)
    ensure_collection(context, s3, bucket_name, s3_client=s3_client)


def parse_partition_key(context: OpExecutionContext | AssetExecutionContext, op_name: str) -> tuple[str, str]:
    """Parse partition key from context.

    :param context: Dagster context
    :param op_name: Operation name
    :returns: Tuple of (date_str, field_id)
    """
    def _parse_key(key: str | None) -> tuple[str, str] | None:
        if key:
            parts = key.split("|")
            if len(parts) == 2:
                return parts[0], parts[1]
        return None

    run_config = getattr(context, "run_config", None)
    if isinstance(run_config, dict):
        partition_key = run_config.get("ops", {}).get(op_name, {}).get("config", {}).get("partition_key")
        result = _parse_key(partition_key)
        if result:
            return result

    run = getattr(context, "run", None)
    if run and hasattr(run, "tags") and isinstance(run.tags, dict):
        result = _parse_key(run.tags.get("dagster/partition"))
        if result:
            return result

    raise ValueError("Partition key is required for STAC publishing")


def load_field_from_s3_geoparquet(
    context: OpExecutionContext | AssetExecutionContext,
    s3_client: Any,
    bucket: str,
    s3_key: str,
    index_name: str,
    index_model_class: type,
) -> Field:
    """Load field from S3 GeoParquet and convert to Field.

    :param context: Dagster context
    :param s3_client: S3 client
    :param bucket: S3 bucket name
    :param s3_key: GeoParquet file S3 key
    :param index_name: Index name (e.g., "ndvi", "ndmi")
    :param index_model_class: Index model class (NDVI or NDMI)
    :returns: Field with index data
    """
    try:
        response = s3_client.get_object(Bucket=bucket, Key=s3_key)
        gdf = gpd.read_parquet(io.BytesIO(response["Body"].read()))
        row = gdf.iloc[0]

        index_data = index_model_class(
            **{index_name: []},
            **{f"{index_name}_{attr}": row[f"{index_name}_{attr}"] for attr in ["mean", "std", "min", "max", "valid_pixel_count"]},
        )

        return Field(
            id=row["field_id"],
            plant_type=row["plant_type"],
            plant_date=row["plant_date"],
            geom=gdf.geometry.iloc[0].__geo_interface__,
            **{index_name: index_data},
        )
    except s3_client.exceptions.NoSuchKey:
        raise ValueError(f"{index_name.upper()} data not found at s3://{bucket}/{s3_key}. Asset may not be materialized yet.")
    except ClientError as e:
        raise RuntimeError(f"Error fetching {index_name.upper()} data from S3: {e}") from e


def add_stac_links(stac_item: dict[str, Any], bucket: str, field_id: str, index_name: str, date_str: str) -> None:
    """Add STAC links to item.

    :param stac_item: STAC item dictionary
    :param bucket: S3 bucket name
    :param field_id: Field ID
    :param index_name: Index name
    :param date_str: Date string
    """
    item_s3_key = f"catalog/items/{field_id}/{index_name}/{date_str}.json"
    stac_item["links"] = [
        {"rel": "self", "href": f"s3://{bucket}/{item_s3_key}", "type": "application/json"},
        {"rel": "collection", "href": f"s3://{bucket}/catalog/collection.json", "type": "application/json"},
        {"rel": "root", "href": f"s3://{bucket}/catalog/catalog.json", "type": "application/json"},
    ]


def publish_stac_item_idempotent(
    context: OpExecutionContext | AssetExecutionContext,
    s3: S3Resource,
    settings: SettingsResource,
    stac_item: dict[str, Any],
    catalog_path: str = "catalog/items",
    s3_client: Any | None = None,
) -> str:
    """Publish STAC Item to S3 idempotently.

    :param context: Dagster context
    :param s3: S3 resource
    :param settings: Settings resource
    :param stac_item: STAC Item dictionary
    :param catalog_path: Catalog path prefix (e.g., "catalog/items")
    :param s3_client: Optional S3 client
    :returns: S3 key where item was written
    """
    item_id_parts = stac_item["id"].split("-")
    if len(item_id_parts) < 3:
        raise ValueError(f"Invalid item_id format: {stac_item['id']}")

    field_id, index_name, date_str = item_id_parts[0], item_id_parts[1], "-".join(item_id_parts[2:])
    s3_key = f"{catalog_path}/{field_id}/{index_name}/{date_str}.json"

    if s3_client is None:
        s3_client = s3.get_client()
    bucket = settings.aws_s3_pipeline_bucket_name

    try:
        s3_client.head_object(Bucket=bucket, Key=s3_key)
        context.log.info(f"STAC item already exists at {s3_key}, skipping registration (idempotent)")
        return s3_key
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "404":
            s3_client.put_object(
                Bucket=bucket,
                Key=s3_key,
                Body=json.dumps(stac_item, indent=2).encode("utf-8"),
                ContentType="application/json",
            )
            context.log.info(f"Published STAC item to S3: s3://{bucket}/{s3_key}")
            return s3_key
        raise


def publish_spectral_index_to_stac(
    context: OpExecutionContext | AssetExecutionContext,
    s3: S3Resource,
    settings: SettingsResource,
    index_name: str,
    index_model_class: type,
    op_name: str,
) -> str:
    """Publish spectral index to STAC.

    :param context: Dagster context
    :param s3: S3 resource
    :param settings: Settings resource
    :param index_name: Index name (e.g., "ndvi", "ndmi")
    :param index_model_class: Index model class (NDVI or NDMI)
    :param op_name: Operation name for partition key extraction
    :returns: S3 key where STAC item was published
    """
    try:
        if hasattr(context, "partition_key") and context.partition_key:
            parts = context.partition_key.split("|")
            if len(parts) == 2:
                date_str, field_id = parts
            else:
                date_str, field_id = parse_partition_key(context, op_name)
        else:
            date_str, field_id = parse_partition_key(context, op_name)
    except Exception:
        date_str, field_id = parse_partition_key(context, op_name)

    s3_client = s3.get_client()
    bucket = settings.aws_s3_pipeline_bucket_name
    s3_key = f"pipeline-outputs/{field_id}/{index_name}/{date_str}.parquet"

    field = load_field_from_s3_geoparquet(context, s3_client, bucket, s3_key, index_name, index_model_class)
    ensure_catalog_structure(context, s3, settings, bucket, s3_client=s3_client)

    stac_item = create_stac_item_json(field, date_str, field_id, index_name, s3_key, bucket)
    add_stac_links(stac_item, bucket, field_id, index_name, date_str)

    return publish_stac_item_idempotent(context, s3, settings, stac_item, s3_client=s3_client)
