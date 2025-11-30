# 🚀 Quick Start Guide

## Complete Clean Start (Fresh Setup)

### Option 1: One Command (Recommended) ✅

```bash
# Complete cleanup + fresh setup
make clean-all && make setup
```

### Option 2: Step by Step

```bash
# 1. Complete cleanup
make clean-all

# 2. Fresh setup
make setup

# 3. Start development
make dev
```

---

## What Gets Removed in `clean-all`

```
✅ Terraform state files
   - terraform.tfstate
   - terraform.tfstate.backup
   - .terraform/ directory
   - .terraform.lock.hcl

✅ Kubernetes cluster
   - k3d cluster (local-hydrosat-cluster)

✅ Docker containers
   - MinIO container
   - All volumes

✅ Temporary files
   - tmp/ directory
```

---

## What Gets Created in `setup`

```
✅ MinIO (Docker)
   - Running on localhost:9000 (API)
   - Running on localhost:9001 (Console)

✅ k3d Cluster
   - Kubernetes cluster
   - Dagster deployed via Helm

✅ Terraform Resources
   - S3 bucket (MinIO)
   - K8s namespace
   - K8s services
   - ConfigMap & Secret

✅ Sample Data
   - Loaded into S3 bucket
```

---

## Access Points After Setup

| Service | URL | Credentials |
|---------|-----|-------------|
| **Dagster UI** | http://localhost:30080 | No auth |
| **MinIO Console** | http://localhost:9001 | minioadmin / minioadmin |
| **MinIO API** | http://localhost:9000 | S3 compatible |

---

## Troubleshooting

### Port Already in Use

```bash
# Check what's using port 30080
lsof -i :30080

# Use different port
echo "DAGSTER_UI_PORT=30081" >> .env
make clean-all
make setup
```

### OrbStack Not Running

```bash
# Start OrbStack (macOS)
open -a OrbStack

# Or use Docker Desktop
open -a Docker
```

### Terraform State Locked

```bash
# Force unlock (if needed)
cd iac/terraform
terraform force-unlock <LOCK_ID>
```

---

## Common Commands

```bash
# Full cleanup
make clean-all

# Fresh setup
make setup

# Start dev server
make dev

# Stop everything
make stop

# Update Dagster code
make k8s-update

# Load sample data
make s3-load
```

---

## Verification

After `make setup`, verify everything is running:

```bash
# Check Docker containers
docker ps

# Check k3d cluster
k3d cluster list

# Check K8s pods
kubectl get pods -n dagster

# Check services
kubectl get svc -n dagster

# Check Terraform state
cd iac/terraform && terraform show
```

---

## Complete Reset (Nuclear Option)

If something is really broken:

```bash
# 1. Complete cleanup
make clean-all

# 2. Remove Docker images (optional)
docker rmi dagster-app:latest minio/minio:RELEASE.2025-04-22T22-12-26Z

# 3. Clean Docker system (optional)
docker system prune -a

# 4. Fresh start
make setup
```

---

## Time Estimates

| Operation | Time |
|-----------|------|
| `clean-all` | ~30 seconds |
| `setup` | ~5-10 minutes |
| First run | ~10-15 minutes (builds images) |
| Subsequent runs | ~5 minutes (uses cached images) |

