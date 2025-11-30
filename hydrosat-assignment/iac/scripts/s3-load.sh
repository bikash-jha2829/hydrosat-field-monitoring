#!/usr/bin/env bash
# Load sample data to MinIO S3 bucket

source "$(dirname "${BASH_SOURCE[0]}")/config.sh"

DATA_DIR="${PROJECT_ROOT_DIR}/sample_data/s3"
DATETIME=$(date +"%Y-%m-%d-%H:%M:%S")
S3_PREFIX="s3://${AWS_S3_PIPELINE_BUCKET_NAME:-hydrosat-pipeline-insights}"

export AWS_ACCESS_KEY_ID="${MINIO_ROOT_USER}"
export AWS_SECRET_ACCESS_KEY="${MINIO_ROOT_PASSWORD}"
export AWS_REGION="${MINIO_REGION}"

AWS_OPTS=(
    --endpoint-url "${AWS_S3_ENDPOINT:-http://localhost:9000}"
)

echo "Loading sample data to S3..."

for prefix in "raw_catalog/fields/" "raw_catalog/bbox/"; do
    aws "${AWS_OPTS[@]}" s3 rm "${S3_PREFIX}/${prefix}" --recursive 2>/dev/null || true
done

TEMP_DIR=$(mktemp -d)
trap "rm -rf ${TEMP_DIR}" EXIT

BBOX_SOURCE="${DATA_DIR}/raw_catalog/bbox/staging/bbox.geojson"
if [ -f "${BBOX_SOURCE}" ]; then
    BBOX_DEST="${TEMP_DIR}/raw_catalog/bbox/staging/bbox-${DATETIME}.geojson"
    mkdir -p "$(dirname "${BBOX_DEST}")"
    cp "${BBOX_SOURCE}" "${BBOX_DEST}"
fi

FIELDS_SOURCE=$(find "${DATA_DIR}/raw_catalog/fields/staging" -name "fields-*.geojson" 2>/dev/null | head -1)
if [ -n "${FIELDS_SOURCE}" ]; then
    FIELDS_DEST="${TEMP_DIR}/raw_catalog/fields/staging/$(basename "${FIELDS_SOURCE}" .geojson)-${DATETIME}.geojson"
    mkdir -p "$(dirname "${FIELDS_DEST}")"
    cp "${FIELDS_SOURCE}" "${FIELDS_DEST}"
fi

echo "Uploading to S3..."
aws "${AWS_OPTS[@]}" s3 sync "${TEMP_DIR}/" "${S3_PREFIX}/" --quiet

echo "Sample data loaded"
