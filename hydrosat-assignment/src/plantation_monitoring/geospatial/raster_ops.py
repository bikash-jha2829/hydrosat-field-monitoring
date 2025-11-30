"""Geospatial and raster operations for spectral index computation."""

from typing import Any

import numpy as np
import rasterio
import rasterio.warp
from numpy.typing import NDArray
from rasterio.enums import Resampling
from rasterio.mask import geometry_mask
from rasterio.windows import from_bounds
from shapely.geometry import mapping, shape


def _get_geom_dict(bbox_geom: dict[str, Any] | None) -> dict[str, Any] | None:
    """Convert geometry to dictionary format.

    :param bbox_geom: Geometry dict or shapely object
    :returns: Geometry dictionary or None
    """
    if bbox_geom is None:
        return None
    if isinstance(bbox_geom, dict):
        return bbox_geom
    return mapping(bbox_geom)


def resample_band_to_match(
    source_data: NDArray[np.floating],
    source_transform: Any,
    source_crs: str,
    target_shape: tuple[int, ...],
    target_transform: Any,
    target_crs: str,
    bbox_transformed_shape: Any = None,
    resampling: Resampling = Resampling.bilinear,
) -> NDArray[np.floating]:
    """Resample source band to match target shape and transform.

    Used when bands have different resolutions (e.g., NIR 10m vs SWIR 20m).

    :param source_data: Source band array
    :param source_transform: Source transform
    :param source_crs: Source CRS
    :param target_shape: Target shape
    :param target_transform: Target transform
    :param target_crs: Target CRS
    :param bbox_transformed_shape: Optional transformed bbox shape
    :param resampling: Resampling method
    :returns: Resampled array
    """
    dst_data = np.full(target_shape, np.nan, dtype="float32")
    rasterio.warp.reproject(
        source=source_data,
        destination=dst_data,
        src_transform=source_transform,
        src_crs=source_crs,
        dst_transform=target_transform,
        dst_crs=target_crs,
        src_nodata=np.nan,
        dst_nodata=np.nan,
        resampling=resampling,
    )

    if bbox_transformed_shape is not None:
        mask = geometry_mask(
            [bbox_transformed_shape],
            transform=target_transform,
            invert=True,
            out_shape=target_shape,
        )
        dst_data[~mask] = np.nan

    return dst_data


def _read_and_mask_band(
    src: Any, geom_dict: dict[str, Any] | None, geom_crs: str
) -> tuple[NDArray[np.floating], Any, Any]:
    """Read and mask band from raster source.

    :param src: Raster source
    :param geom_dict: Geometry dictionary or None
    :param geom_crs: Geometry CRS
    :returns: Tuple of (data, transform, bbox_shape)
    """
    if geom_dict:
        bbox_transformed = rasterio.warp.transform_geom(src_crs=geom_crs, dst_crs=src.crs, geom=geom_dict)
        bbox_shape = shape(bbox_transformed)
        window = from_bounds(*bbox_shape.bounds, transform=src.transform)
        data = src.read(1, window=window).astype("float32")
        window_transform = src.window_transform(window)
        mask = geometry_mask([bbox_shape], transform=window_transform, invert=True, out_shape=data.shape)
        data[~mask] = np.nan
        return data, window_transform, bbox_shape
    data = src.read(1).astype("float32")
    return data, src.transform, None


def compute_ndvi_from_cog_urls(
    red_url: str, nir_url: str, bbox_geom: dict[str, Any] | None = None, geom_crs: str = "EPSG:4326"
) -> NDArray[np.floating]:
    """Compute NDVI from red and NIR bands.

    Resamples red to match NIR grid if shapes differ.

    :param red_url: Red band COG URL
    :param nir_url: NIR band COG URL
    :param bbox_geom: Optional bbox geometry
    :param geom_crs: Geometry CRS
    :returns: NDVI array
    """
    geom_dict = _get_geom_dict(bbox_geom)

    with rasterio.open(red_url) as red_src, rasterio.open(nir_url) as nir_src:
        red_data, red_transform, red_shape = _read_and_mask_band(red_src, geom_dict, geom_crs)
        nir_data, nir_transform, nir_shape = _read_and_mask_band(nir_src, geom_dict, geom_crs)

        if red_data.shape != nir_data.shape:
            red_data = resample_band_to_match(
                source_data=red_data,
                source_transform=red_transform,
                source_crs=red_src.crs,
                target_shape=nir_data.shape,
                target_transform=nir_transform,
                target_crs=nir_src.crs,
                bbox_transformed_shape=nir_shape,
            )

    ndvi: NDArray[np.floating] = (nir_data - red_data) / (nir_data + red_data + 1e-6)
    return ndvi


def compute_ndmi_from_cog_urls(
    nir_url: str, swir_url: str, bbox_geom: dict[str, Any] | None = None, geom_crs: str = "EPSG:4326"
) -> NDArray[np.floating]:
    """Compute NDMI from NIR and SWIR bands.

    Resamples SWIR to match NIR grid if resolutions differ.

    :param nir_url: NIR band COG URL
    :param swir_url: SWIR band COG URL
    :param bbox_geom: Optional bbox geometry
    :param geom_crs: Geometry CRS
    :returns: NDMI array
    """
    geom_dict = _get_geom_dict(bbox_geom)

    with rasterio.open(nir_url) as nir_src, rasterio.open(swir_url) as swir_src:
        nir_data, nir_transform, nir_shape = _read_and_mask_band(nir_src, geom_dict, geom_crs)
        swir_data, swir_transform, _ = _read_and_mask_band(swir_src, geom_dict, geom_crs)

        if nir_data.shape != swir_data.shape:
            swir_data = resample_band_to_match(
                source_data=swir_data,
                source_transform=swir_transform,
                source_crs=swir_src.crs,
                target_shape=nir_data.shape,
                target_transform=nir_transform,
                target_crs=nir_src.crs,
                bbox_transformed_shape=nir_shape,
            )

    ndmi: NDArray[np.floating] = (nir_data - swir_data) / (nir_data + swir_data + 1e-6)
    return ndmi
