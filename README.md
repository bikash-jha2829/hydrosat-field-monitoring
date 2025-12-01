# 🌱🛰️ Hydrosat Field Monitoring Pipeline

A Dagster-based pipeline for monitoring plantation field health using satellite imagery. This system processes Sentinel-2 data to compute spectral indices (NDVI and NDMI) and provides insights for irrigation management and crop health monitoring.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Pipeline Flow](#pipeline-flow)
- [Key Features](#key-features)
- [Components](#components)
- [Data Flow](#data-flow)
- [Notes & Assumptions](#notes--assumptions)
- [Handling Large Asset Counts](#handling-large-asset-counts)
- [Future Improvements](#future-improvements)

## 🎯 Overview

This pipeline enables automated processing of satellite imagery from Sentinel-2 to monitor field health and irrigation needs. It uses **Dagster** for orchestration, **Kubernetes (k3d)** for deployment, and **MinIO** (S3-compatible) for storage.

The system ingests Sentinel-2 satellite imagery based on field geometries and date ranges, processes raw satellite data to compute spectral indices (NDVI and NDMI), stores processed results in S3-compatible storage, publishes results to a STAC (SpatioTemporal Asset Catalog) for easy querying, and provides a FastAPI interface for querying field health data.

**Geographic Coverage**: The pipeline is currently configured for **Imperial County, California, USA** (South Imperial Valley region), with Sentinel-2 tile ID `11SPS`. The system processes fields in the Alamo River Basin area, irrigated via the Colorado River through the All-American Canal.

**Crop Types Supported**:
- **Winter Crops**: Lettuce (Iceberg/Romaine), Broccoli, Carrots, Spinach
- **Summer Crops**: Cotton, Alfalfa, Bermuda Grass, Sudan Grass

  ![out2](https://github.com/user-attachments/assets/ec46eb3a-f1ac-4eff-ae0e-dbc93f4388f7)


### Why Catalog Raw Data?

To maintain an internal archive, avoid future data loss, and reduce egress costs from commercial providers. By cataloging processed data in STAC format, we enable efficient querying and reuse without repeated API calls to external providers.

## 🏗️ Architecture

The system is built on a microservices architecture:

- **Dagster**: Orchestrates the data pipeline with daily partitioned assets, auto-materialization policies, and sensor-based triggers
- **Kubernetes (k3d)**: Container orchestration for scalable deployment of Dagster services
- **MinIO**: S3-compatible object storage for field geometries, processed data, and STAC catalogs
- **FastAPI**: RESTful API service for querying processed field data via STAC endpoints
- **Planetary Computer**: External STAC API provider for Sentinel-2 satellite imagery
- **Jupyter Notebooks**: Interactive analysis and visualization of field health metrics (see [`field_analysis.ipynb`](field_analysis.ipynb) for time series analysis, field health classification, and irrigation recommendations)

## 🔄 Pipeline Flow

### Phase 1: Data Ingestion

The pipeline starts by loading field geometries and bounding boxes from S3 storage. These define the area of interest and individual field boundaries for processing.

### Phase 2: Satellite Data Acquisition

For each daily partition, the system queries the Planetary Computer STAC API to find Sentinel-2 L2A imagery matching the field geometries and date range. Results are filtered by cloud cover threshold (default 30%) to ensure data quality.

### Phase 3: Spectral Index Computation

Required spectral bands (Red, NIR, SWIR) are downloaded as Cloud-Optimized GeoTIFFs (COGs), resampled to match field geometries, and used to compute:

- **NDVI** (Normalized Difference Vegetation Index): Measures vegetation health and density
- **NDMI** (Normalized Difference Moisture Index): Measures water content and soil moisture

Statistics (mean, min, max, standard deviation) are extracted for each field.

### Phase 4: Storage & Cataloging

Processed results are saved as GeoParquet files to S3, organized by date and field. STAC items are created with proper metadata and published to a STAC catalog, enabling standards-compliant querying and discovery.

### Phase 5: Query & Analysis

The FastAPI STAC API provides endpoints for querying processed data by field, date, or index type. Jupyter notebooks enable interactive analysis, visualization, and identification of fields needing irrigation.

## ✨ Key Features

- **Dagster Orchestration**: Daily partitioned assets with auto-materialization and sensor-based triggers
- **Kubernetes Deployment**: Scalable deployment using k3d for local development or full Kubernetes for production
- **S3-Compatible Storage**: MinIO for local development, easily switchable to AWS S3 for production
- **Sentinel-2 Integration**: Direct integration with Planetary Computer STAC API for satellite imagery
- **STAC Catalog**: Standards-compliant catalog following STAC specification for geospatial data
- **Spectral Indices**: NDVI for vegetation health and NDMI for moisture content monitoring
- **Interactive Analysis**: Jupyter notebooks for visualization, trend analysis, and field health insights

## 🧩 Components

### Dagster Assets

- **bbox**: Bounding box defining the processing extent
- **fields**: Field geometries with planting dates and crop types
- **field_ndvi**: NDVI computation per field per daily partition
- **field_ndmi**: NDMI computation per field per daily partition

### Resources

- **S3Resource**: S3 client for MinIO or AWS S3 operations
- **STACResource**: STAC API client for querying Planetary Computer
- **SettingsResource**: Configuration management from environment variables

### Partitions

- **Daily Partitions**: Format `YYYY-MM-DD|field_id` for temporal and field-based partitioning
- **Dynamic Field Partitions**: Automatically added when new field geometries are detected
- **Configurable Start Date**: Set via `DAGSTER_PARTITION_START_DATE` environment variable

### Sensors

- **S3 File Sensors**: Monitor S3 buckets for new field or bounding box data and trigger asset materialization

## 📊 Data Flow

**Input Sources**
- Field geometries stored as GeoJSON in S3
- Bounding box defining processing extent
- Sentinel-2 imagery from Planetary Computer STAC API

**Processing Pipeline**
- Dagster orchestrates daily partition execution
- Field geometries are loaded and validated
- Sentinel-2 scenes are queried and filtered by cloud cover
- Spectral bands are downloaded and processed
- NDVI and NDMI indices are computed per field
- Statistics are extracted and aggregated

**Storage Layer**
- Processed data saved as GeoParquet files in S3
- STAC catalog items created with metadata
- Catalog structure follows STAC specification
- Data organized by date and field for efficient querying

**Output & Access**
- STAC catalog enables standards-compliant data discovery
- FastAPI provides RESTful endpoints for querying
- Jupyter notebooks support interactive analysis
- Results enable irrigation management and crop health monitoring

## 📝 Notes & Assumptions

### Current Implementation

- **Sentinel-2 Only**: For simplicity, only Sentinel-2 L2A imagery is currently supported
- **Cloud Cover Threshold**: Default 30% threshold, configurable via environment variable
- **Single Region**: Designed for processing a single area of interest (extensible to multiple regions)
- **Local Storage**: Uses MinIO for local development, production-ready for AWS S3

### Data Quality

- Cloud cover filtering ensures only high-quality imagery is processed
- Spectral indices are computed only when required bands are available
- Missing data is handled gracefully with NaN values in output

### Scalability

- Kubernetes deployment enables horizontal scaling
- Dagster partitions allow parallel processing of multiple fields and dates
- S3 storage supports large-scale data archival and retrieval

## 🚀 Handling Large Asset Counts

The above setup works just fine as long as the Dagster [definitions](https://docs.dagster.io/api/dagster/definitions) hold just few assets in total (< 1000). Once the definitions become large (>> 1000 assets), the job submission time—i.e., the time span from manually or automatically requesting a materialization event to the moment the actual job starts—increases significantly.

### Measuring Job Submission Lag

To measure the job submission lag, you can:

1. **Observability Tools**: Use Dagster's built-in observability or integrate with monitoring tools (Prometheus, Grafana) to track:

   **A. Metrics (Prometheus/Grafana)** - Focus on these three specific metrics to identify bottlenecks:
   
   - **`dagster_run_queued_duration_seconds`**
     - **Signal**: Measures latency between entering the queue and being picked up by a worker.
     - **Alert**: A rising slope (e.g., 2s → 300s) indicates the Daemon cannot keep up with the submission rate.
   
   - **`dagster_run_queue_depth`**
     - **Signal**: The total number of runs waiting to start.
     - **Alert**: A constantly high number indicates a "Backlog." If this grows faster than it drains, we must increase concurrency limits.
   
   - **`dagster_code_location_load_duration_seconds`**
     - **Signal**: How long it takes Dagster to parse `definitions.py`.
     - **Alert**: If this exceeds 60s, the Daemon is spending too much time loading Python code instead of launching runs.
   
   **B. Logs (Loki)** - Use Loki to analyze the Daemon's behavior during the lag. Search your logs for:
   
   - **Code Location Loading**: `grep` for "Loaded code location". If the timestamp difference between "Loading..." and "Loaded..." is high, your Python imports are too heavy.
   
   - **Daemon Loop Time**: `grep` for "Daemon loop finished". If the loop takes longer than the default tick interval (30s), the Daemon is overloaded.



### Solutions Implemented

To overcome job submission lag with large asset counts, we've implemented the following strategies with code examples:

#### 1. Multi-Partitioning Strategy

Instead of creating thousands of individual assets, we use **multi-partitioning** to break down assets by date and field ID. This dramatically reduces the number of asset definitions Dagster needs to load, while still allowing fine-grained materialization control.

**Implementation:**

```python
# Multi-partition combines daily + field dimensions
daily_partitions = DailyPartitionsDefinition(start_date=...)
field_partitions = DynamicPartitionsDefinition(name="field_id")
multi_partitions = MultiPartitionsDefinition({"date": daily_partitions, "field_id": field_partitions})

@asset(partitions_def=multi_partitions, deps=[fields, bbox])
def field_ndvi(context: AssetExecutionContext, ...) -> Output[Field]:
    date_str, field_id = _extract_partition_keys(context)  # Process only this partition
    ...
```

**Benefits:**
- With 100 fields and 365 days, instead of 73,000 asset definitions (100 × 365 × 2 indices), we have only 2 partitioned assets
- Dagster loads 2 asset definitions instead of 73,000, reducing code location load time from minutes to seconds
- Partitions are materialized on-demand, not all at once

#### 2. Dynamic Partition Management

New fields are automatically registered as partitions when detected, avoiding the need to restart Dagster or manually update definitions.

**Implementation:**

```python
@asset(auto_materialize_policy=AutoMaterializePolicy.eager())
def fields(context: AssetExecutionContext, s3: S3Resource, settings: SettingsResource) -> Output[list[Field]]:
    all_fields, new_field_ids = load_fields_from_s3(...)
    
    # Auto-register new fields as dynamic partitions
    if new_field_ids:
        context.instance.add_dynamic_partitions("field_id", list(new_field_ids))
    
    return Output(all_fields, ...)
```

**Benefits:**
- No code changes needed when new fields are added
- Partitions are created dynamically at runtime
- Reduces manual intervention and system restarts

#### 3. Selective Auto-Materialization with Job-Based Triggers

We use **eager auto-materialization** only for upstream assets (`bbox`, `fields`), and combine it with **explicit jobs** triggered by sensors. This ensures only necessary assets are evaluated.

**Implementation:**

```python
# definitions.py
defs = Definitions(
    assets=all_assets,
    jobs=[fields_job, bbox_job],  # Explicit jobs for batch operations
    sensors=[s3_fields_sensor, s3_bbox_sensor],  # Sensors trigger jobs
    ...
)

# triggers/jobs.py
fields_job = define_asset_job(name="fields_job", selection=["fields"])
bbox_job = define_asset_job(name="bbox_job", selection=["bbox"])
```

**Benefits:**
- Jobs allow precise control over which assets to materialize
- Sensors trigger jobs only when new data arrives, not continuously
- Reduces the overhead of evaluating all assets in definitions

#### 4. Sensor-Based Incremental Materialization

S3 file sensors monitor for new data and trigger materialization only when upstream data changes, preventing unnecessary processing.

**Implementation:**

```python
@sensor(job=fields_job, minimum_interval_seconds=5, name="s3_fields_sensor")
def sensor_fn(context: SensorEvaluationContext, s3: S3Resource, settings: SettingsResource):
    # Detect new files and trigger job only when new data arrives
    all_files = s3.get_client().list_objects_v2(Bucket=..., Prefix=...).get("Contents", [])
    previous_files = json.loads(context.cursor) if context.cursor else []
    new_files = list(set(all_files) - set(previous_files))
    
    if new_files:
        for file_key in new_files:
            yield RunRequest(run_key=file_key)
    context.update_cursor(json.dumps(all_files))
```

**Benefits:**
- Materialization triggered only when new data arrives
- Avoids processing all historical partitions at once
- Reduces unnecessary run submissions and queue depth

#### 5. Partition-Aware Asset Dependencies

Partitioned assets depend on non-partitioned upstream assets, ensuring proper dependency resolution without loading all partition combinations.

**Implementation:**

```python
# Non-partitioned upstream assets
@asset(auto_materialize_policy=AutoMaterializePolicy.eager())
def bbox(...) -> Bbox: ...

@asset(auto_materialize_policy=AutoMaterializePolicy.eager())
def fields(...) -> Output[list[Field]]: ...

# Partitioned downstream assets depend on non-partitioned assets
@asset(partitions_def=multi_partitions, deps=[fields, bbox])
def field_ndvi(context: AssetExecutionContext, bbox: Bbox, fields: list[Field], ...) -> Output[Field]:
    date_str, field_id = _extract_partition_keys(context)  # Process only this partition
    ...
```

**Benefits:**
- Clear dependency graph without partition explosion
- Dagster resolves dependencies per partition, not for all combinations
- Reduces graph complexity from O(fields × dates) to O(1) for definitions

### Best Practices

- **Monitor Asset Count**: Regularly check the total number of assets in your definitions. If approaching 1000+, consider splitting into multiple code locations
- **Use Dynamic Partitions Wisely**: While dynamic partitions are powerful, be mindful of partition explosion. Consider archiving old partitions or using time-based retention
- **Batch Operations**: For large backfills, use jobs with explicit partition selection rather than auto-materialization
- **Profile Code Location Loading**: Use Dagster's profiling tools to identify slow imports or initialization code
- **Consider Code Location Splitting**: For very large deployments (>5000 assets), split assets across multiple code locations to reduce per-location load times

## 🔮 Future Improvements
1. Backfill of delayed data
2. TF state management on dynamoDB/Tf cloud
3. Use xarray instead of Rasterio

## 🙏 Acknowledgments

**AI Assistance:**
- Used ChatGPT for research on Dagster framework concepts and best practices
- AI assistance with writing the Makefile for project automation
- AI help with documentation formatting, emoji usage, and structure
- AI assistance with writing docstrings for code documentation

**Code Development:**
- All code implementation was written independently
- Core logic, algorithms, and business logic developed from scratch
- Architecture and design decisions made independently


## 📚 Additional Resources

- [Dagster Documentation](https://docs.dagster.io/)
- [STAC Specification](https://stacspec.org/)
- [Planetary Computer](https://planetarycomputer.microsoft.com/)
- [Sentinel-2 Documentation](https://sentinel.esa.int/web/sentinel/missions/sentinel-2)

---

**🌱 Please Reach out in case of any questions**
