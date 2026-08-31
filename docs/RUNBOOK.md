# Runbook

Operational procedures for the Curry Takeaway Ordering System on Clawsrv.
This is a stub — fill each section out as milestone 10 (§22) builds the
real deploy pipeline; keep it accurate as the source of truth for anyone
operating the system other than the developer.

## First deploy (already done — for reference / disaster recovery)

Stack lives at `/home/clawusr/curry-orders/` on Clawsrv (`ssh clawusr@100.78.70.2`).

```bash
# On Clawsrv:
git clone https://github.com/alboogycOdR/curry-orders.git /home/clawusr/curry-orders
cd /home/clawusr/curry-orders
cp .env.example .env && chmod 0600 .env   # populate secrets
docker compose build
# Bootstrap MinIO bucket + policy (mc is inside the minio container):
docker compose up -d minio
docker exec curry-orders-minio-1 sh -c "
  mc alias set local http://localhost:9000 \$MINIO_ROOT_USER \$MINIO_ROOT_PASSWORD &&
  mc mb --ignore-existing local/curry-media &&
  mc anonymous set download local/curry-media/dish-images"
docker compose up -d
docker compose exec web python manage.py migrate
# Append deploy/caddy-site.conf to host Caddyfile, then:
systemctl reload caddy
# Verify:
curl http://localhost:8102/healthz
```

## Routine redeploy (frontend or backend changes)

```bash
cd /home/clawusr/curry-orders
git pull --ff-only
docker compose up -d --build web   # always --build; restart alone does NOT pick up template/JS changes
```

## Rotate `SECRET_KEY` / MinIO keys
TODO.

## Restore from backup (DB + proofs bucket)
TODO: pull from `BACKUP_TARGET`, decrypt with `BACKUP_ENCRYPTION_KEY`,
`pg_restore`, `mc mirror` back into the proofs bucket. Verify a signed
proof URL resolves post-restore (§21 go-live item 2).

## Change bank details
TODO: `/manage/settings`, owner only; verify with a R1 test order before
trusting it live (§21 item 4).

## Add a staff user
TODO: `/manage/staff`, owner only; temporary password + forced change
(D-12).

## Force-expire a hold
TODO: EFT queue → **Expire now** (§12.3), or via `/api/manage/orders/:id/transition`.

## Scheduler heartbeat is stale
TODO: check `docker compose logs scheduler`; `/healthz` fails if
`job_heartbeats` hasn't updated in > 3 minutes (§17.1).

## Restart the stack without disturbing other Clawsrv tenants
TODO: `docker compose restart` inside `/srv/curry-orders` only — never
`docker restart` a bare container name shared across projects; confirm
`skulcozm_*`, `lekkerswot_*`, `oracle_postgres`, `grafana`, `uptime_kuma`
are unaffected afterwards (§17.5).
