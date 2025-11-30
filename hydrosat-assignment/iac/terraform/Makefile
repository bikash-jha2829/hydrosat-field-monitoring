TERRAFORM ?= terraform

# Load .env from project root (TF_VAR_* variables auto-loaded)
-include ../../.env
export

.PHONY: fmt init init-fresh plan apply destroy import-namespace import-bucket

fmt:
	$(TERRAFORM) fmt -recursive

init:
	rm -rf .terraform
	$(TERRAFORM) init

init-fresh:
	@echo "Removing Terraform state (keeping lock file)..."
	rm -rf .terraform terraform.tfstate* || true
	$(TERRAFORM) init

plan:
	$(TERRAFORM) plan

apply:
	$(TERRAFORM) apply -auto-approve

destroy:
	@echo "About to destroy local environment"
	@read -p "Type 'yes' to confirm: " -r && [ "$${REPLY}" == "yes" ] && \
		$(TERRAFORM) destroy -auto-approve

# Import existing resources (idempotent)
import-namespace:
	@$(TERRAFORM) import kubernetes_namespace.dagster dagster && echo "  Imported namespace" || true

import-bucket:
	@$(TERRAFORM) import minio_s3_bucket.pipeline hydrosat-pipeline-insights && echo "  Imported S3 bucket" || true
