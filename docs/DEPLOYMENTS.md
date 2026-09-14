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
| URL | http://204.168.249.99:8105/ |
| Host | same Clawsrv VPS/stack as the production app above |
| Stack dir | `/home/clawusr/curry-orders/` (same checkout; `web-v2` compose service) |
| Serves | same image/database as `web`, but with `ROOT_URLCONF=config.urls_v2_root`, mounting `public.urls_v2` (the poster/broadsheet variant from `updates0909/handover_poster_variant`) at `/` |
| Redeploy | same as production above — `git pull --ff-only && docker compose up -d --build web-v2` |
| Status | Live comparison build, for evaluating the poster/broadsheet redesign against the current production surface. |

**Note:** `docker-compose.yml`'s default `WEB_V2_BIND_PORT` is `8104`; the live Clawsrv `.env` overrides this to `8105`. Only `8102` (production) and `8105` (poster variant) are current — treat any other port number in older docs/comments as stale.
