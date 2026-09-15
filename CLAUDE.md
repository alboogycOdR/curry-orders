# Current work

Customer-surface rebuild (Tasks 1–9) and Monday Sprint (Phases 1–4) are **complete and live on Clawsrv**. The app runs at `http://204.168.249.99:8102/`.

Two site variants are currently live on Clawsrv for comparison: `http://204.168.249.99:8102/` (production) and the poster/broadsheet variant (`updates0909/handover_poster_variant`, served via the `web-v2` compose service) — now reachable over real HTTPS at **`https://roticonnect.duckdns.org/`** (added 2026-09-15, host Caddy + DuckDNS), as well as still directly at `http://204.168.249.99:8105/`. See `docs/DEPLOYMENTS.md`. Treat any other port mentioned in older docs (e.g. 8104) as stale.

Google OAuth login (staff + customer, fully consolidated) shipped 2026-09-15 — see `docs/handovers/2026-09-15.md`. Not on the original M10 backlog; done ahead of it.

Active focus: dish-card UI polish (not yet scoped anywhere — confirm scope before starting), then **M10** (reports, retention/backups, Caddy/TLS, runbook, load + security tests — none of M10 started except security headers/robots.txt, already checked off). See `docs/PHASE_2_PLAN.md` for the M10 backlog.

Design detail: **`docs/ROTI_CONNECT_WIREFRAME_PLAN.md`**. That plan wins over the wireframe extract on auth and order numbers.
Readable UI spec: `docs/_wireframe_spec_extract.md`. Behaviour: `docs/SPEC_v1.1.md` + `docs/DECISIONS.md`. Agent conventions: `AGENTS.md`.

Do not rewrite capacity, transitions, or staff `/manage`. Do not invent a second status machine or `RC-` order numbers. **v1 Account is password login, not OTP — do not render Send code.**

## Deploy rule (Clawsrv)
Templates and static JS/CSS are **baked into the Docker image**. `docker compose restart` does NOT pick up frontend changes. Always:
```bash
cd /home/clawusr/curry-orders && git pull --ff-only && docker compose up -d --build web
```
