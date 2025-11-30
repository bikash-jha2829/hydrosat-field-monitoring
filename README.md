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
- [Future Improvements](#future-improvements)

## 🎯 Overview

This pipeline enables automated processing of satellite imagery from Sentinel-2 to monitor field health and irrigation needs. It uses **Dagster** for orchestration, **Kubernetes (k3d)** for deployment, and **MinIO** (S3-compatible) for storage.

The system ingests Sentinel-2 satellite imagery based on field geometries and date ranges, processes raw satellite data to compute spectral indices (NDVI and NDMI), stores processed results in S3-compatible storage, publishes results to a STAC (SpatioTemporal Asset Catalog) for easy querying, and provides a FastAPI interface for querying field health data.

### Why Catalog Raw Data?

To maintain an internal archive, avoid future data loss, and reduce egress costs from commercial providers. By cataloging processed data in STAC format, we enable efficient querying and reuse without repeated API calls to external providers.

## 🏗️ Architecture

The system is built on a microservices architecture:

- **Dagster**: Orchestrates the data pipeline with daily partitioned assets, auto-materialization policies, and sensor-based triggers
- **Kubernetes (k3d)**: Container orchestration for scalable deployment of Dagster services
- **MinIO**: S3-compatible object storage for field geometries, processed data, and STAC catalogs
- **FastAPI**: RESTful API service for querying processed field data via STAC endpoints
- **Planetary Computer**: External STAC API provider for Sentinel-2 satellite imagery
- **Jupyter Notebooks**: Interactive analysis and visualization of field health metrics

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

## 🔮 Future Improvements

### Short Term

- Additional spectral indices (EVI, SAVI, NDWI) for enhanced analysis
- Multi-satellite support (Landsat, MODIS) for increased temporal resolution
- Advanced filtering options for cloud cover and data quality
- Batch processing optimizations for large-scale operations

### Medium Term

- Machine learning integration for crop yield prediction and disease detection
- Automated alerting system for fields requiring immediate attention
- Web-based dashboard for real-time field monitoring
- Historical trend analysis and forecasting capabilities

### Long Term

- Real-time processing pipeline for near-instantaneous updates
- Multi-region support for scaling to multiple geographic areas
- Advanced analytics with anomaly detection and predictive modeling
- Integration with farm management systems and IoT sensors

## 📚 Additional Resources

- [Dagster Documentation](https://docs.dagster.io/)
- [STAC Specification](https://stacspec.org/)
- [Planetary Computer](https://planetarycomputer.microsoft.com/)
- [Sentinel-2 Documentation](https://sentinel.esa.int/web/sentinel/missions/sentinel-2)

---

**Built with** 🌱 **for sustainable agriculture and efficient field monitoring**
