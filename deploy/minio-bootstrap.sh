#!/usr/bin/env bash
# Curry Takeaway Ordering System — one-time MinIO bootstrap on Clawsrv (D-28)
#
# Creates the two buckets the schema/spec expect (§7.13), a service account
# scoped to them (never use the root key in the app), and the public-read
# policy on the media bucket only. Run once after `docker compose up -d`,
# using the `mc` client against the root credentials, then rotate
# MINIO_ROOT_PASSWORD and switch the app's S3_ACCESS_KEY/S3_SECRET_KEY to
# the generated service-account keys.
set -euo pipefail

ALIAS="curry-local"
ENDPOINT="${S3_ENDPOINT:-http://127.0.0.1:${MINIO_API_BIND_PORT:-8103}}"
BUCKET_PROOFS="${S3_BUCKET_PROOFS:-curry-proofs}"
BUCKET_PUBLIC="${S3_BUCKET_PUBLIC:-curry-media}"

: "${MINIO_ROOT_USER:?set MINIO_ROOT_USER}"
: "${MINIO_ROOT_PASSWORD:?set MINIO_ROOT_PASSWORD}"

mc alias set "$ALIAS" "$ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"

mc mb --ignore-existing "$ALIAS/$BUCKET_PROOFS"
mc mb --ignore-existing "$ALIAS/$BUCKET_PUBLIC"

# Proofs stay private (default). Dish images are public-read only.
mc anonymous set download "$ALIAS/$BUCKET_PUBLIC"

# Service account scoped for the app — do not put root credentials in .env.
echo "Creating app service account (record the printed AccessKey/SecretKey" \
     "as S3_ACCESS_KEY / S3_SECRET_KEY in .env, then rotate MINIO_ROOT_PASSWORD):"
mc admin user svcacct add "$ALIAS" "$MINIO_ROOT_USER"
