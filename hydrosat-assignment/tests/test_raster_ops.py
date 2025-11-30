from pathlib import Path

import numpy as np
import rasterio
from affine import Affine
from numpy.typing import NDArray
from shapely.geometry import Polygon, mapping

from plantation_monitoring.geospatial import raster_ops


def _write_geotiff(
    path: Path, data: NDArray[np.floating], crs: str = "EPSG:4326", transform: Affine | None = None
) -> None:
    """
    Helper function to write a GeoTIFF file for testing.

    Args:
      path: Path to write the GeoTIFF
      data: NumPy array with raster data
      crs: Coordinate reference system
      transform: Affine transform (defaults to simple scale)
    """
    height, width = data.shape
    transform = transform or Affine.translation(0, 0) * Affine.scale(1, -1)
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype=data.dtype,
        crs=crs,
        transform=transform,
    ) as dst:
        dst.write(data, 1)


def test_read_band_window_masks_to_geometry(tmp_path: Path) -> None:
    """
    Test that read_band_window correctly masks data to the provided geometry.

    Verifies that only pixels within the geometry bounds are returned
    and values outside are masked as NaN.
    """
    data = np.array([[1, 2], [3, 4]], dtype="float32")
    tif_path = tmp_path / "test.tif"
    # One-degree pixels starting at (0,0); y decreasing to match Affine.scale(1, -1)
    transform = Affine.translation(0, 0) * Affine.scale(1, -1)
    _write_geotiff(tif_path, data, transform=transform)

    # Geometry covers only the top-left pixel
    geom = mapping(Polygon([(0, 0), (1, 0), (1, -1), (0, -1), (0, 0)]))

    window = raster_ops.read_band_window(str(tif_path), geom, geom_crs="EPSG:4326")
    assert window.shape == (1, 1)
    np.testing.assert_allclose(window[0, 0], 1.0)


def test_compute_ndvi_from_cog_urls_matches_expected(tmp_path: Path) -> None:
    """
    Test that NDVI computation produces expected results.

    Verifies the NDVI formula: (NIR - Red) / (NIR + Red)
    with known input values.
    """
    red = np.array([[1, 1], [1, 1]], dtype="float32")
    nir = np.array([[3, 3], [3, 3]], dtype="float32")
    red_path = tmp_path / "red.tif"
    nir_path = tmp_path / "nir.tif"
    _write_geotiff(red_path, red)
    _write_geotiff(nir_path, nir)

    geom = mapping(Polygon([(0, 0), (2, 0), (2, -2), (0, -2), (0, 0)]))
    ndvi = raster_ops.compute_ndvi_from_cog_urls(str(red_path), str(nir_path), bbox_geom=geom, geom_crs="EPSG:4326")
    assert ndvi.shape == (2, 2)
    expected = np.full((2, 2), 0.5, dtype="float32")
    np.testing.assert_allclose(ndvi, expected, rtol=1e-5)


def test_compute_ndmi_from_cog_urls_resamples_swir(tmp_path: Path) -> None:
    """
    Test that NDMI computation correctly resamples SWIR to match NIR resolution.

    Verifies that when NIR and SWIR have different resolutions,
    SWIR is resampled to match NIR before computing NDMI.
    """
    nir = np.array([[4, 4], [4, 4]], dtype="float32")
    swir = np.array([[2]], dtype="float32")
    nir_path = tmp_path / "nir.tif"
    swir_path = tmp_path / "swir.tif"
    _write_geotiff(nir_path, nir)
    _write_geotiff(swir_path, swir)

    geom = mapping(Polygon([(0, 0), (2, 0), (2, -2), (0, -2), (0, 0)]))
    ndmi = raster_ops.compute_ndmi_from_cog_urls(str(nir_path), str(swir_path), bbox_geom=geom, geom_crs="EPSG:4326")
    expected_value = (4 - 2) / (4 + 2)
    valid_mask = ~np.isnan(ndmi)
    assert np.any(valid_mask), "Should have at least some valid pixels"
    np.testing.assert_allclose(ndmi[valid_mask], expected_value, rtol=1e-2, atol=1e-2)
