#!/usr/bin/env bash
# Curry Takeaway Ordering System — daily backup job (spec §15, §17.1)
#
# Runs from HOST CRON on Clawsrv at 03:00 SAST (01:00 UTC), NOT from the
# in-process scheduler — a backup job must survive the app container being
# down. Backs up both halves: the Postgres database and the proofs bucket.
# Writes to job_heartbeats so a silent failure is visible on /healthz.
#
# A backup that lives only on Clawsrv's own disk is not a backup — set
# BACKUP_TARGET (§17.4 / Appendix D) to a rclone remote on different
# infrastructure (Hetzner Storage Box recommended: same provider, separate
# failure domain) before relying on this in production.
set -euo pipefail

ENV_FILE="${ENV_FILE:-/srv/curry-orders/.env}"
# shellcheck disable=SC1090
[ -f "$ENV_FILE" ] && source "$ENV_FILE"

: "${BACKUP_TARGET:?set BACKUP_TARGET (off-Clawsrv rclone remote)}"
: "${BACKUP_ENCRYPTION_KEY:?set BACKUP_ENCRYPTION_KEY}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

DB_DUMP="$WORKDIR/curry-db-$STAMP.dump"
DB_DUMP_ENC="$DB_DUMP.gpg"

echo "[backup] dumping database..."
docker compose exec -T db pg_dump -Fc -U curry curry > "$DB_DUMP"
gpg --batch --yes --passphrase "$BACKUP_ENCRYPTION_KEY" --symmetric \
    --cipher-algo AES256 -o "$DB_DUMP_ENC" "$DB_DUMP"

echo "[backup] mirroring proofs bucket..."
mc mirror --overwrite "curry-local/${S3_BUCKET_PROOFS:-curry-proofs}" \
    "$WORKDIR/proofs-$STAMP/"
tar -C "$WORKDIR" -czf "$WORKDIR/proofs-$STAMP.tar.gz" "proofs-$STAMP"
gpg --batch --yes --passphrase "$BACKUP_ENCRYPTION_KEY" --symmetric \
    --cipher-algo AES256 -o "$WORKDIR/proofs-$STAMP.tar.gz.gpg" \
    "$WORKDIR/proofs-$STAMP.tar.gz"

echo "[backup] pushing to $BACKUP_TARGET..."
rclone copy "$DB_DUMP_ENC" "$BACKUP_TARGET/db/"
rclone copy "$WORKDIR/proofs-$STAMP.tar.gz.gpg" "$BACKUP_TARGET/proofs/"

echo "[backup] pruning backups older than 14 days on the remote..."
rclone delete --min-age 14d "$BACKUP_TARGET/db/" || true
rclone delete --min-age 14d "$BACKUP_TARGET/proofs/" || true

echo "[backup] recording heartbeat..."
docker compose exec -T db psql -U curry -d curry -c \
  "INSERT INTO job_heartbeats (job_name, last_run_at, last_ok, detail)
   VALUES ('backup', now(), true, 'db+proofs to $BACKUP_TARGET')
   ON CONFLICT (job_name) DO UPDATE
     SET last_run_at = excluded.last_run_at,
         last_ok = excluded.last_ok,
         detail = excluded.detail;"

echo "[backup] done: $STAMP"
