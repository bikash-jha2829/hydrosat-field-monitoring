#!/usr/bin/env bash
# Stop the k3d cluster

source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

check_software "k3d"

k3d cluster stop "$K3D_CLUSTER_NAME"
echo "Cluster stopped"
