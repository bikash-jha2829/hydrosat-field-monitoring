# Hydrosat Field Monitoring - Infrastructure Makefile
# 🚀 No configuration needed! Works with sensible defaults out-of-the-box

PROJECT_ROOT := $(shell pwd)
DOCKER_COMPOSE_FILE := $(PROJECT_ROOT)/iac/docker/docker-compose.yml
TERRAFORM_DIR := $(PROJECT_ROOT)/iac/terraform
SCRIPTS_DIR := $(PROJECT_ROOT)/iac/scripts

# Load single .env file (optional - defaults work fine)
-include .env
export

# Defaults (overrideable by .env)
MINIO_ROOT_USER ?= minioadmin
MINIO_ROOT_PASSWORD ?= minioadmin
MINIO_DATA_DIR ?= $(PROJECT_ROOT)/tmp/minio_data
K3D_CLUSTER_NAME ?= local-hydrosat-cluster
K8S_DAGSTER_NAMESPACE ?= dagster
STAC_API_PORT ?= 8000
STAC_API_PID_FILE ?= $(PROJECT_ROOT)/tmp/stac_api.pid

DOCKER_COMPOSE := MINIO_ROOT_USER=$(MINIO_ROOT_USER) \
	MINIO_ROOT_PASSWORD=$(MINIO_ROOT_PASSWORD) \
	MINIO_DATA_DIR=$(MINIO_DATA_DIR) \
	docker compose -f $(DOCKER_COMPOSE_FILE)

.PHONY: help setup dev stop clean-all status
.PHONY: minio-start minio-stop minio-restart
.PHONY: k8s-update s3-load
.PHONY: stac-api-start stac-api-stop stac-api-restart

help:
	@echo "🌱 Hydrosat Field Monitoring"
	@echo ""
	@echo "🚀 Main Commands:"
	@echo "  make setup         Complete setup (5-10 min) - First time or after clean-all"
	@echo "  make dev           Start Dagster dev server (localhost:3000)"
	@echo "  make stop          Stop all services (keeps data)"
	@echo "  make clean-all     Complete cleanup ⚠️  Destructive! Use for fresh start"
	@echo ""
	@echo "🔧 Utility Commands:"
	@echo "  make status           Check status of all services"
	@echo "  make minio-start      Start MinIO only"
	@echo "  make minio-stop       Stop MinIO only"
	@echo "  make minio-restart    Restart MinIO (use if connection errors)"
	@echo "  make k8s-update       Update after code changes (2-3 min)"
	@echo "  make s3-load          Load sample data to S3/MinIO"
	@echo ""
	@echo "📚 Common Workflows:"
	@echo "  First time:        make setup && make dev"
	@echo "  After code change: make k8s-update"
	@echo "  End of day:        make stop"
	@echo "  Fresh start:       make clean-all && make setup"
	@echo ""
	@echo "🌐 Access (after setup):"
	@echo "  Dagster UI:    http://localhost:30080"
	@echo "  MinIO Console: http://localhost:9001 (minioadmin/minioadmin)"
	@echo "  STAC API:      http://localhost:8000 (docs: http://localhost:8000/docs)"
	@echo ""
	@echo "💡 Customize via .env file (DAGSTER_UI_PORT, credentials, etc.)"

# === MAIN TARGETS ===

