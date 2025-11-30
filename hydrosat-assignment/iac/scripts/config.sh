#!/usr/bin/env bash
# Shared configuration for k8s scripts (loads from .env in project root)

set -eu

SCRIPT_ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export SCRIPT_ROOT_DIR
export PROJECT_ROOT_DIR="$(realpath "${SCRIPT_ROOT_DIR}/../..")"
export DOCKER_COMPOSE_FILE="${SCRIPT_ROOT_DIR}/../docker/docker-compose.yml"

ENV_FILE="${PROJECT_ROOT_DIR}/.env"
if [ -f "$ENV_FILE" ]; then
    set -a
    source "$ENV_FILE"
    set +a
fi

export K3D_CLUSTER_NAME="${K3D_CLUSTER_NAME:-local-hydrosat-cluster}"
export K8S_CLUSTER_NAME="k3d-${K3D_CLUSTER_NAME}"
export K8S_DAGSTER_NAMESPACE="${K8S_DAGSTER_NAMESPACE:-dagster}"

# Using 30080 (K8s NodePort range) to avoid conflicts with common apps on 8080
export DAGSTER_UI_PORT="${DAGSTER_UI_PORT:-30080}"

export MINIO_ROOT_USER="${MINIO_ROOT_USER:-minioadmin}"
export MINIO_ROOT_PASSWORD="${MINIO_ROOT_PASSWORD:-minioadmin}"
export MINIO_SERVER="${MINIO_SERVER:-localhost:9000}"
export MINIO_REGION="${MINIO_REGION:-eu-west-1}"

check_software() {
    local programs=("$@")
    for program in "${programs[@]}"; do
        if ! command -v "$program" &> /dev/null; then
            echo "Error: $program is not installed. Please install it and try again."
            exit 1
        fi
    done
}

check_port_available() {
    local port=$1
    
    if lsof -Pi :$port -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "Warning: Port $port is already in use!"
        echo "Options: Stop the service or set DAGSTER_UI_PORT in .env"
        read -p "Continue anyway? (y/n): " answer
        [[ "$answer" =~ ^[yY]$ ]] || exit 1
    fi
}

build_and_import_dagster_image() {
    echo "Building Dagster image..."
    MINIO_DATA_DIR="${PROJECT_ROOT_DIR}/tmp/minio_data" \
        docker compose -f "${DOCKER_COMPOSE_FILE}" build dagster
    
    echo "Importing image to k3d cluster..."
    k3d image import dagster-app:latest -c "$K3D_CLUSTER_NAME"
    echo "Dagster image ready"
}
