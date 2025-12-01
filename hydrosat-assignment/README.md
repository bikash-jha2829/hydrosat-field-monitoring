# 🛰️ Hydrosat Field Monitoring Pipeline

**Processing Sentinel-2 satellite imagery to compute spectral indices (NDVI & NDMI) for plantation fields and publish results to a STAC catalog.**

This pipeline uses **Dagster** for orchestration, **Kubernetes (k3d)** for deployment, and **MinIO** for S3-compatible storage.

---

## ⚡ Quick Start

Got everything installed? Launch in 30 seconds:

```bash
# 1. Clone & Install dependencies
git clone <repository-url>
cd hydrosat-assignment
uv sync --all-groups

# 2. Launch everything (MinIO, K8s, Dagster, STAC API)
echo "y" | make setup

# 3. Open Mission Control
# Navigate to http://localhost:30080 in your browser
```

> **Note:** First-time setup takes **5-10 minutes**. Subsequent runs are faster.

---

## 🧰 Prerequisites

**Required Tools:**
- 🐍 **Python 3.11+**
- 🐳 **Docker** (OrbStack or Docker Desktop)
- ☸️ **k3d** & **kubectl**
- 🏗️ **Terraform**
- 📦 **uv** (auto-installed if missing)

<details>
<summary><strong>🔻 Installation Guides (click if missing tools)</strong></summary>

### Python 3.11+

```bash
python3.11 --version
```

### Docker

**macOS (OrbStack recommended):**
```bash
brew install --cask orbstack
docker --version
```

**Linux:**
```bash
sudo apt-get update
sudo apt-get install docker.io docker-compose
```

### k3d

```bash
# macOS
brew install k3d

# Linux
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
```

### kubectl

**Required even when using k3d** - k3d creates the cluster, but you'll use kubectl to interact with it.

```bash
# macOS
brew install kubectl

# Linux
curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl"
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
```

### Terraform