setup:
	@echo "🚀 Starting full setup..."
	@echo "⚠️  Ensure Docker is running (OrbStack recommended for macOS)"
	@echo ""
	@echo "1️⃣  Starting MinIO..."
	@$(MAKE) minio-start
	@echo ""
	@echo "2️⃣  Creating k3d cluster and building Dagster image..."
	@$(SCRIPTS_DIR)/k8s-init.sh
	@echo ""
	@echo "3️⃣  Creating Kubernetes namespace..."
	@kubectl create namespace $(K8S_DAGSTER_NAMESPACE) 2>/dev/null || echo "  Namespace already exists"
	@echo "✅ Namespace ready"
	@echo ""
	@echo "4️⃣  Applying Kubernetes configs (ConfigMap & Secret)..."
	@kubectl apply -f $(PROJECT_ROOT)/iac/k8s/dagster-secret.yaml
	@kubectl apply -f $(PROJECT_ROOT)/iac/k8s/dagster-configmap.yaml
	@echo "✅ Kubernetes configs applied"
	@echo ""
	@echo "5️⃣  Initializing Terraform..."
	@$(MAKE) -C $(TERRAFORM_DIR) init
	@echo ""
	@echo "6️⃣  Importing existing resources into Terraform state..."
	@$(MAKE) -C $(TERRAFORM_DIR) import-namespace 2>/dev/null || echo "  📝 Namespace will be managed by Terraform"
	@$(MAKE) -C $(TERRAFORM_DIR) import-bucket 2>/dev/null || echo "  📝 S3 bucket will be created"
	@echo ""
	@echo "7️⃣  Loading sample data to S3 (before Dagster starts)..."
	@$(SCRIPTS_DIR)/s3-load.sh
	@echo ""
	@echo "8️⃣  Deploying infrastructure (this takes 2-5 minutes)..."
	@$(MAKE) -C $(TERRAFORM_DIR) apply
	@echo ""
	@echo "9️⃣  Waiting for Dagster pods to be ready..."
	@kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=dagster -n $(K8S_DAGSTER_NAMESPACE) --timeout=300s 2>/dev/null || \
		(echo "⚠️  Some pods still starting, continuing..."; sleep 10)
	@echo ""
	@echo "🔟  Syncing Python dependencies..."
	@uv sync
	@echo ""
	@echo "1️⃣1️⃣  Starting STAC API server..."
	@$(MAKE) stac-api-start
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "✅ Setup complete!"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "📊 Dagster Status:"
	@kubectl get pods -n $(K8S_DAGSTER_NAMESPACE)
	@echo ""
	@echo "🌐 Access Points:"
	@echo "   Dagster UI:    http://localhost:30080"
	@echo "   MinIO Console: http://localhost:9001 (minioadmin/minioadmin)"
	@echo "   STAC API:      http://localhost:$(STAC_API_PORT) (docs: http://localhost:$(STAC_API_PORT)/docs)"
	@echo ""
	@echo "💡 Next Steps:"
	@echo "   • Open Dagster UI in your browser: http://localhost:30080"
	@echo "   • Materialize assets from the Dagster UI"
	@echo "   • Query STAC catalog via API: http://localhost:$(STAC_API_PORT)/docs"
	@echo "   • For local dev (outside k8s): Run 'make dev'"

dev:
	dagster dev

stop:
	@echo "🛑 Stopping all services..."
	@-$(DOCKER_COMPOSE) stop 2>/dev/null || true
	@-$(MAKE) stac-api-stop 2>/dev/null || true
	@-k3d cluster stop $(K3D_CLUSTER_NAME) 2>/dev/null || true
	@echo "✅ All services stopped"

clean-all:
	@echo "🧹 COMPLETE CLEANUP - Removing everything..."
	@echo ""
	@echo "This will delete:"
	@echo "  - All Terraform state files"
	@echo "  - k3d cluster"
	@echo "  - Docker containers (MinIO)"
	@echo "  - MinIO data (all S3 buckets and objects)"
	@echo "  - STAC API server"
	@echo "  - All temporary files"
	@echo ""
	@read -p "⚠️  Are you sure? Type 'y' to continue: " -r && \
		if [ "$${REPLY}" == "y" ]; then \
			echo ""; \
			echo "1️⃣  Stopping STAC API server..."; \
			-$(MAKE) stac-api-stop 2>/dev/null || true; \
			echo ""; \
			echo "2️⃣  Destroying Terraform resources..."; \
			-$(MAKE) -C $(TERRAFORM_DIR) destroy 2>/dev/null || true; \
			echo ""; \
			echo "3️⃣  Removing Terraform state..."; \
			rm -rf $(TERRAFORM_DIR)/.terraform $(TERRAFORM_DIR)/.terraform.lock.hcl; \
			rm -f $(TERRAFORM_DIR)/terraform.tfstate*; \
			echo ""; \
			echo "4️⃣  Deleting k3d cluster..."; \
			k3d cluster delete $(K3D_CLUSTER_NAME) 2>/dev/null || true; \
			echo ""; \
			echo "5️⃣  Stopping Docker containers..."; \
			-$(DOCKER_COMPOSE) down -v 2>/dev/null || true; \
			echo ""; \
			echo "6️⃣  Removing MinIO data and temporary files..."; \
			rm -rf $(PROJECT_ROOT)/tmp/ 2>/dev/null || true; \
			echo ""; \
			echo "✅ Complete cleanup done! Run 'make setup' to recreate."; \
		else \
			echo "Cancelled."; \
		fi

# === MINIO ===

minio-start:
	@mkdir -p $(MINIO_DATA_DIR)
	@$(DOCKER_COMPOSE) up -d minio
	@echo "✅ MinIO running at http://localhost:9001"

minio-stop:
	@$(DOCKER_COMPOSE) stop minio
	@echo "✅ MinIO stopped"

minio-restart:
	@echo "🔄 Restarting MinIO..."
	@$(MAKE) minio-stop
	@$(MAKE) minio-start

# === KUBERNETES ===

