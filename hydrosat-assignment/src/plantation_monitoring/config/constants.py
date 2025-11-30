"""Constants for S3 paths and configuration."""

DEFAULT_TMP_DIR = "/tmp"
DEFAULT_PARTITION_START_DATE = "2025-10-01"
DEFAULT_CLOUD_COVER_THRESHOLD = 30

AWS_S3_PIPELINE_STATICDATA_FIELDS_PENDING_KEY = "raw_catalog/fields/staging"
AWS_S3_PIPELINE_STATICDATA_FIELDS_PROCESSED_KEY = "raw_catalog/fields/processed"

AWS_S3_PIPELINE_STATICDATA_BBOX_PENDING_KEY = "raw_catalog/bbox/staging"
AWS_S3_PIPELINE_STATICDATA_BBOX_PROCESSED_KEY = "raw_catalog/bbox/processed"
AWS_S3_PIPELINE_STATICDATA_BBOX_FALLBACK_KEY = "raw_catalog/config/bbox.geojson"

NDVI_BAND_PREFERENCES: dict[str, list[str]] = {
    "red": ["B04", "red", "visual", "B04_visual"],
    "nir": ["B08", "nir", "B08_visual"],
}

NDMI_BAND_PREFERENCES: dict[str, list[str]] = {
    "nir": ["B08", "nir", "B08_visual"],
    "swir": ["B11", "swir16", "B12", "swir"],
}
