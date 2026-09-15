# Deployments

What is actually live right now, where, and how current it is.

---

## Production Django app — Clawsrv, port 8102 ✅ LIVE

| | |
|---|---|
| URL | http://204.168.249.99:8102/ |
| Host | Clawsrv VPS — `ssh clawusr@100.78.70.2` (or `ssh clawsrv` with key config) |
| Stack dir | `/home/clawusr/curry-orders/` |
| Containers | `curry-orders-web-1` (Gunicorn, port 8102), `curry-orders-db-1` (Postgres 16), `curry-orders-minio-1` (MinIO S3, internal port 9000 / host 127.0.0.1:8103), `curry-orders-scheduler-1` |
| Static files | WhiteNoise (served from the web container) |
| Dish images | MinIO `curry-media` bucket, served via Django proxy at `/media/dish-images/<key>` (interim until Caddy/TLS — M10) |
| Redeploy | `cd /home/clawusr/curry-orders && git pull --ff-only && docker compose up -d --build web` |

### ⚠️ Deploy rule
Templates and static JS/CSS are baked into the Docker image. **`docker compose restart` will NOT pick up frontend changes.** Always rebuild with `--build web`.

### What's live
- Customer surface: Home, Menu, Order, Basket, Checkout, Order Status, Lookup, Account, Help, Policies
- Staff surface: `/manage/` (login, kitchen/collection boards, EFT queue, settings)
- Monday Sprint Phases 1–4: day refresh, inline slot change in checkout, accessibility pass, homepage hero
- Business name: **Roti Connect** throughout (all 23+ staff templates updated 2026-08-31)
- Dish card layout: Nando's-style (image right, price + add button inline, alternating card tint)

---

## Poster-variant Django app — Clawsrv, port 8105 ✅ LIVE

| | |
|---|---|
| URL | **`https://roticonnect.duckdns.org/`** (real HTTPS, no port — added 2026-09-15) — also still reachable at `http://204.168.249.99:8105/` directly |
| Host | same Clawsrv VPS/stack as the production app above |
| Stack dir | `/home/clawusr/curry-orders/` (same checkout; `web-v2` compose service) |
| Serves | same image/database as `web`, but with `ROOT_URLCONF=config.urls_v2_root`, mounting `public.urls_v2` (the poster/broadsheet variant from `updates0909/handover_poster_variant`) at `/` |
| Redeploy | same as production above — `git pull --ff-only && docker compose up -d --build web-v2` |
| Status | Live comparison build, for evaluating the poster/broadsheet redesign against the current production surface. |

### HTTPS via DuckDNS + host Caddy (2026-09-15)

`roticonnect.duckdns.org` → `204.168.249.99` (DuckDNS A record, static, no dynamic-update script needed). The **host** Caddy (not part of this repo's `docker-compose.yml` — see that file's own header comment) reverse-proxies it straight to `localhost:8105`:

```caddy
# --- Roti Connect (poster variant) ---
roticonnect.duckdns.org {
	reverse_proxy localhost:8105
}
```

Appended to `/etc/caddy/Caddyfile` on Clawsrv (root-owned — needs `sudo`, `clawusr` has no passwordless sudo). Backed up first to `/etc/caddy/Caddyfile.before-roticonnect`; validate with `sudo caddy validate --config /etc/caddy/Caddyfile` before `sudo systemctl reload caddy`, same as the existing `.before-v2` backup's precedent.

Also needed: `ALLOWED_HOSTS=204.168.249.99,roticonnect.duckdns.org` added explicitly to `.env` (was previously unset, silently defaulting to just the `SITE_URL` host — `config/settings/prod.py`'s own fallback) — without it Django 400s every request to the new hostname even though Caddy successfully proxies it. `.env` backed up to `.env.bak-roticonnect` first. Both `web` and `web-v2` restarted (`docker compose up -d web web-v2`) to pick it up, since `env_file` is read at container creation, not hot-reloaded.

**`DJANGO_TLS` deliberately left `false`** (unchanged) — turning it on would force `SECURE_SSL_REDIRECT`/`Secure` cookies globally (shared `.env`, both `web` and `web-v2`), breaking the still-active raw-IP:port access paths (`http://204.168.249.99:8102/`, `:8105/`) that have no TLS in front of them. The new HTTPS domain works fine without it — Caddy alone handles the actual TLS termination and HTTP→HTTPS redirect for that hostname; Django's own HSTS/secure-cookie hardening for it is a nice-to-have, not a requirement, and can be revisited once the raw-IP paths are retired.

`admin.rwc.org.za` (another line in the same Caddyfile) resolves to a different IP entirely (`35.164.64.246`) — not actually served by this Clawsrv instance, unrelated to any of the above.

**Note:** `docker-compose.yml`'s default `WEB_V2_BIND_PORT` is `8104`; the live Clawsrv `.env` overrides this to `8105`. Only `8102` (production) and `8105` (poster variant) are current — treat any other port number in older docs/comments as stale.
