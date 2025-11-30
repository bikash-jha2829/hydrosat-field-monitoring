#!/usr/bin/env bash
# Initialize k3d cluster and build Dagster image

source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

check_software "k3d" "kubectl" "docker"

check_port_available "$DAGSTER_UI_PORT" "Dagster UI"

if k3d cluster list | grep -q "$K3D_CLUSTER_NAME"; then
    echo "Cluster '$K3D_CLUSTER_NAME' already exists."
    read -p "Delete existing cluster? (y/n): " answer
    if [[ "$answer" =~ ^[yY]$ ]]; then
        k3d cluster delete "$K3D_CLUSTER_NAME"
    else
        echo "Exiting."
        exit 0
    fi
fi

echo "Creating cluster '$K3D_CLUSTER_NAME'..."
k3d cluster create "$K3D_CLUSTER_NAME" \
    --agents 0 \
    --api-port 6443 \
    --port ${DAGSTER_UI_PORT}:80@loadbalancer \
    --k3s-arg "--disable=traefik@server:0"

sleep 5
kubectl wait --for=condition=Ready nodes --all --timeout=120s
build_and_import_dagster_image

echo "Cluster initialized"
echo "Dagster UI: http://localhost:$DAGSTER_UI_PORT"
