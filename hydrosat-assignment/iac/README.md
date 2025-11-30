# Infrastructure as Code (IAC)

This directory contains all infrastructure automation for the Hydrosat Field Monitoring project.

> **🚀 No Configuration Needed!** Everything works with sensible defaults. Just run `make setup`.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Developer Machine                         │
│                                                               │
│  ┌────────────┐      ┌─────────────────────────────────┐    │
│  │   MinIO    │      │    k3d (K8s Cluster)            │    │
│  │ (Docker)   │◄─────┤                                  │    │
│  │ :9000/9001 │      │  ┌──────────────────────────┐   │    │
│  └────────────┘      │  │   Dagster (Helm)         │   │    │
│                      │  │   - Webserver :30080      │   │    │
│                      │  │   - User Deployment       │   │    │
│                      │  │                           │   │    │
│                      │  │   ConfigMap: dagster-env  │   │    │
│                      │  │   Secret: dagster-secret  │   │    │
│                      │  └──────────────────────────┘   │    │
│                      └─────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
iac/
├── docker/              # Docker & Docker Compose
│   ├── Dockerfile       # Multi-stage Dagster image
│   └── docker-compose.yml  # MinIO service
│
├── k8s/                 # Kubernetes manifests
│   ├── dagster-configmap.yaml  # Non-sensitive config
│   ├── dagster-secret.yaml     # Credentials
│   └── helm/
│       └── dagster/
│           └── values.yaml     # Helm chart customization
│
├── scripts/             # Shell scripts
│   ├── config.sh        # Shared configuration (with defaults)
│   ├── k8s-*.sh         # Cluster lifecycle management
│   └── s3-load.sh       # Sample data loader
│
└── terraform/           # Infrastructure as Code
    ├── providers.tf     # Provider configuration
    ├── versions.tf      # Provider versions
    ├── variables.tf     # Input variables (with defaults)
    ├── s3.tf            # MinIO S3 bucket
    ├── k8s_dagster.tf   # K8s resources
    └── Makefile         # Terraform wrapper
```

## Quick Start (No Setup Required!)

```bash
# Single command setup - fully idempotent
make setup

# Start development
make dev
```

**✨ Key Feature**: `make setup` is fully idempotent - you can run it multiple times safely. It automatically imports existing resources into Terraform state.

## 🧹 Complete Clean Start (Fresh Setup)

If you want to **completely remove everything** and start fresh:

```bash
# Step 1: Complete cleanup (removes ALL state, clusters, containers)
make clean-all

# Step 2: Fresh setup
make setup
```

**What `clean-all` removes:**
- ✅ All Terraform state files (`.tfstate`, `.tfstate.backup`)
- ✅ Terraform lock files (`.terraform.lock.hcl`)
- ✅ k3d cluster (entire Kubernetes cluster)
- ✅ Docker containers (MinIO)
- ✅ All temporary files (`tmp/`)

**What `clean-all` does NOT remove:**
- ❌ Your `.env` file (configuration preserved)
- ❌ Source code
- ❌ Docker images (cached for faster rebuild)

### Manual Clean Start (Step-by-Step)

If you prefer manual control:

```bash
# 1. Destroy Terraform resources
make tf-destroy

# 2. Remove Terraform state
rm -rf iac/terraform/.terraform
rm -rf iac/terraform/.terraform.lock.hcl
rm -f iac/terraform/terraform.tfstate*

# 3. Delete k3d cluster
k3d cluster delete local-hydrosat-cluster

# 4. Stop Docker containers
docker compose -f iac/docker/docker-compose.yml down -v

# 5. Remove temp files
rm -rf tmp/

# 6. Fresh setup
make setup
```

**Default Credentials (Development Only):**
- MinIO User: `minioadmin`
- MinIO Password: `minioadmin`
- S3 Endpoint: `http://localhost:9000`
- Dagster UI: `http://localhost:30080`

### Optional: Customize Configuration

All configuration is in **one single file**: `.env` at project root.

**✅ `.env` is already in the repo with working defaults!**

```bash
# Just edit if you need to customize (optional!)
vim .env
```

All tools automatically read from this single `.env`:
- ✅ Docker Compose
- ✅ Bash scripts
- ✅ Terraform
- ✅ Makefile

## Components

### 1. Docker (`docker/`)
- **MinIO**: S3-compatible object storage (replaces AWS S3 locally)
- **Dagster**: Data orchestration platform (built as Docker image)

### 2. Kubernetes (`k8s/`)
- **ConfigMap**: Non-sensitive environment variables
- **Secret**: Credentials (MinIO access keys)
- **Helm Values**: Dagster chart customization

