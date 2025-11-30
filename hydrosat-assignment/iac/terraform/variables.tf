# Terraform Variables (loaded from .env via TF_VAR_* prefix)

variable "minio_server" {
  description = "MinIO server endpoint"
  type        = string
  default     = "localhost:9000"
}

variable "minio_user" {
  description = "MinIO root user"
  type        = string
  default     = "minioadmin"
}

variable "minio_password" {
  description = "MinIO root password"
  type        = string
  sensitive   = true
  default     = "minioadmin"
}

variable "minio_region" {
  description = "MinIO region"
  type        = string
  default     = "eu-west-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "local"
}

variable "creator" {
  description = "Creator/owner tag"
  type        = string
  default     = "local-dev"
}
