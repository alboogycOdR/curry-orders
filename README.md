# Curry Takeaway Ordering System

Capacity-aware collection ordering and staff dashboard for a home-based
curry kitchen in Cape Town, South Africa. Website-first ordering (EFT or
capped same-day cash), a shared staff dashboard for payment verification,
kitchen production and collection handover, and a capacity engine that
enforces day/slot/dish/cash ceilings so the kitchen is never committed to
unsecured or oversold work.

**This is a private repository. Do not make it public** — it will contain
real customer data handling logic, bank-detail plumbing, and eventually
production configuration.

## Start here

- [`docs/SPEC_v1.1.md`](docs/SPEC_v1.1.md) — the build contract. Read this
  before touching `src/`.
- [`schema_v1_1.sql`](schema_v1_1.sql) — reference DDL for §7/§8 (Django
  migrations are the runtime source of truth; this file is executed in CI
  against an empty database to prove it still loads).
- [`docs/DECISIONS.md`](docs/DECISIONS.md) — the decision log (spec
  Appendix A, maintained going forward).
- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — deploy, backup/restore, rotate
  secrets, common ops (stub until milestone 10).
- [`docs/DISH_LIST_DRAFT.md`](docs/DISH_LIST_DRAFT.md) — draft menu
  content pending owner confirmation (§23).

## Stack

Django 5 + PostgreSQL 16 + HTMX/Alpine/Tailwind, in-process APScheduler,
self-hosted on the Clawsrv VPS with MinIO for object storage (no AWS
account, no Redis, no message broker — see spec §17, §17.5/§17.6, and
decision D-28).

## Repository layout

```
pyproject.toml     ruff, mypy, pytest config
docker-compose.yml web, scheduler, db, minio — no caddy container; the
                   host's existing Caddy reverse-proxies in (§17.5)
.env.example       see Appendix D of the spec
schema_v1_1.sql    reference DDL
deploy/            backup.sh, minio-bootstrap.sh, caddy-site.conf
docs/              SPEC_v1.1.md, DECISIONS.md, RUNBOOK.md, DISH_LIST_DRAFT.md
src/
  config/          settings (split base/prod/test), urls, asgi/wsgi
  core/            domain: models, capacity.py, transitions.py, ordering.py,
                   tz.py, phone.py, money.py — no HTTP imports, mypy strict
  public/          customer views, templates, forms, api
  manage/          staff views, templates, forms, api
  jobs/            scheduler + job functions
  storage/         media handling, signed URLs, validation
  notifications/   SMS adapter interface
tests/
  unit/ integration/ e2e/ fixtures/
```

## Build order

Milestones and their definition-of-done are in spec §22. Do not start with
visual polish on the marketing home page — the capacity transaction and
payment queue are the product (spec §22, design intent §24).

## Status

Pre-milestone-1: repository scaffolded, schema reviewed against the spec,
Clawsrv surveyed and provisioned for in the spec. Django project itself
(`manage.py`, models, `config/settings/*`) not yet written. Owner inputs
still outstanding are tracked in spec §23.