### 3. Terraform (`terraform/`)
Manages:
- ✅ Kubernetes namespace
- ✅ MinIO S3 bucket creation
- ✅ ExternalName service (connects K8s to host MinIO)
- ✅ Helm release (Dagster deployment)

Does NOT manage:
- ❌ ConfigMap (for fast iteration)
- ❌ Secret (security best practice)

## Best Practices Applied

### ✅ Separation of Concerns
| Layer | Tool | Update Frequency |
|-------|------|------------------|
| Infrastructure | Terraform | Rare |
| Configuration | kubectl + YAML | Frequent |
| Secrets | K8s Secrets | On rotation |
| Application Code | Docker | On changes |

### ✅ Security
- Credentials in K8s Secrets (not ConfigMaps)
- Development credentials hardcoded for assignment simplicity
- Production: use Sealed Secrets or External Secrets Operator

### ✅ DRY (Don't Repeat Yourself)
- **Single `.env` file** for all configuration
- Shared `config.sh` for all scripts
- All tools read from same source
- No duplicate config across files

### ✅ Developer Experience
- **Zero config**: Works with defaults
- One command setup: `make setup`
- Fast config updates: `make k8s-config`
- Clear error messages
- Idempotent operations

## Common Operations

### Update Configuration
```bash
# Edit config
vim iac/k8s/dagster-configmap.yaml

# Apply (no Terraform needed!)
make k8s-config

# Restart pods to pick up changes
kubectl rollout restart deployment -n dagster
```

### Update Infrastructure
```bash
# Edit Terraform files
vim iac/terraform/k8s_dagster.tf

# Apply changes
make tf-apply
```

### Update Application Code
```bash
# Edit Python code
vim src/plantation_monitoring/assets.py

# Rebuild and deploy
make k8s-update
```

### Stop & Cleanup
```bash
# Stop all services (preserves data)
make stop

# Full cleanup (deletes everything)
make clean
```

## Configuration: Single Source of Truth ✅

**Everything uses ONE file**: `.env` in project root.

**✅ Already committed with working defaults - no setup needed!**

```
                    ┌─────────────┐
                    │   .env      │  ← Single source of truth
                    │ (committed) │  ← Ready to use!
                    └──────┬──────┘
                           │
         ┌─────────────────┼─────────────────┐
         │                 │                 │
    ┌────▼────┐      ┌────▼────┐      ┌────▼────┐
    │ Makefile│      │ Scripts │      │Terraform│
    │         │      │(config) │      │(tf-vars)│
    └─────────┘      └─────────┘      └─────────┘
         │                 │                 │
         └─────────────────┼─────────────────┘
                           │
                    All use same config!
```

### Customize (Optional)
```bash
# Edit if you want to change defaults
vim .env
```

### What reads from `.env`?
| Tool | How It Loads |
|------|-------------|
| **Makefile** | `-include .env` (Make native) |
| **Scripts** | `source .env` in `config.sh` |
| **Terraform** | Converted to `TF_VAR_*` by `tf-vars.sh` |
| **Docker Compose** | Env vars passed through Makefile |

### ❌ No More Multiple Files!
Before (confusing):
```
.env
.env.k8s          ← Deleted
.env.terraform    ← Never existed
env-template.txt  ← Deleted (redundant)
config.sh (hardcoded values)  ← Now reads from .env
```

After (simple):
```
.env  ← Already in repo! Everything reads this
```

**One file. Committed. Zero setup. Zero duplication. ✅**

## Access Points

| Service | URL | Credentials | Configurable |
|---------|-----|-------------|--------------|
| MinIO Console | http://localhost:9001 | minioadmin / minioadmin | ❌ |
| MinIO API | http://localhost:9000 | (S3 compatible) | ❌ |
| Dagster UI (K8s) | http://localhost:30080 | No auth | ✅ via `DAGSTER_UI_PORT` |
| Dagster Dev Server | http://localhost:3000 | No auth (local only) | ❌ |

### Service Exposure Strategy

**Dagster UI**: Exposed via `LoadBalancer` service type
- ✅ k3d's built-in servicelb handles LoadBalancer automatically
- ✅ Mapped: `localhost:30080` → `dagster-webserver:80` (customizable)
- ✅ Port 30080 chosen to avoid conflicts (K8s NodePort range)
- ✅ No random port assignment (unlike NodePort)
- ✅ Mirrors production cloud LoadBalancers
- ✅ Port conflict detection built-in

**MinIO**: Direct Docker port binding
- Port 9000: S3 API
- Port 9001: Web Console

### Customize Dagster UI Port

