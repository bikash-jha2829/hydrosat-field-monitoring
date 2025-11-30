#!/usr/bin/env bash
# Rebuild Dagster image and update deployment

source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

check_software "k3d" "docker" "kubectl"

kubectl config use-context "$K8S_CLUSTER_NAME"
build_and_import_dagster_image

echo "Restarting Dagster deployment..."
kubectl rollout restart deployment -n "$K8S_DAGSTER_NAMESPACE" -l app.kubernetes.io/name=dagster 2>/dev/null || true

echo "Dagster image updated"
