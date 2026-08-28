# Runbook

Operational procedures for the Curry Takeaway Ordering System on Clawsrv.
This is a stub — fill each section out as milestone 10 (§22) builds the
real deploy pipeline; keep it accurate as the source of truth for anyone
operating the system other than the developer.

## First deploy
TODO: clone repo to `/srv/curry-orders` on Clawsrv, populate `.env` from
`.env.example` (mode 0600), `docker compose build`, run
`deploy/minio-bootstrap.sh`, `docker compose up -d`, run migrations, append
`deploy/caddy-site.conf` to the host Caddyfile and `systemctl reload caddy`,
verify `/healthz`.

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
