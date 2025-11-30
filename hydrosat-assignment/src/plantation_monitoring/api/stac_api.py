"""FastAPI application for querying STAC catalog from S3.

This API reads directly from S3 on each request, so new data pushed to S3
will be immediately available without restarting the API server.
"""

import json
from datetime import datetime as dt
from typing import Any

from botocore.exceptions import ClientError
from fastapi import FastAPI, HTTPException, Query

from plantation_monitoring.connectors.s3_client import S3Resource
from plantation_monitoring.connectors.settings import SettingsResource

COLLECTION_ID = "field-indices"
ITEMS_PREFIX = "catalog/items/"

app = FastAPI(
    title="STAC API",
    description="STAC catalog API for querying field spectral indices",
    version="1.0.0",
)

settings = SettingsResource.create(swallow_errors=True)
s3_resource = S3Resource(settings=settings)
s3_client = s3_resource.get_client()
bucket_name = settings.aws_s3_pipeline_bucket_name


def _load_json_from_s3(key: str) -> dict[str, Any]:
    """Load JSON object from S3.

    :param key: S3 key
    :returns: JSON dictionary
    :raises HTTPException: If object not found
    """
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        content = response["Body"].read().decode("utf-8")
        result: dict[str, Any] = json.loads(content)
        return result
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "NoSuchKey":
            raise HTTPException(status_code=404, detail=f"STAC object not found: {key}") from e
        raise HTTPException(status_code=500, detail=f"Error loading from S3: {e}") from e


def _filter_by_datetime(items: list[dict[str, Any]], datetime_filter: str) -> list[dict[str, Any]]:
    """Filter items by datetime.

    Supports prefix matching (e.g., "2025-01") and ISO 8601 intervals.

    :param items: List of STAC items
    :param datetime_filter: Datetime filter string
    :returns: Filtered items
    """
    filtered = []
    for item in items:
        item_datetime = item.get("properties", {}).get("datetime", "")
        if not item_datetime:
            continue

        if "/" in datetime_filter:
            start_str, end_str = datetime_filter.split("/", 1)
            try:
                start_dt = dt.fromisoformat(start_str.replace("Z", "+00:00").replace("T", " "))
                end_dt = dt.fromisoformat(end_str.replace("Z", "+00:00").replace("T", " "))
                item_dt = dt.fromisoformat(item_datetime.replace("Z", "+00:00").replace("T", " "))
                if start_dt <= item_dt <= end_dt:
                    filtered.append(item)
            except (ValueError, AttributeError):
                continue
        elif item_datetime.startswith(datetime_filter):
            filtered.append(item)

    return filtered


def _list_items() -> list[dict[str, Any]]:
    """List all STAC items from S3.

    :returns: List of STAC item dictionaries
    """
    items = []
    paginator = s3_client.get_paginator("list_objects_v2")
    page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=ITEMS_PREFIX)

    for page in page_iterator:
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".json"):
                try:
                    item = _load_json_from_s3(key)
                    items.append(item)
                except HTTPException:
                    continue

    return items