k8s-update:
	@echo "🔄 Rebuilding and updating Dagster..."
	@$(SCRIPTS_DIR)/k8s-update.sh
	@echo "✅ Dagster updated! Changes will be live shortly."

s3-load:
	@echo "📦 Loading sample data to S3/MinIO..."
	@$(SCRIPTS_DIR)/s3-load.sh
	@echo "✅ Sample data loaded!"

# === STAC API ===

stac-api-start:
	@if [ -f $(STAC_API_PID_FILE) ] && kill -0 $$(cat $(STAC_API_PID_FILE)) 2>/dev/null; then \
		echo "  ℹ️  STAC API already running (PID: $$(cat $(STAC_API_PID_FILE)))"; \
	else \
		echo "  🚀 Starting STAC API server on port $(STAC_API_PORT)..."; \
		mkdir -p $(PROJECT_ROOT)/tmp; \
		cd $(PROJECT_ROOT) && \
		uv run python -m plantation_monitoring.api.run_stac_api > $(PROJECT_ROOT)/tmp/stac_api.log 2>&1 & \
		echo $$! > $(STAC_API_PID_FILE); \
		sleep 2; \
		if kill -0 $$(cat $(STAC_API_PID_FILE)) 2>/dev/null; then \
			echo "  ✅ STAC API started (PID: $$(cat $(STAC_API_PID_FILE)))"; \
			echo "  📖 API docs: http://localhost:$(STAC_API_PORT)/docs"; \
		else \
			echo "  ❌ Failed to start STAC API. Check logs: $(PROJECT_ROOT)/tmp/stac_api.log"; \
			rm -f $(STAC_API_PID_FILE); \
			exit 1; \
		fi; \
	fi

stac-api-stop:
	@if [ -f $(STAC_API_PID_FILE) ]; then \
		PID=$$(cat $(STAC_API_PID_FILE)); \
		if kill -0 $$PID 2>/dev/null; then \
			echo "  🛑 Stopping STAC API server (PID: $$PID)..."; \
			kill $$PID 2>/dev/null || true; \
			rm -f $(STAC_API_PID_FILE); \
			echo "  ✅ STAC API stopped"; \
		else \
			echo "  ℹ️  STAC API not running"; \
			rm -f $(STAC_API_PID_FILE); \
		fi; \
	else \
		echo "  ℹ️  STAC API not running"; \
	fi

stac-api-restart:
	@$(MAKE) stac-api-stop
	@sleep 1
	@$(MAKE) stac-api-start

# === STATUS CHECK ===

status:
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo "📊 Infrastructure Status"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@echo ""
	@echo "🐳 Docker (MinIO):"
	@docker ps --filter "name=minio" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null || echo "  ❌ Docker not running"
	@echo ""
	@echo "☸️  Kubernetes Cluster:"
	@k3d cluster list 2>/dev/null || echo "  ❌ k3d not running"
	@echo ""
	@echo "📦 Dagster Pods:"
	@kubectl get pods -n $(K8S_DAGSTER_NAMESPACE) 2>/dev/null || echo "  ❌ Cluster not running"
	@echo ""
	@echo "🌐 Services:"
	@kubectl get svc -n $(K8S_DAGSTER_NAMESPACE) 2>/dev/null || echo "  ❌ No services found"
	@echo ""
	@echo "🌐 STAC API:"
	@if [ -f $(STAC_API_PID_FILE) ] && kill -0 $$(cat $(STAC_API_PID_FILE)) 2>/dev/null; then \
		echo "  ✅ Running (PID: $$(cat $(STAC_API_PID_FILE)))"; \
	else \
		echo "  ❌ Not running"; \
	fi
	@echo ""
	@echo "🔗 Access Points:"
	@echo "   Dagster UI:    http://localhost:30080"
	@echo "   MinIO Console: http://localhost:9001"
	@echo "   STAC API:      http://localhost:$(STAC_API_PORT) (docs: http://localhost:$(STAC_API_PORT)/docs)"
	@echo ""
	@echo "🧪 Connectivity Test:"
	@curl -s -o /dev/null -w "   Dagster UI: HTTP %{http_code}\n" http://localhost:30080 2>/dev/null || echo "   Dagster UI: ❌ Not accessible"
	@curl -s -o /dev/null -w "   MinIO:      HTTP %{http_code}\n" http://localhost:9001 2>/dev/null || echo "   MinIO:      ❌ Not accessible"
	@curl -s -o /dev/null -w "   STAC API:   HTTP %{http_code}\n" http://localhost:$(STAC_API_PORT) 2>/dev/null || echo "   STAC API:   ❌ Not accessible"
	@echo ""
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
