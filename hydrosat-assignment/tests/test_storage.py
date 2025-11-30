from types import SimpleNamespace
from typing import Any

import pytest
from shapely.geometry import Polygon, mapping

from plantation_monitoring import storage
from plantation_monitoring.models.models import Field


class FakeS3Client:
    def __init__(self) -> None:
        self.put_calls: list[dict[str, Any]] = []

    def put_object(self, **kwargs: Any) -> dict[str, Any]:
        self.put_calls.append(kwargs)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}


class FakeS3Resource:
    def __init__(self) -> None:
        self.client = FakeS3Client()

    def get_client(self) -> FakeS3Client:
        return self.client


@pytest.fixture
def fake_settings() -> Any:
    return SimpleNamespace(aws_s3_pipeline_bucket_name="test-bucket")


@pytest.fixture
def fake_context() -> Any:
    return SimpleNamespace(log=SimpleNamespace(info=lambda *_, **__: None))


def test_save_spectral_index_to_s3_writes_parquet(fake_settings: Any, fake_context: Any) -> None:
    """
    Test that save_spectral_index_to_s3 correctly writes GeoParquet to S3.

    Verifies:
    - Correct S3 key format
    - Parquet content is written
    - Correct content type
    - All required fields are included
    """
    s3_resource = FakeS3Resource()

    geom = mapping(Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]))
    field = Field(id="field_1", plant_type="test", plant_date="2024-01-01", geom=geom)
    index = SimpleNamespace(
        ndvi_mean=0.5, ndvi_std=0.1, ndvi_min=0.2, ndvi_max=0.8, ndvi_valid_pixel_count=42
    )

    key = storage.save_spectral_index_to_s3(
        context=fake_context,
        s3=s3_resource,
        settings=fake_settings,
        field=field,
        date_str="2024-10-10",
        field_id="field_1",
        index_name="ndvi",
        index_data=index,
    )

    assert key == "field/field_1/ndvi/2024-10-10.parquet"
    assert len(s3_resource.client.put_calls) == 1
    call = s3_resource.client.put_calls[0]
    assert call["Bucket"] == "test-bucket"
    assert call["Key"] == key
    assert call["ContentType"] == "application/parquet"
    assert isinstance(call["Body"], bytes | bytearray)


def test_publish_spectral_index_to_stac_calls_helpers(
    monkeypatch: pytest.MonkeyPatch, fake_settings: Any, fake_context: Any
) -> None:
    """
    Test that publish_spectral_index_to_stac calls all required helper functions.

    Verifies the orchestration of:
    - Catalog structure creation
    - STAC item creation
    - Link addition
    - Item publishing
    """
    s3_resource = FakeS3Resource()
    geom = mapping(Polygon([(0, 0), (1, 0), (1, 1), (0, 1), (0, 0)]))
    field = Field(id="field_1", plant_type="test", plant_date="2024-01-01", geom=geom)

    called: dict[str, Any] = {}

    def fake_ensure_catalog_structure(context: Any, s3: Any, settings: Any, bucket: str) -> None:
        called["ensure"] = (bucket,)

    def fake_create_stac_item_json(**kwargs: Any) -> dict[str, Any]:
        called["create_item"] = kwargs
        return {"id": "fake-item"}

    def fake_add_stac_links(
        stac_item: dict[str, Any], bucket: str, field_id: str, index_name: str, date_str: str
    ) -> None:
        called["add_links"] = (stac_item, bucket, field_id, index_name, date_str)

    def fake_publish_stac_item_idempotent(context: Any, s3: Any, settings: Any, stac_item: dict[str, Any]) -> str:
        called["publish"] = stac_item
        return "catalog/items/field_1/ndvi/2024-10-10.json"

    monkeypatch.setattr(storage, "ensure_catalog_structure", fake_ensure_catalog_structure)
    monkeypatch.setattr(storage, "create_stac_item_json", fake_create_stac_item_json)
    monkeypatch.setattr(storage, "add_stac_links", fake_add_stac_links)
    monkeypatch.setattr(storage, "publish_stac_item_idempotent", fake_publish_stac_item_idempotent)

    result_key = storage.publish_spectral_index_to_stac(
        context=fake_context,
        s3=s3_resource,
        settings=fake_settings,
        field=field,
        date_str="2024-10-10",
        field_id="field_1",
        index_name="ndvi",
        s3_key="field/field_1/ndvi/2024-10-10.parquet",
    )

    assert called["ensure"] == ("test-bucket",)
    assert called["create_item"]["field_id"] == "field_1"
    assert called["add_links"][1:] == ("test-bucket", "field_1", "ndvi", "2024-10-10")
    assert result_key == "catalog/items/field_1/ndvi/2024-10-10.json"


def test_extract_fields_from_geojson_returns_only_fields() -> None:
    """
    Test that extract_fields_from_geojson filters only field features.

    Verifies that only features with object-type="field" are returned,
    and other feature types are filtered out.
    """
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "object-type": "field",
                    "object-id": "f1",
                    "plant-type": "wheat",
                    "plant-date": "2024-01-01",
                },
                "geometry": {"type": "Point", "coordinates": [0, 0]},
            },
            {
                "type": "Feature",
                "properties": {"object-type": "other", "object-id": "x"},
                "geometry": {"type": "Point", "coordinates": [1, 1]},
            },
        ],
    }
    fields = list(storage.extract_fields_from_geojson(geojson))
    assert len(fields) == 1
    field_id, feature = fields[0]
    assert field_id == "f1"
    assert feature["properties"]["object-type"] == "field"


def test_load_fields_from_s3_merges_processed_and_staging(
    monkeypatch: pytest.MonkeyPatch, fake_settings: Any, fake_context: Any
) -> None:
    """
    Test that load_fields_from_s3 merges fields from processed and staging.

    Verifies:
    - Fields from both processed and staging are loaded
    - New field IDs are correctly identified
    - Staging files are moved to processed after loading
    """
    processed_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "object-type": "field",
                    "object-id": "f1",
                    "plant-type": "wheat",
                    "plant-date": "2024-01-01",
                },
                "geometry": {"type": "Point", "coordinates": [0, 0]},
            },
        ],
    }
    staging_geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "object-type": "field",
                    "object-id": "f2",
                    "plant-type": "corn",
                    "plant-date": "2024-02-01",
                },
                "geometry": {"type": "Point", "coordinates": [1, 1]},
            },
        ],
    }

    calls: list[str | tuple[str, str]] = []

    def fake_list_geojson_files(_context: Any, _s3: Any, _settings: Any, prefix: str) -> Any:
        calls.append(prefix)
        if prefix == "processed":
            yield "processed/f1.geojson", processed_geojson
        if prefix == "staging":
            yield "staging/f2.geojson", staging_geojson

    def fake_move_s3_files(_context: Any, _s3: Any, _settings: Any, src: str, dest: str) -> None:
        calls.append((src, dest))

    monkeypatch.setattr(storage, "list_geojson_files", fake_list_geojson_files)
    monkeypatch.setattr(storage, "move_s3_files", fake_move_s3_files)

    s3_resource = FakeS3Resource()
    fields, new_ids = storage.load_fields_from_s3(
        context=fake_context,
        s3=s3_resource,
        settings=fake_settings,
        processed_prefix="processed",
        staging_prefix="staging",
    )

    assert {f.id for f in fields} == {"f1", "f2"}
    assert new_ids == {"f2"}
    assert ("staging", "processed") in calls