def _apply_filters(
    items: list[dict[str, Any]],
    field_id: str | None = None,
    index_type: str | None = None,
    datetime_filter: str | None = None,
    bbox: list[float] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Apply filters to STAC items.

    :param items: List of STAC items
    :param field_id: Filter by field ID
    :param index_type: Filter by index type (NDVI, NDMI)
    :param datetime_filter: Filter by datetime
    :param bbox: Filter by bounding box [min_lon, min_lat, max_lon, max_lat]
    :param limit: Maximum number of items to return
    :returns: Filtered items
    """
    filtered = items
    if field_id:
        filtered = [item for item in filtered if item.get("properties", {}).get("field_id") == field_id]
    if index_type:
        filtered = [item for item in filtered if item.get("properties", {}).get("index_type") == index_type.upper()]
    if datetime_filter:
        filtered = _filter_by_datetime(filtered, datetime_filter)
    if bbox and len(bbox) == 4:
        min_lon, min_lat, max_lon, max_lat = bbox
        filtered = [
            item
            for item in filtered
            if item.get("bbox")
            and item["bbox"][0] >= min_lon
            and item["bbox"][1] >= min_lat
            and item["bbox"][2] <= max_lon
            and item["bbox"][3] <= max_lat
        ]
    if limit is not None:
        filtered = filtered[:limit]
    return filtered


@app.get("/collections/{collection_id}/items")
def list_collection_items(
    collection_id: str,
    limit: int = Query(default=10, ge=1, le=1000),
    bbox: str | None = Query(default=None, description="Bounding box: min_lon,min_lat,max_lon,max_lat"),
    datetime: str | None = Query(default=None, description="Date filter (e.g., '2025-01' or '2025-01-01T00:00:00Z/2025-01-31T23:59:59Z')"),
    field_id: str | None = Query(default=None, description="Filter by field ID"),
    index_type: str | None = Query(default=None, description="Filter by index type (NDVI, NDMI)"),
) -> dict[str, Any]:
    """List items in collection with filters.

    Essential endpoint for querying field data by field_id, date, index_type, and bounding box.

    :param collection_id: Collection ID (must be "field-indices")
    :param limit: Maximum number of items to return
    :param bbox: Bounding box filter (comma-separated: min_lon,min_lat,max_lon,max_lat)
    :param datetime: Datetime filter (prefix or ISO 8601 interval)
    :param field_id: Field ID filter
    :param index_type: Index type filter (NDVI, NDMI)
    :returns: FeatureCollection with filtered items
    """
    if collection_id != COLLECTION_ID:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")

    all_items = _list_items()

    bbox_values = None
    if bbox:
        try:
            bbox_values = [float(x) for x in bbox.split(",")]
            if len(bbox_values) != 4:
                raise HTTPException(status_code=400, detail="Invalid bbox, expected four values")
        except ValueError as e:
            raise HTTPException(status_code=400, detail="Invalid bbox format, expected comma-separated floats") from e

    filtered_items = _apply_filters(
        all_items,
        field_id=field_id,
        index_type=index_type,
        datetime_filter=datetime,
        bbox=bbox_values,
        limit=limit,
    )

    return {
        "type": "FeatureCollection",
        "features": filtered_items,
        "links": [
            {"rel": "self", "href": f"/collections/{collection_id}/items", "type": "application/geo+json"},
        ],
    }


@app.get("/collections/{collection_id}/items/{item_id}")
def get_item(collection_id: str, item_id: str) -> dict[str, Any]:
    """Get specific item by ID.

    Item ID format: {field_id}-{index_name}-{date}
    Example: field-123-ndvi-2025-01-15

    :param collection_id: Collection ID (must be "field-indices")
    :param item_id: Item ID
    :returns: STAC Item JSON
    """
    if collection_id != COLLECTION_ID:
        raise HTTPException(status_code=404, detail=f"Collection not found: {collection_id}")

    parts = item_id.split("-")
    if len(parts) < 3:
        raise HTTPException(status_code=400, detail=f"Invalid item ID format: {item_id}")

    field_id, index_name, date_str = parts[0], parts[1], "-".join(parts[2:])
    s3_key = f"{ITEMS_PREFIX}{field_id}/{index_name}/{date_str}.json"

    try:
        return _load_json_from_s3(s3_key)
    except HTTPException as e:
        if e.status_code == 404:
            raise HTTPException(status_code=404, detail=f"Item not found: {item_id}") from e
        raise


@app.post("/search")
def search_items(
    field_id: str | None = None,
    index_type: str | None = None,
    datetime: str | None = None,
    bbox: list[float] | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search STAC items with filters.

    Alternative to GET endpoint for complex queries with JSON body.

    :param field_id: Filter by field ID
    :param index_type: Filter by index type (NDVI, NDMI)
    :param datetime: Datetime filter (prefix or ISO 8601 interval)
    :param bbox: Bounding box [min_lon, min_lat, max_lon, max_lat]
    :param limit: Maximum number of items
    :returns: FeatureCollection with search results
    """
    all_items = _list_items()
    filtered_items = _apply_filters(
        all_items,
        field_id=field_id,
        index_type=index_type,
        datetime_filter=datetime,
        bbox=bbox,
        limit=limit,
    )

    return {
        "type": "FeatureCollection",
        "features": filtered_items,
        "links": [{"rel": "self", "href": "/search", "type": "application/geo+json"}],
    }
