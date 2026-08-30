# Phase 2 plan

Phase 1 (milestones 1–7, narrowed 8, thin 10 — see `docs/DECISIONS.md`
D-34) is complete and merged to `main`. This is what's left of
`SPEC_v1.1.md` §22's ten-milestone sequence, and it is not optional
polish: §22 states plainly that milestone 10 is what makes **go-live
checklist items 2–7** (§21) satisfiable, and §20.1's own acceptance
criteria include lookup and reorder, which live in milestone 9.

Status legend: `[ ]` not started, `[~]` in progress, `[x]` done.

---

## M8 remainder — Menu editor (§12.7)

Daily controls (toggle a dish off *today*, sell out, close a slot) shipped
in Phase 1. This is the other half: actually managing the monthly
catalogue that daily controls reads from.

- [x] Dish list view (staff, manager+): all dishes including archived,
      sort order, active flag, category
- [x] Create/edit dish: name, slug (**set once**, immutable after), price,
      portion label, short/long description, spice default, allergen
      text, dietary tags, category, sort order, `allow_notes`
- [x] Image upload (dish photo) — reuse the MinIO/proof-upload plumbing
      from M4 (`core.storage`), validated the same way (magic bytes, size
      cap)
- [x] Dish options & option values: CRUD, price delta per value,
      `is_available` per value, required/optional per option group
- [x] Archive (soft delete) — not hard delete per D-25; archiving a dish
      with occupying orders is allowed (order snapshots persist), editor
      **warns with the affected-order count** before confirming, same
      confirm-gate pattern as M8's slot/day closing
- [x] Price changes never touch existing orders — verify via a test that
      changing `price_cents` after checkout leaves `order_lines`
      snapshots untouched
- [x] Integration tests: CRUD, slug immutability, archive-with-orders
      warning + confirm gate, price-change isolation, image upload
      validation (20 tests, `tests/integration/test_menu_editor.py`)

**Owner-input dependency:** the real dish list, prices, and photos
(`docs/GO_LIVE_PREP_SHEET.md` item 1) — this milestone is buildable
without them, but useless to actually run without them.

---

## M9 — Assisted create, calendar, lookup, reorder, inbox (§12.6, §12.9, §11.10, §11.11, §12.2)

- [ ] **Assisted order entry** (§12.9, staff, `/manage/orders/new` or
      similar): same validation and same §8.3 capacity transaction as web
      checkout; `source` tagged (`phone`/`in_person`/`whatsapp_assisted`).
      EFT assisted orders can go straight to `payment_review` (customer
      says paid, proof attached if available) or `confirmed_prep` (staff
      saw the funds — reason required, counts as `verify_eft` per D-18).
      Cash assisted follows all cash rules (M7). After cut-off requires
      `assisted_after_cutoff_enabled` (D-11) + mandatory reason.
- [ ] **Preorder calendar** (§12.6, `/manage/calendar` or similar):
      8-day grid (today + 7); per day — open/closed, orders vs cap, cash
      count vs cap, per-slot heat (occupancy/capacity), dish warnings at
      ≥80% of `max_units`. Tap-through to `/manage/days/:date` (M8) or a
      kitchen preview.
- [ ] **Lookup** (§11.10, public, already has a throttle model from M7's
      `throttle_events` table — reuse it): order number (`CT-…`,
      case-insensitive) + mobile (any accepted format, matched on last 9
      digits of E.164). Match sets a 24h `httpOnly` cookie scoped to that
      token and redirects to `/orders/:public_token`. Throttle 10/h/IP
      and 10/h/order number; failures return a generic message (no
      account-enumeration leak).
- [ ] **Reorder** (§11.11): on a `collected` order's status page, "Order
      these again" seeds a fresh cart from the same lines, dropping any
      dish that's since been archived or deactivated (with a notice
      listing what was dropped), priced at *current* prices, not the
      original order's snapshot. Customer picks date/slot/payment fresh.
- [ ] **Inbox** (§12.2, staff landing page — likely `/manage/` root):
      sectioned list — Cash requests (M7 already has its own page; inbox
      surfaces the same accept/reject inline), Hold-lapsed / SLA-breached
      reviews, Orders with notes, Recent assisted, Recently expired
      (reinstate if feasible). Row actions: open, assign, contact
      (`wa.me` link), change slot.
- [ ] Integration tests: assisted-order capacity parity with web checkout,
      after-cutoff gating + reason requirement, lookup throttle + cookie,
      reorder with an archived-dish drop notice, inbox section grouping

---

## M10 remainder — Reports, retention, backups, runbook, hardening (§12.10, §15, §17.4, §20.5)

This is the milestone §22 ties directly to go-live readiness.

