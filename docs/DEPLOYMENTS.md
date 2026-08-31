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

## Static prototype — Clawsrv, port 8104 (SUPERSEDED)

| | |
|---|---|
| URL | http://204.168.249.99:8104/ |
| Container | `brandons-kitchen-prototype` |
| Serves | `design/prototype/index.html` — static HTML only, no backend |
| Status | **Stale.** Serves the old dark jewel-tone theme (retired by D-30). Predates the real app entirely. |

**Owner decision required** — one of:
1. **Tear it down**: `docker rm -f brandons-kitchen-prototype` on Clawsrv
2. **Leave as historical**: stops being a "current state" link
3. **Repoint at real app**: Milestone 10 work, already scoped in `PHASE_2_PLAN.md`
