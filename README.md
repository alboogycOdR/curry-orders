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
- [`docs/PHASE_2_PLAN.md`](docs/PHASE_2_PLAN.md) — **the current work
  queue.** Phase 1 (milestones 1–7, narrowed 8, thin 10) is done and on
  `main`; this is the checklist for what's left (menu editor, milestone
  9, the rest of milestone 10) — start here to resume development.
- [`docs/GO_LIVE_PREP_SHEET.md`](docs/GO_LIVE_PREP_SHEET.md) /
  [`.pdf`](docs/GO_LIVE_PREP_SHEET.pdf) — the 14 owner-supplied items
  (menu/prices/photos, bank details, address, etc.) blocking pilot
  go-live per §23, formatted to hand to the owner.
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

**Phase 1 complete and merged to `main`.** Milestones 1–7 shipped in full,
milestone 8 narrowed to daily controls (menu editor deferred), milestone
10 narrowed to the help/policies copy blocks (reports, retention, backups,
runbook and hardening deferred) — see decision D-34 in `docs/DECISIONS.md`
for the reasoning. The order-taking core is real end to end: menu →
checkout → capacity engine → EFT queue → kitchen board → collection board
→ cash path → daily controls, all with real staff auth and a full audit
trail. 335 tests passing.

**Not yet built** (Phase 2 — see `docs/PHASE_2_PLAN.md` for the itemised
checklist): the menu editor, assisted order entry, the preorder calendar,
public lookup/reorder, the staff inbox, pilot reports, the retention purge
job, automated backups, `RUNBOOK.md`'s real content, and the load/security
test passes. §22 ties most of this directly to go-live readiness — it
isn't polish.

**Owner inputs still outstanding**, tracked in spec §23 and formatted for
hand-off in `docs/GO_LIVE_PREP_SHEET.md`: final dish list/prices/photos,
bank details, collection address, allergen/home-kitchen disclaimer
wording, support WhatsApp number, logo/brand colours, staff names/emails,
backup destination, site/media hostnames, EU-hosting sign-off, VAT status,
and two policy decisions (cash ordering window, no-show refund policy).

### Resuming on a new machine

```
git clone <this repo> && cd curry-orders
git checkout main   # source of truth — see docs/DECISIONS.md D-34
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # fill in local DB creds, see spec Appendix D
# start Postgres 16 locally, then:
cd src && python manage.py migrate && cd ..
pytest -q   # should show 335 passed
```

Then open `docs/PHASE_2_PLAN.md` and pick up the next unchecked item.
