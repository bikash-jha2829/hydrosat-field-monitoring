"""STAC operations for searching and accessing satellite imagery."""

from typing import Any

from dagster import AssetExecutionContext, OpExecutionContext
from planetary_computer import sign

from plantation_monitoring.config.constants import DEFAULT_CLOUD_COVER_THRESHOLD


def search_first_sentinel_item(
    context: OpExecutionContext | AssetExecutionContext,
    stac_client: Any,
    intersects: dict[str, Any],
    date_str: str,
    cloud_cover_lt: int = DEFAULT_CLOUD_COVER_THRESHOLD,
) -> tuple[Any | None, list[str]]:
    """Search Sentinel-2 items and return first match.

    :param context: Dagster context
    :param stac_client: STAC client
    :param intersects: Geometry dictionary
    :param date_str: Date string
    :param cloud_cover_lt: Maximum cloud cover percentage
    :returns: Tuple of (item or None, available_assets)
    """
    items = list(
        stac_client.search(
            collections=["sentinel-2-l2a"],
            intersects=intersects,
            datetime=f"{date_str}/{date_str}",
            query={"eo:cloud_cover": {"lt": cloud_cover_lt}},
        ).items()
    )

    if not items:
        context.log.info(f"No Sentinel-2 items found for {date_str}")
        return None, []

    item = items[0]
    available_assets = list(item.assets.keys())
    context.log.info(f"Available assets: {available_assets}")
    return item, available_assets


def select_and_sign_band_urls(
    item: Any,
    band_preferences: dict[str, list[str]],
) -> tuple[dict[str, str] | None, list[str], list[str]]:
    """Select and sign band URLs based on preferences.

    :param item: STAC item
    :param band_preferences: Band preference mapping
    :returns: Tuple of (signed_urls or None, available_assets, missing_labels)
    """
    available_assets = list(item.assets.keys())
    signed_urls = {}
    missing = []

    for label, candidates in band_preferences.items():
        for asset_key in candidates:
            if asset_key in item.assets:
                signed_urls[label] = sign(item.assets[asset_key].href)
                break
        else:
            missing.append(label)

    return (None, available_assets, missing) if missing else (signed_urls, available_assets, missing)
