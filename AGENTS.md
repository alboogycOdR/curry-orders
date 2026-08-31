# Roti Connect / curry-orders

Django 5 + PostgreSQL 16 collection-ordering site for a Kraaifontein home kitchen. Public mobile web + staff `/manage`. Not a marketplace, not delivery.

## Source of truth

1. **Live task board:** `PLAN.md` — each task/work item has a status. Implement the next `in_progress` / first `todo` item, then mark it `done`. Design detail: `docs/ROTI_CONNECT_WIREFRAME_PLAN.md`. Do not greenfield-rewrite.
2. Customer UI screens/copy/tokens: `docs/_wireframe_spec_extract.md` (from `docs/Roti-Connect-Wireframe-Spec.docx`). If prototype ≠ extract, implement the extract **except** where the plan overrides it.
3. Behaviour / capacity / money / statuses / security: `docs/SPEC_v1.1.md`, `schema_v1_1.sql`, `docs/DECISIONS.md`.

### Do not implement from the extract (plan KD-3 / KD-6 / PR 3)

- **No OTP / Send code** in v1. Password sessions. Account must not show Send code.
- **No `RC-` order numbers or lookup aliases.** Display and bank ref stay `CT-YYMMDD-NNNN`. Lookup placeholder `CT-260901-0001`.
- **Do not remove the `/order/` slot picker in PR 3.** PR 5 moves it to `/basket/`.

## Deploy to Clawsrv (IMPORTANT)

Templates (`.html`) and static files (`*.js`, `*.css`) are **COPY**-ed into the Docker image at build time. `docker compose restart` reuses the old image and will NOT serve updated frontend code — even a browser hard-refresh cannot help if the container is still running old code.

**Always use `--build` for any frontend change:**
```bash
cd /home/clawusr/curry-orders && git pull --ff-only && docker compose up -d --build web
```

Use `--build web` only (not bare `--build`) to avoid rebuilding db/minio/scheduler.  
`restart` is only safe for env-var changes that don't touch the image itself.

## Tests

```text
py -3 -m pytest
```

From repo root. Settings: `config.settings.test`.

## Do not touch (unless a PR explicitly says so)

- `src/core/capacity.py`, `src/core/transitions.py`
- Staff templates (`src/templates/staff/`) and staff JS
- `deploy/`, production secrets
- `schema_v1_1.sql` / core migrations (no `RC-` order-number rewrite)

Integer cents everywhere (`core.money`). Django templates + vanilla JS. No React/Vue/HTMX/Alpine. No Brandon's Kitchen on customer chrome.

Stack notes: public views `src/public/`, templates `src/templates/public/`, chrome `src/templates/base.html`, CSS `src/static/css/broadsheet.css`, cart `src/static/js/cart.js`.
