from types import SimpleNamespace

from plantation_monitoring import assets
from plantation_monitoring.config.constants import NDVI_BAND_PREFERENCES
from plantation_monitoring.models.models import Field


def make_context(date: str, field_id: str) -> SimpleNamespace:
    """
    Create a fake Dagster context for testing.

    Args:
      date: Date string for partition
      field_id: Field ID for partition

    Returns:
      SimpleNamespace mimicking AssetExecutionContext
    """
    partition_key = SimpleNamespace(keys_by_dimension={"date": date, "field_id": field_id})
    logger = SimpleNamespace(
        info=lambda *_, **__: None,
        error=lambda *_, **__: None,
        warning=lambda *_, **__: None,
    )
    return SimpleNamespace(partition_key=partition_key, log=logger)


def test_extract_partition_keys() -> None:
    """
    Test that partition keys are correctly extracted from context.
    """
    ctx = make_context("2024-10-01", "field_1")
    date, fid = assets._extract_partition_keys(ctx)
    assert date == "2024-10-01"
    assert fid == "field_1"


def test_find_field_by_id_and_eligibility() -> None:
    """
    Test field lookup and eligibility checking.

    Verifies:
    - Field can be found by ID
    - Field eligibility check returns error for dates before planting
    """
    field = Field(
        id="field_1", plant_type="wheat", plant_date="2024-10-02", geom={"type": "Point", "coordinates": [0, 0]}
    )

    found = assets._find_field_by_id([field], "field_1")
    assert found is field

    ctx = make_context("2024-10-01", "field_1")
    output = assets._check_field_eligibility(ctx, field, "2024-10-01", "ndvi")
    assert output is not None
    # Metadata values may be wrapped in Dagster metadata types
    success_value = output.metadata["success"]
    assert success_value is False or (hasattr(success_value, "value") and success_value.value is False)
    computed_value = output.metadata["ndvi_computed"]
    assert computed_value is False or (hasattr(computed_value, "value") and computed_value.value is False)


def test_prepare_band_urls_missing_band_returns_error() -> None:
    """
    Test that missing required bands return an error output.

    When a STAC item doesn't have all required bands,
    the function should return None for band_urls and an error Output.
    """
    item = SimpleNamespace(assets={"B04": SimpleNamespace(href="http://red")})
    field = Field(
        id="field_1", plant_type="wheat", plant_date="2024-10-02", geom={"type": "Point", "coordinates": [0, 0]}
    )
    ctx = make_context("2024-10-03", "field_1")

    band_urls, error_output = assets._prepare_band_urls(
        context=ctx,
        item=item,
        band_preferences=NDVI_BAND_PREFERENCES,
        field=field,
        index_name="ndvi",
    )
    assert band_urls is None
    assert error_output is not None
    # Metadata values may be wrapped in Dagster metadata types
    success_value = error_output.metadata["success"]
    assert success_value is False or (hasattr(success_value, "value") and success_value.value is False)
    error_msg = error_output.metadata["error"]
    if hasattr(error_msg, "value"):
        error_msg = error_msg.value
    assert "Could not find required bands" in str(error_msg)