Default port is **30080** (chosen to avoid common conflicts).

If you prefer a different port:

```bash
# Option 1: Set in .env
echo "DAGSTER_UI_PORT=8080" >> .env

# Option 2: Set temporarily
export DAGSTER_UI_PORT=8080
make setup
```

The script will automatically:
- ✅ Detect port conflicts
- ✅ Warn you if port is in use
- ✅ Show options to resolve

## Troubleshooting

### Cluster won't start
```bash
# Check Docker is running
docker ps

# Recreate cluster
make clean
make setup
```

### ConfigMap not applied
```bash
# Manually apply
kubectl apply -f iac/k8s/dagster-configmap.yaml
kubectl apply -f iac/k8s/dagster-secret.yaml

# Verify
kubectl get configmap dagster-env -n dagster -o yaml
kubectl get secret dagster-secret -n dagster
```

### MinIO not accessible from K8s
```bash
# Check external service
kubectl get svc minio-external -n dagster -o yaml

# Test connectivity from a pod
kubectl run -it --rm debug --image=curlimages/curl --restart=Never -n dagster -- \
  curl -v http://minio-external:9000
```

### Ports already in use

**Dagster UI (port conflict - rare with 30080):**
```bash
# Check what's using the port
lsof -i :30080

# Option 1: Kill the process
lsof -ti:30080 | xargs kill

# Option 2: Use different port
echo "DAGSTER_UI_PORT=30081" >> .env
make clean
make setup
```

**MinIO (port 9000/9001 conflict):**
```bash
# Check what's using the ports
lsof -i :9000  # MinIO API
lsof -i :9001  # MinIO Console

# Kill conflicting processes
lsof -ti:9000 | xargs kill
lsof -ti:9001 | xargs kill

# Or change ports in docker-compose.yml
```

## Production Considerations

This setup is **optimized for local development**. For production:

1. **Secrets Management**: 
   - Replace hardcoded secrets with Sealed Secrets or External Secrets Operator
   - Use HashiCorp Vault or cloud provider secret managers

2. **Terraform Backend**: 
   - Use remote state (S3 + DynamoDB lock)
   - Enable state encryption

3. **K8s Configuration**:
   - Use production Kubernetes cluster (EKS, GKE, AKS)
   - Configure resource limits/requests
   - Add horizontal pod autoscaling

4. **Storage**:
   - Replace MinIO with AWS S3 or production MinIO cluster
   - Configure backup and replication

5. **Monitoring**:
   - Add Prometheus + Grafana
   - Configure alerts
   - Set up log aggregation (ELK/Loki)

6. **GitOps**:
   - Use ArgoCD or Flux for continuous delivery
   - Implement proper CI/CD pipelines

## File Count & Complexity

| Component | Files | Lines | Purpose |
|-----------|-------|-------|---------|
| Docker | 2 | ~100 | Container images |
| K8s | 3 | ~80 | Config & secrets |
| Scripts | 6 | ~180 | Automation (shared functions) |
| Terraform | **3** | ~180 | `main.tf` + `variables.tf` + `Makefile` |
| **Total** | **14** | **~540** | **Complete setup** |

**Simplifications**:
- Terraform: **All-in-one** `main.tf` (providers, resources, outputs)
- No wrapper scripts: Terraform reads `TF_VAR_*` from `.env` directly
- Scripts: Shared functions in `config.sh` reduce duplication
- Total: **Minimal files** for easy understanding

## How Setup Handles Idempotency

The `make setup` command is designed to be **fully idempotent** - safe to run multiple times:

1. **Namespace**: Creates if missing, skips if exists
2. **ConfigMap/Secret**: Updates if already present (via `kubectl apply`)
3. **Terraform Resources**: 
   - Imports existing namespace into state
   - Imports existing S3 bucket into state
   - Only creates what's missing

This means:
- ✅ No "resource already exists" errors
- ✅ No need for destructive cleanup between runs
- ✅ Preserves data and configuration
- ✅ Fast re-runs (skips what exists)

**Under the hood** (step 6 of setup):
```bash
# Import existing resources
terraform import kubernetes_namespace.dagster dagster
terraform import minio_s3_bucket.pipeline hydrosat-pipeline-insights

# Then apply (only creates missing resources)
terraform apply
```

## References

- [Dagster Helm Chart](https://github.com/dagster-io/dagster/tree/master/helm)
- [k3d Documentation](https://k3d.io/)
- [MinIO Documentation](https://min.io/docs/)
- [Terraform Kubernetes Provider](https://registry.terraform.io/providers/hashicorp/kubernetes/latest/docs)
