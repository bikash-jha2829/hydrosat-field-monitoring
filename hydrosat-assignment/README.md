# Steps to Run the Project

## Overview

This guide will walk you through setting up and running the Hydrosat Field Monitoring pipeline.

This project processes Sentinel-2 satellite imagery, computes spectral indices (NDVI and NDMI) for plantation fields, and publishes results to a STAC catalog. The pipeline uses Dagster for orchestration, Kubernetes (k3d) for deployment, and MinIO for S3-compatible storage.

<!-- TOC -->

* [Steps to Run the Project](#steps-to-run-the-project)
  * [Overview](#overview)
  * [Prerequisites](#prerequisites)
  * [Setup Instructions](#setup-instructions)
  * [Running the Project](#running-the-project)
  * [Accessing Services](#accessing-services)
  * [Developer Notes](#developer-notes)
  * [Output Files](#output-files)
  * [Troubleshooting](#troubleshooting)

<!-- TOC -->

## Prerequisites

- [ ] **Python 3.11+**: Ensure that Python 3.11 or 3.12 is installed on your machine
- [ ] **Docker**: Required for MinIO and containerized services
- [ ] **Docker Compose**: For running MinIO locally
- [ ] **kubectl**: Kubernetes command-line tool
- [ ] **k3d**: Kubernetes in Docker (for local cluster)
- [ ] **Terraform**: For infrastructure deployment
- [ ] **uv**: Python package manager (will be installed automatically if missing)

### Installing Prerequisites

If any prerequisites are missing, follow these installation instructions:

#### Python 3.11+

```bash
# macOS (using Homebrew)
brew install python@3.11

# Linux (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install python3.11 python3.11-venv

# Verify installation
python3.11 --version
```

#### Docker

```bash
# macOS
# Download Docker Desktop from https://www.docker.com/products/docker-desktop
# Or use Homebrew:
brew install --cask docker

# Linux (Ubuntu/Debian)
sudo apt-get update
sudo apt-get install docker.io docker-compose
sudo systemctl start docker
sudo systemctl enable docker

# Verify installation
docker --version
docker compose version
```

#### kubectl

```bash
# macOS
brew install kubectl

# Linux
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Verify installation
kubectl version --client
```

#### k3d

```bash
# macOS
brew install k3d

# Linux
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash

# Verify installation
k3d version
```

#### Terraform

```bash
# macOS
brew install terraform

# Linux
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform

# Verify installation
terraform version
```

#### uv (Python Package Manager)

```bash
# macOS and Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or using pip
pip install uv

# Verify installation
uv --version
```

## Setup Instructions

### 1. Install Dependencies

The project uses `uv` for dependency management. If you don't have `uv` installed, it will be installed automatically during setup.

```bash
# Clone the repository (if not already done)
git clone <repository-url>
cd hydrosat-assignment

# Install Python dependencies (including dev and notebook groups)
uv sync --all-groups
```

### 2. Configure Environment Variables

Create a `.env` file in the project root (optional - defaults work fine):

```bash
# MinIO Configuration
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin

# Kubernetes Configuration
K3D_CLUSTER_NAME=local-hydrosat-cluster
K8S_DAGSTER_NAMESPACE=dagster

# Dagster Configuration
DAGSTER_PARTITION_START_DATE=2025-10-01
CLOUD_COVER_THRESHOLD=30

# S3 Configuration
AWS_S3_PIPELINE_BUCKET_NAME=hydrosat-pipeline-insights
AWS_S3_ENDPOINT=http://localhost:9000
AWS_ACCESS_KEY_ID=minioadmin
AWS_SECRET_ACCESS_KEY=minioadmin
AWS_REGION=us-east-1

# STAC API
STAC_API_URL=http://localhost:8000
```

### 3. Complete Setup

Run the setup command to initialize all services:

```bash
make setup
```

This command will:
1. Start MinIO (S3-compatible storage)
2. Load sample field data to S3
3. Initialize k3d Kubernetes cluster
4. Build and deploy Dagster to Kubernetes
5. Start STAC API server

**Note:** First-time setup takes 5-10 minutes.

## Running the Project

### Option 1: Full Kubernetes Deployment (Recommended)

After running `make setup`, the pipeline is automatically running in Kubernetes:

```bash
# Check status of all services
make status

# View Dagster UI (Kubernetes deployment)
# Open browser to http://localhost:30080
```

**Note**: When running via Kubernetes, Dagster UI is accessible on port **30080**, not 3000.

### Option 2: Local Development Mode

For local development and testing:

```bash
# Start Dagster dev server
make dev
```

This starts Dagster in development mode on `http://localhost:3000` (different from Kubernetes deployment).

### Materializing Assets

Once Dagster is running, you can materialize assets:

1. **Via Dagster UI**: 
   - Kubernetes: Navigate to http://localhost:30080
   - Dev Mode: Navigate to http://localhost:3000
2. **Select Assets**: Choose `field_ndvi` or `field_ndmi` assets
3. **Select Partitions**: Choose specific date/field combinations (e.g., `2025-10-11|field_1`)
4. **Materialize**: Click "Materialize" to start processing

### Auto-Materialization

The pipeline includes auto-materialization policies:
- `bbox` and `fields` assets auto-materialize when new data arrives
- `field_ndvi` and `field_ndmi` can be configured for auto-materialization

## Accessing Services

### Dagster UI

**Kubernetes Deployment (via `make setup`)**:
- **URL**: http://localhost:30080
- **Example**: http://localhost:30080/runs/b/jzllinjo?tab=runs
- **Purpose**: Monitor pipeline execution, view assets, materialize partitions

**Development Mode (via `make dev`)**:
- **URL**: http://localhost:3000
- **Purpose**: Local development with hot-reload

**Features**: 
- Asset graph visualization
- Partition management
- Run history and logs
- Sensor status
- Materialize assets and partitions

### MinIO Console

- **URL**: http://localhost:9001
- **Username**: `minioadmin`
- **Password**: `minioadmin`
- **Purpose**: Browse S3 buckets, view processed data, manage buckets

**Access Steps**:
1. Open http://localhost:9001 in your browser
2. Enter username: `minioadmin`
3. Enter password: `minioadmin`
4. Click "Login"

**Buckets**:
- `hydrosat-pipeline-insights`: Main data bucket
  - `raw_catalog/`: Field geometries and bounding boxes
  - `pipeline-outputs/`: Processed spectral index data
  - `catalog/`: STAC catalog files

**MinIO API Access (S3-compatible)**:
- **Endpoint**: http://localhost:9000
- **Access Key**: `minioadmin`
- **Secret Key**: `minioadmin`
- **Region**: `us-east-1` (default)

### STAC API

- **URL**: http://localhost:8000
- **Purpose**: Query processed field data via STAC endpoints
- **Endpoints**:
  - `GET /collections/field-indices/items`: List all items
  - `POST /search`: Search with filters

### Kubernetes Dashboard

Access via kubectl proxy:

```bash
kubectl proxy
# Then open http://localhost:8001/api/v1/namespaces/kubernetes-dashboard/services/https:kubernetes-dashboard:/proxy/
```

## Developer Notes

### Project Structure

```
hydrosat-assignment/
├── src/plantation_monitoring/
│   ├── assets.py              # Dagster assets (bbox, fields, field_ndvi, field_ndmi)
│   ├── connectors/            # S3, STAC, Settings resources
│   ├── geospatial/            # Raster operations, STAC publishing
│   ├── models/                 # Pydantic models (Bbox, Field, NDVI, NDMI)
│   ├── storage.py              # S3 I/O operations
│   ├── api/                    # FastAPI STAC API
│   └── triggers/               # Sensors and jobs
├── iac/
│   ├── docker/                 # Docker Compose for MinIO
│   ├── k8s/                    # Kubernetes manifests
│   ├── terraform/              # Infrastructure as Code
│   └── scripts/                # Setup and utility scripts
├── tests/                       # Unit tests
├── field_analysis.ipynb        # Jupyter notebook for analysis
├── Makefile                    # Main commands
└── pyproject.toml              # Project dependencies
```

### Configuration Files

**`src/plantation_monitoring/connectors/settings.py`**
- Centralized configuration management
- Environment variable resolution
- Default values for development

**`src/plantation_monitoring/config/constants.py`**
- S3 path prefixes
- Default thresholds and dates
- Band preferences for spectral indices

### Key Environment Variables

- `DAGSTER_PARTITION_START_DATE`: Start date for daily partitions (default: `2025-10-01`)
- `CLOUD_COVER_THRESHOLD`: Maximum cloud cover percentage (default: `30`)
- `AWS_S3_PIPELINE_BUCKET_NAME`: S3 bucket name (default: `hydrosat-pipeline-insights`)
- `AWS_S3_ENDPOINT`: S3 endpoint URL (default: `http://localhost:9000` for MinIO)

### Common Commands

```bash
# Check service status
make status

# Update after code changes
make k8s-update

# Restart MinIO (if connection issues)
make minio-restart

# Load sample data to S3
make s3-load

# Stop all services (keeps data)
make stop

# Complete cleanup (⚠️ Destructive!)
make clean-all

# Start STAC API
make stac-api-start

# Stop STAC API
make stac-api-stop
```

### Code Changes Workflow

1. **Make code changes** in `src/plantation_monitoring/`
2. **Update deployment**:
   ```bash
   make k8s-update
   ```
   This rebuilds the Docker image and updates the Kubernetes deployment.

3. **Verify changes**:
   - Check Dagster UI for updated code
   - View logs: `kubectl logs -n dagster -l app=dagster`

### Testing

Run unit tests:

```bash
# Run all tests
pytest tests/

# Run specific test file
pytest tests/test_storage.py

# Run with coverage
pytest --cov=src tests/
```

### Linting and Formatting

```bash
# Run all checks
./run_checks.sh

# Or individually:
ruff format .
ruff check .
mypy src/
```

## Output Files

After the pipeline successfully processes data, you will find the following structure in the S3 bucket (`hydrosat-pipeline-insights`):

### 1. Raw Catalog Directory

**Location**: `raw_catalog/`

Contains input data for the pipeline:

- **`bbox/`**: Bounding box geometries (GeoJSON)
  - `staging/`: Newly uploaded files
  - `processed/`: Processed and validated files
  
- **`fields/`**: Field geometries (GeoJSON)
  - `staging/`: Newly uploaded files
  - `processed/`: Processed and validated files

- **`config/`**: Configuration files
  - `bbox.geojson`: Fallback bounding box

### 2. Pipeline Outputs Directory

**Location**: `pipeline-outputs/`

Contains processed spectral index data:

```
pipeline-outputs/
├── 2025-10-11/
│   ├── field_1/
│   │   ├── ndvi.parquet          # NDVI data with field geometry
│   │   └── ndmi.parquet          # NDMI data with field geometry
│   ├── field_2/
│   │   ├── ndvi.parquet
│   │   └── ndmi.parquet
│   └── field_3/
│       ├── ndvi.parquet
│       └── ndmi.parquet
├── 2025-10-16/
│   └── ...
└── ...
```

Each Parquet file contains:
- Field geometry (GeoJSON)
- Spectral index statistics (mean, min, max, std)
- Valid pixel counts
- Field metadata (field_id, plant_type, plant_date)

### 3. STAC Catalog Directory

**Location**: `catalog/`

Contains the STAC catalog structure:

```
catalog/
├── catalog.json                  # Root catalog
├── collection.json              # Field indices collection
└── items/
    ├── field_1_2025-10-11_ndvi.json
    ├── field_1_2025-10-11_ndmi.json
    ├── field_2_2025-10-11_ndvi.json
    └── ...
```

Each STAC item includes:
- Metadata (field_id, plant_type, datetime)
- Spectral index values (ndvi_mean, ndmi_mean, etc.)
- Links to data assets (S3 paths)
- Geometry and bounding box

## Troubleshooting

### MinIO Connection Issues

```bash
# Restart MinIO
make minio-restart

# Check MinIO logs
docker compose -f iac/docker/docker-compose.yml logs minio

# Verify MinIO is running
curl http://localhost:9000/minio/health/live
```

### Dagster Pod Not Starting

```bash
# Check pod status
kubectl get pods -n dagster

# View pod logs
kubectl logs -n dagster -l app=dagster

# Describe pod for events
kubectl describe pod -n dagster <pod-name>

# Restart deployment
kubectl rollout restart deployment/dagster -n dagster
```

### S3 Access Errors

```bash
# Verify credentials in Kubernetes secret
kubectl get secret dagster-secret -n dagster -o yaml

# Check environment variables
kubectl exec -n dagster <pod-name> -- env | grep AWS

# Verify MinIO credentials match
# Should be: minioadmin/minioadmin (default)
```

### Partition Materialization Failing

1. **Check asset logs** in Dagster UI
2. **Verify field data exists**:
   ```bash
   # List fields in S3
   aws --endpoint-url=http://localhost:9000 s3 ls s3://hydrosat-pipeline-insights/raw_catalog/fields/processed/
   ```
3. **Check Sentinel-2 data availability**:
   - Verify date has available imagery
   - Check cloud cover threshold
   - Ensure required bands are available

### STAC API Not Responding

```bash
# Check if STAC API is running
ps aux | grep uvicorn

# Start STAC API
make stac-api-start

# Check STAC API logs
tail -f tmp/stac_api.log

# Test STAC API
curl http://localhost:8000/collections/field-indices/items?limit=5
```

### Clean Start

If you encounter persistent issues:

```bash
# Complete cleanup (⚠️ Removes all data!)
make clean-all

# Fresh setup
make setup
```

### Viewing Logs

```bash
# Dagster logs
kubectl logs -n dagster -l app=dagster --tail=100 -f

# MinIO logs
docker compose -f iac/docker/docker-compose.yml logs -f minio

# All Kubernetes resources
kubectl get all -n dagster
```

### Accessing MinIO via AWS CLI

You can also access MinIO using AWS CLI or boto3:

```bash
# Configure AWS CLI for MinIO
aws configure set aws_access_key_id minioadmin
aws configure set aws_secret_access_key minioadmin
aws configure set default.region us-east-1

# List buckets
aws --endpoint-url=http://localhost:9000 s3 ls

# List objects in bucket
aws --endpoint-url=http://localhost:9000 s3 ls s3://hydrosat-pipeline-insights/

# Copy file from MinIO
aws --endpoint-url=http://localhost:9000 s3 cp s3://hydrosat-pipeline-insights/path/to/file ./
```

## What Happens After Running?

After running the pipeline and materializing assets:

1. **Data Processing**:
   - Field geometries are loaded from S3
   - Sentinel-2 imagery is queried from Planetary Computer
   - Spectral indices (NDVI and NDMI) are computed
   - Results are saved as GeoParquet files

2. **STAC Catalog Updates**:
   - STAC items are created for each processed field/date/index combination
   - Catalog structure is maintained in S3
   - Metadata enables efficient querying

3. **Data Availability**:
   - Processed data accessible via S3/MinIO
   - STAC API provides query interface
   - Jupyter notebook enables analysis and visualization

4. **Monitoring**:
   - Dagster UI shows execution status
   - Asset materialization history
   - Partition status and run logs

## Next Steps

- **Query Data**: Use the STAC API to query processed field data
- **Analyze Results**: Open `field_analysis.ipynb` for visualization
- **Materialize More Partitions**: Use Dagster UI to process additional dates/fields
- **Monitor Health**: Check Dagster UI for pipeline status and asset health

---

For detailed API usage, see the STAC API documentation. For analysis examples, see `field_analysis.ipynb`.

