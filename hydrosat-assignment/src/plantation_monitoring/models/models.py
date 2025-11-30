"""Data models for plantation monitoring."""

import json
import uuid
from typing import Any
from uuid import UUID

import geopandas as gpd
import numpy as np
from pydantic import BaseModel, Field as PydanticField
from shapely.geometry import mapping


class Bbox(BaseModel):
    """Bounding box model with geometry and UUID.

    :param id: UUID derived from geometry
    :param bbox: GeoDataFrame containing bbox
    :param geom: GeoJSON geometry dictionary
    """

    id: UUID = PydanticField(..., description="UUIDv5 derived from the geometry")
    bbox: Any = PydanticField(..., description="GeoDataFrame containing the bbox")
    geom: dict[str, Any] = PydanticField(..., description="GeoJSON representation of the geometry")

    @staticmethod
    def get_id_from_geom(geometry: Any) -> UUID:
        """Generate UUIDv5 from geometry.

        :param geometry: Geometry object
        :returns: UUIDv5
        """
        geojson = json.dumps(mapping(geometry), sort_keys=True)
        return uuid.uuid5(uuid.NAMESPACE_URL, geojson)

    @classmethod
    def from_geodataframe(cls, gdf: gpd.GeoDataFrame) -> "Bbox":
        """Create Bbox from GeoDataFrame.

        :param gdf: GeoDataFrame
        :returns: Bbox instance
        """
        geometry = gdf.geometry.iloc[0]
        geom_json = mapping(geometry)
        bbox_id = cls.get_id_from_geom(geometry)
        return cls(id=bbox_id, bbox=gdf, geom=geom_json)


class NDVI(BaseModel):
    """Normalized Difference Vegetation Index model.

    :param ndvi: NDVI values array
    :param ndvi_mean: Mean NDVI value
    :param ndvi_std: Standard deviation
    :param ndvi_min: Minimum value
    :param ndvi_max: Maximum value
    :param ndvi_valid_pixel_count: Valid pixel count
    """

    ndvi: list[list[float]] = PydanticField(..., description="NDVI values")
    ndvi_mean: float = PydanticField(..., description="Mean NDVI value for the field")
    ndvi_std: float = PydanticField(..., description="Standard deviation of NDVI values")
    ndvi_min: float = PydanticField(..., description="Minimum NDVI value for the field")
    ndvi_max: float = PydanticField(..., description="Maximum NDVI value for the field")
    ndvi_valid_pixel_count: int = PydanticField(..., description="Number of valid pixels used for NDVI computation")

    @classmethod
    def from_array(cls, array: Any) -> "NDVI":
        """Create NDVI from numpy array.

        :param array: NDVI numpy array
        :returns: NDVI instance
        """
        array = array.astype("float32")
        valid_pixels = array[~np.isnan(array)]

        return cls(
            ndvi=array.tolist(),
            ndvi_mean=float(np.mean(valid_pixels)) if valid_pixels.size > 0 else 0.0,
            ndvi_std=float(np.std(valid_pixels)) if valid_pixels.size > 0 else 0.0,
            ndvi_min=float(np.min(valid_pixels)) if valid_pixels.size > 0 else 0.0,
            ndvi_max=float(np.max(valid_pixels)) if valid_pixels.size > 0 else 0.0,
            ndvi_valid_pixel_count=int(np.count_nonzero(~np.isnan(array))),
        )


class NDMI(BaseModel):
    """Normalized Difference Moisture Index model.

    :param ndmi: NDMI values array
    :param ndmi_mean: Mean NDMI value
    :param ndmi_std: Standard deviation
    :param ndmi_min: Minimum value
    :param ndmi_max: Maximum value
    :param ndmi_valid_pixel_count: Valid pixel count
    """

    ndmi: list[list[float]] = PydanticField(..., description="NDMI values")
    ndmi_mean: float = PydanticField(..., description="Mean NDMI value for the field")
    ndmi_std: float = PydanticField(..., description="Standard deviation of NDMI values")
    ndmi_min: float = PydanticField(..., description="Minimum NDMI value for the field")
    ndmi_max: float = PydanticField(..., description="Maximum NDMI value for the field")
    ndmi_valid_pixel_count: int = PydanticField(..., description="Number of valid pixels used for NDMI computation")

    @classmethod
    def from_array(cls, array: Any) -> "NDMI":
        """Create NDMI from numpy array.

        :param array: NDMI numpy array
        :returns: NDMI instance
        """
        array = array.astype("float32")
        valid_pixels = array[~np.isnan(array)]

        return cls(
            ndmi=array.tolist(),
            ndmi_mean=float(np.mean(valid_pixels)) if valid_pixels.size > 0 else 0.0,
            ndmi_std=float(np.std(valid_pixels)) if valid_pixels.size > 0 else 0.0,
            ndmi_min=float(np.min(valid_pixels)) if valid_pixels.size > 0 else 0.0,
            ndmi_max=float(np.max(valid_pixels)) if valid_pixels.size > 0 else 0.0,
            ndmi_valid_pixel_count=int(np.count_nonzero(~np.isnan(array))),
        )


class Field(BaseModel):
    """Field model with geometry and spectral indices.

    :param id: Field ID
    :param plant_type: Plant type
    :param plant_date: Planting date
    :param geom: GeoJSON geometry dictionary
    :param ndvi: Optional NDVI data
    :param ndmi: Optional NDMI data
    """

    id: str = PydanticField(..., description="ID of the field")
    plant_type: str = PydanticField(..., description="Type of plant")
    plant_date: str = PydanticField(..., description="Date of planting")
    geom: dict[str, Any] = PydanticField(..., description="GeoJSON representation of the geometry")

    ndvi: NDVI | None = PydanticField(default=None, description="NDVI values")
    ndmi: NDMI | None = PydanticField(default=None, description="NDMI values")
