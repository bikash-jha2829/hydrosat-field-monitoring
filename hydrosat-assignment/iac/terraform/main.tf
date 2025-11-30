terraform {
  required_version = ">= 1.5.0"
  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.17"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.36"
    }
    minio = {
      source  = "aminueza/minio"
      version = "~> 3.3"
    }
  }
}

# Providers
provider "minio" {
  minio_server   = var.minio_server
  minio_user     = var.minio_user
  minio_password = var.minio_password
  minio_region   = var.minio_region
  minio_ssl      = false
}

provider "kubernetes" {
  config_path    = "~/.kube/config"
  config_context = "k3d-local-hydrosat-cluster"
}

provider "helm" {
  kubernetes {
    config_path    = "~/.kube/config"
    config_context = "k3d-local-hydrosat-cluster"
  }
}

# Configuration
locals {
  bucket_name = "hydrosat-pipeline-insights"
  namespace   = "dagster"
}

# MinIO S3 Bucket
resource "minio_s3_bucket" "pipeline" {
  bucket         = local.bucket_name
  acl            = "public"
  object_locking = false
}

# Kubernetes Namespace
resource "kubernetes_namespace" "dagster" {
  metadata {
    name = local.namespace
  }
}

# MinIO ExternalName Service (routes to host MinIO via k3d)
resource "kubernetes_service" "minio_external" {
  metadata {
    name      = "minio-external"
    namespace = kubernetes_namespace.dagster.metadata[0].name
  }

  spec {
    type          = "ExternalName"
    external_name = "host.k3d.internal"

    port {
      port        = 9000
      target_port = 9000
    }
  }
}

# Helm: Deploy Dagster
resource "helm_release" "dagster" {
  name       = "dagster"
  repository = "https://dagster-io.github.io/helm"
  chart      = "dagster"
  namespace  = kubernetes_namespace.dagster.metadata[0].name

  timeout       = 600
  wait          = true
  wait_for_jobs = true

  values = [
    file("${path.module}/../k8s/helm/dagster/values.yaml")
  ]

  depends_on = [kubernetes_service.minio_external]
}

# Outputs
output "bucket_name" {
  description = "MinIO S3 bucket name"
  value       = minio_s3_bucket.pipeline.bucket
}

output "bucket_arn" {
  description = "MinIO S3 bucket ARN"
  value       = minio_s3_bucket.pipeline.arn
}

output "dagster_namespace" {
  description = "Kubernetes namespace for Dagster"
  value       = kubernetes_namespace.dagster.metadata[0].name
}