**Reference:** [Official Installation Guide](https://developer.hashicorp.com/terraform/tutorials/aws-get-started/install-cli)

```bash
# macOS
brew tap hashicorp/tap
brew install hashicorp/tap/terraform

# Linux
wget -O- https://apt.releases.hashicorp.com/gpg | sudo gpg --dearmor -o /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt update && sudo apt install terraform
```

### uv (Python Package Manager)

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# Or: pip install uv
```

</details>

---

## 🚀 Setup & Launch

### 1. Install Dependencies

```bash
git clone <repository-url>
cd hydrosat-assignment
uv sync --all-groups
```

### 2. Configure Environment (Optional)

The `.env` file configures Kubernetes, MinIO, S3, and Dagster settings. Default values in `Makefile` work out-of-the-box, so creating `.env` is **optional**.

**Location:** Create `.env` in project root (same directory as `Makefile`) if you want to customize.

### 3. Launch Infrastructure

```bash
# Interactive mode
make setup

# Non-interactive (auto-confirm)
echo "y" | make setup
```

**What `make setup` does:**
This command performs a comprehensive setup that includes:

1. **Start MinIO** (S3-compatible storage)
   - Launches MinIO Docker container
   - Accessible at http://localhost:9000 (API) and http://localhost:9001 (Console)
   - **Username**: `minioadmin`
   - **Password**: `minioadmin`

2. **Create k3d Kubernetes Cluster**
   - Initializes a local Kubernetes cluster using k3d
   - Configures port forwarding for Dagster UI (port 30080)

3. **Build Dagster Docker Image**
   - Builds custom Dagster image with project code
   - Imports image into k3d cluster

4. **Create Kubernetes Namespace**
   - Creates `dagster` namespace for organizing resources

5. **Apply Kubernetes Configurations**
   - Applies ConfigMap (environment variables)
   - Applies Secret (credentials and sensitive data)

6. **Initialize Terraform**
   - Downloads required Terraform providers (Kubernetes, Helm, MinIO)
   - Prepares Terraform state

7. **Import Existing Resources**
   - Imports existing Kubernetes namespace into Terraform state
   - Imports existing S3 bucket (if present) into Terraform state

8. **Load Sample Data to S3**
   - Uploads field geometries (GeoJSON files) to S3
   - Uploads bounding box data to S3
   - Data is loaded to `raw_catalog/fields/` and `raw_catalog/bbox/` prefixes
   - **Note**: This happens before Terraform creates the bucket, but the bucket will be created by Terraform if it doesn't exist

9. **Deploy Infrastructure with Terraform**
   - **Creates S3 bucket** (`hydrosat-pipeline-insights`) in MinIO
   - Creates Kubernetes namespace (managed by Terraform)
   - Creates MinIO ExternalName service (routes Kubernetes to host MinIO)
   - **Deploys Dagster via Helm chart** (includes webserver, daemon, and worker pods)
   - Configures all Kubernetes resources

10. **Wait for Dagster Pods**
   - Waits up to 5 minutes for all Dagster pods to be ready
   - Ensures services are operational before proceeding
   - **Dagster UI**: http://localhost:30080 (available once pods are ready)

11. **Sync Python Dependencies**
    - Installs/updates Python packages using `uv sync`

12. **Start STAC API Server**
    - Launches FastAPI server for querying STAC catalog
    - Accessible at http://localhost:8000
    - API documentation at http://localhost:8000/docs

**Note:** First-time setup takes 5-10 minutes. Subsequent runs are faster as resources are reused.

### 4. Verify Deployment

```bash
make status
```

### 5. Access Services

| Service | URL | Credentials |
|---------|-----|-------------|
| **Dagster UI** | http://localhost:30080 | N/A |
| **MinIO Console** | http://localhost:9001 | `minioadmin` / `minioadmin` |
| **MinIO API** | http://localhost:9000 | `minioadmin` / `minioadmin` |
| **STAC API** | http://localhost:8000 | N/A |
| **STAC API Docs** | http://localhost:8000/docs | N/A |

**Note:** Dagster UI port is configured in `iac/scripts/config.sh` (default: `30080`). Override via `DAGSTER_UI_PORT` in `.env`.

---

## 🕹️ Operations Guide

### The Data Workflow (Medallion Architecture)



Data flows through three stages:

1. **Raw → Staging:** Upload GeoJSON files to S3
2. **Staging → Processed:** `bbox` and `fields` assets **automatically** materialize when new files are detected
3. **Processed → Insights:** **Manually** trigger `field_ndvi` and `field_ndmi` computation

### Computing Spectral Indices (NDVI/NDMI)

1. **Open Dagster UI**:
   - Kubernetes: http://localhost:30080
   - Dev Mode: http://localhost:3000

2. **Check Valid Dates**: Refer to `valid_sentinel_partitions.txt` for dates where Sentinel-2 has coverage for your AOI (Area of Interest)

3. **Select Partitions**: Choose date/field combinations:
   - Single: `2025-10-11|all` (one date, all field)
   - Multiple dates: Select multiple date/field combinations

4. **Materialize**: Click "Materialize" on `field_ndvi` and `field_ndmi` assets

**What Happens After Materialization:**

- ✅ Processed outputs are written to S3: `pipeline-outputs/{date}/{field_id}/ndvi.parquet` and `ndmi.parquet`
- ✅ STAC catalog is updated on S3: `catalog/` directory with new items
- ✅ Materialized assets appear in the catalog and can be queried via STAC API

**Success!** 🎉
- ✅ Results written to S3: `pipeline-outputs/{date}/{field_id}/ndvi.parquet` and `ndmi.parquet`
- ✅ STAC catalog updated: `catalog/` directory with new items
- ✅ Queryable via STAC API: `/collections/field-indices/items`

**Verify:**
- Dagster UI shows "Materialized" status
- Files appear in S3 `pipeline-outputs/` directory
- New items in STAC API

### Auto-Materialization

The pipeline includes **automatic materialization** for certain assets:

**Auto-Materialized Assets:**
- ✅ **`bbox` asset**: Automatically materializes when new bounding box data is uploaded to `raw_catalog/bbox/staging/`
- ✅ **`fields` asset**: Automatically materializes when new field geometry data is uploaded to `raw_catalog/fields/staging/`

**How It Works:**
1. New GeoJSON files are uploaded to S3 `staging/` directories
2. Sensors detect the new files
3. `bbox` and `fields` assets automatically materialize
4. Data is validated and moved from `staging/` → `processed/`
5. Once fields are processed, you can manually trigger `field_ndvi` and `field_ndmi` materialization

**Manual Materialization Required:**
- ⚙️ **`field_ndvi` asset**: Must be manually triggered via Dagster UI
- ⚙️ **`field_ndmi` asset**: Must be manually triggered via Dagster UI

**Note**: NDVI and NDMI require manual selection of partitions (dates/fields) because they depend on:
- Sentinel-2 satellite data availability
- Cloud cover conditions
- User's specific analysis needs

### Adding New Data

Need to analyze new fields?

1. **Place GeoJSON files**:
   ```bash
   # Bounding boxes
   sample_data/s3/raw_catalog/bbox/staging/bbox.geojson
   
   # Field geometries (name: fields-*.geojson)
   sample_data/s3/raw_catalog/fields/staging/fields-*.geojson
   ```

2. **Load to S3**:
   ```bash
   make s3-load
   ```

3. **Watch sensors** automatically pick up files and materialize `bbox` and `fields` assets!

---

## 📂 Output Structure

All data in `hydrosat-pipeline-insights` S3 bucket:

### 1. Raw Catalog (`raw_catalog/`)

Input data:
- **`bbox/`**: Bounding box geometries
  - `staging/`: Newly uploaded files
  - `processed/`: Validated files
- **`fields/`**: Field geometries
  - `staging/`: Newly uploaded files
  - `processed/`: Validated files

### 2. Pipeline Outputs (`pipeline-outputs/`)

Processed spectral indices:

```
pipeline-outputs/
├── 2025-10-11/
│   ├── field_1/
│   │   ├── ndvi.parquet    # GeoJSON + Stats + Metadata
│   │   └── ndmi.parquet
│   └── field_2/
│       ├── ndvi.parquet
│       └── ndmi.parquet
└── ...
```

Each Parquet file contains:
- Field geometry (GeoJSON)
- Spectral index statistics (mean, min, max, std)
- Valid pixel counts
- Field metadata (field_id, plant_type, plant_date)

### 3. STAC Catalog (`catalog/`)

Standardized catalog structure:

```
catalog/
├── catalog.json
├── collection.json
└── items/
    ├── field_1_2025-10-11_ndvi.json
    ├── field_1_2025-10-11_ndmi.json
    └── ...
```

Each STAC item includes:
- Metadata (field_id, plant_type, datetime)
- Spectral index values (ndvi_mean, ndmi_mean, etc.)
- Links to data assets (S3 paths)
- Geometry and bounding box

---

## 👩‍💻 Developer Notes

### Project Structure

```
hydrosat-assignment/
├── src/plantation_monitoring/   # Assets, sensors, logic
├── iac/                         # K8s, Terraform, scripts
├── tests/                        # Unit tests
├── field_analysis.ipynb          # Analysis notebook
└── Makefile                      # Command center
```

### Development Mode

Run Dagster locally (no Kubernetes overhead):

```bash
make dev
# Runs on http://localhost:3000
```

### Key Commands

```bash
make status          # Check all services
make k8s-update      # Apply code changes to cluster
make minio-restart   # Fix storage connection issues
make s3-load         # Load new data to S3
make stac-api-start  # Start STAC API server
make stop            # Pause services (keeps data)
make clean-all       # ⚠️ Nuke everything (destructive!)
```

### Code Changes Workflow

1. Make changes in `src/plantation_monitoring/`
2. Update deployment: `make k8s-update`
3. Verify in Dagster UI

### Testing & Linting

```bash
# Run tests
pytest tests/

# Linting
# Uses ruff for formatting/linting, mypy for type checking
```

### Kubernetes Commands

**List Pods:**
```bash
kubectl get pods -n dagster
kubectl get pods -n dagster -o wide
kubectl get pods -n dagster -w  # Watch
```

**View Logs:**
```bash
kubectl logs -n dagster <POD_NAME>
kubectl logs -n dagster <POD_NAME> -f  # Follow
kubectl logs -n dagster -l app.kubernetes.io/name=dagster
```

**Common Pod Names:**
- `dagster-webserver-*`: UI server
- `dagster-daemon-*`: Daemon process
- `dagster-worker-*`: Worker pods

---

## 🔧 Troubleshooting

### MinIO Connection Issues

```bash
make minio-restart
```

### Dagster Pods Not Starting

```bash
kubectl get pods -n dagster
kubectl logs -n dagster -l app=dagster --tail=50 -f
kubectl describe pod -n dagster <pod-name>
```

### S3 Access Errors

Verify credentials match MinIO defaults (`minioadmin`/`minioadmin`).

### Partition Materialization Failing

1. Check asset logs in Dagster UI
2. Verify field data exists in S3 `raw_catalog/fields/processed/`
3. Check Sentinel-2 data availability for selected date
4. Verify cloud cover threshold (default: 30%)

### STAC API Not Responding

```bash
make stac-api-start
tail -f tmp/stac_api.log
curl http://localhost:8000/collections/field-indices/items?limit=5
```

### Clean Start

```bash
make clean-all  # ⚠️ Removes all data!
make setup      # Fresh start
```

### Accessing MinIO via AWS CLI

```bash
aws configure set aws_access_key_id minioadmin
aws configure set aws_secret_access_key minioadmin
aws configure set default.region us-east-1

# List buckets
aws --endpoint-url=http://localhost:9000 s3 ls

# List objects
aws --endpoint-url=http://localhost:9000 s3 ls s3://hydrosat-pipeline-insights/
```

---

## 🔮 Next Steps

1. **Query Data**: Use STAC API to query processed field data
2. **Visualize**: Open `field_analysis.ipynb` for charts and analysis
3. **Scale**: Add more fields and watch Dagster process them
4. **Monitor**: Check Dagster UI for pipeline status and asset health

---

For detailed API usage, see STAC API docs at http://localhost:8000/docs. For analysis examples, see `field_analysis.ipynb`.