### Reports (§12.10)
- [ ] On-screen report tables + CSV export, date-range filtered:
      orders/day by source and final status; confirmed vs expired vs
      cancelled (by `cancellation_reason`); payment mix; EFT median
      time-to-proof / time-to-verify / expire rate; cash no-shows; orders
      per slot; dish units sold; website vs assisted share;
      assisted-after-cutoff count; hold extensions used
- [ ] Matches §20.4's pilot-metrics acceptance line

### Retention & privacy (§15)
- [ ] Retention purge job: proof media removed `proof_retention_days`
      after `collected_at` **unless `dispute_flag`** is set
- [ ] Order-record retention per `order_retention_months`
- [ ] "Anonymise customer" staff action (replaces name/mobile snapshots
      with `[deleted]`, keeps order totals) for deletion requests routed
      through the support WhatsApp per §11.12
- [ ] Integration test: retention purge respects `dispute_flag` (already
      named explicitly in §20.5's own test-plan table)

### Backups (§15, §17.5)
- [ ] Nightly `pg_dump -Fc` **and** `mc mirror` of the MinIO proofs
      bucket, to an **off-Clawsrv** destination (owner's Hetzner Storage
      Box per the prep sheet), 14-day retention, encrypted at rest
      (GPG or rclone-encrypted remote)
- [ ] Restore drill: both DB and bucket, verified before go-live —
      **a signed proof URL must resolve after the restore** (§21 item 2's
      own bar, not just "the dump imports")

### Runbook & hardening (§17.4, §16)
- [ ] `RUNBOOK.md`: first deploy, rotate `SECRET_KEY` and MinIO keys,
      restore DB **and** bucket from backup, change bank details, add a
      staff user, force-expire a hold, what to do if the scheduler
      heartbeat is stale, restart the stack without disturbing Clawsrv's
      other tenants
- [ ] Security headers: CSP (self + CDN image host), `X-Content-Type-Options`,
      `Referrer-Policy: strict-origin-when-cross-origin`, minimal
      `Permissions-Policy`
- [ ] `robots.txt` + `noindex` on every `/orders/:token`, cash-request and
      EFT page — verified with an actual crawler check (§21 item 7)
- [ ] 4GB swap on Clawsrv, `mem_limit`s per service, host Caddy site
      blocks added + reloaded without disturbing `admin.rwc.org.za` or
      any existing tenant (§17.5)
- [ ] `/healthz` registered in Clawsrv's Uptime Kuma **and** one external
      monitor off-host; Sentry alerts routed to developer + owner

### Load & security test passes (§20.5)
- [ ] k6: 20 checkouts/min for 10 min against Clawsrv; p95 checkout
      < 800ms **measured server-side at the origin**; watch Grafana to
      confirm existing tenants aren't starved
- [ ] OWASP ZAP baseline scan + manual checklist: token entropy,
      `noindex`, signed-URL expiry, upload validation, CSRF, headers,
      lockout

### Pre-existing debt (surfaced while merging Phase 1 to `main`)
- [ ] Ruff cleanup pass — ~163 pre-existing lint errors, all in
      scaffold-era files predating the milestone work (confirmed via a
      throwaway worktree against `origin/main` before merging; the
      Phase 1 milestone files were kept clean individually throughout)
- [ ] mypy: `migrations/0001_initial.py`'s `CheckConstraint(check=...)`
      calls flag under strict mode (Django's generated migration code,
      not hand-written) — either exclude migrations from the mypy target
      or confirm this is accepted as expected noise

---

## Go-live checklist crosswalk (§21)

| Item | Depends on |
|---|---|
| 1. Owner inputs received | `docs/GO_LIVE_PREP_SHEET.md` — outside this plan, owner-side |
| 2. Backup taken + restore verified | M10 backups |
| 3. `/healthz` green in both monitors, Sentry routed | M10 runbook & hardening |
| 3a. Clawsrv prepared (swap, mem_limits, Caddy blocks, tenants healthy) | M10 runbook & hardening |
| 4. Bank details verified with a R1 test order | Owner input (bank details) + working EFT flow (already shipped) |
| 5. Both managers complete one assisted order, verify, cash accept, collect | **M9's assisted order entry** must exist first |
| 6. Print stylesheet checked on kitchen printer/phone | Already shipped (M6); re-verify on real hardware |
| 7. `robots.txt`/`noindex` verified with a crawler | M10 hardening |
| 8. Canned WhatsApp reply set up | Owner-side, outside this plan |
| 9. Pilot start + two-week review date calendared | Scheduling, outside this plan |

Items 2, 3, 3a, 7 are **blocked on M10**. Item 5 is **blocked on M9**.
Nothing in Phase 2 is blocked on owner input except the obvious (real
menu content makes the menu editor worth using, but doesn't block
*building* it).
