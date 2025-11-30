#!/usr/bin/env bash
# Start an existing k3d cluster

source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

check_software "k3d" "kubectl"

k3d cluster start "$K3D_CLUSTER_NAME" --wait
sleep 5
kubectl wait --for=condition=Ready nodes --all --timeout=120s
echo "Cluster started"
