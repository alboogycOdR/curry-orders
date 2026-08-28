# Curry Takeaway Ordering System

## Design and Development Specification v1.1

| Field | Value |
|---|---|
| Document type | Developer handover — build contract |
| Status | **Implementation-ready.** Supersedes v1.0. Blocking owner inputs listed in §23. |
| Market | Cape Town, South Africa — home-based kitchen, collection only |
| Timezone | Africa/Johannesburg (SAST, UTC+2, no DST) |
| Fulfilment in v1 | Collection / takeaway only |
| Companion file | `schema_v1_1.sql` — authoritative PostgreSQL DDL for §7 |
| Revision date | 2026-08-28 |

Where product copy later changes, the behaviour and data rules in this document take precedence. Where this document and `schema_v1_1.sql` disagree, the SQL wins for structure and this document wins for behaviour; raise a ticket to reconcile.

---

## 0. What changed from v1.0 and why

v1.0 was a sound product spec but not yet a build contract: several rules were stated twice with different meanings, the technical shape was left open, the state machine had transitions described in prose but absent from the diagram, and there was no schema, test plan, or deployment target. v1.1 closes every one of those gaps. Every ambiguity found is resolved by a numbered decision in **Appendix A**; nothing is left "to be decided by the developer".

### 0.1 Contradictions and gaps fixed

| # | v1.0 problem | v1.1 resolution |
|---|---|---|
| 1 | §8.1 says `cancelled` never occupies capacity; §19 says cancelling from `in_kitchen`/`ready` must **not** release dish units. | Introduced `orders.dish_units_consumed` (set true on entering `in_kitchen`, never cleared). Dish-unit ceiling counts occupying statuses **plus** any order with the flag set. Day/slot ceilings use status only. §8.1, D-03. |
| 2 | §8.2 headed "Three independent ceilings" then lists four. | Four ceilings, named and coded. §8.2. |
| 3 | §12.3 allows *reject payment → stay awaiting_eft*, *reinstate expired*, and *extend hold*; none appear in the §9 diagram. | Full transition matrix with guards and side effects. §9.1. |
| 4 | `rejected` listed as a status in §8.1 but §9 shows only `cancelled`. | One terminal `cancelled` status with a `cancellation_reason` enum. D-02. |
| 5 | `new_request` described as optional. | Dropped. Checkout writes `awaiting_eft` or `cash_request` inside the capacity transaction. D-01. |
| 6 | Order number `CT-YYMMDD-NNNN` has no defined sequence source, so two concurrent checkouts could collide. | `trading_days.next_order_seq`, incremented under the same `FOR UPDATE` lock the capacity check already takes. D-04. |
| 7 | "Today + next 7 days" vs `preorder_days = 7` — 7 or 8 orderable dates? | Horizon = today (if open and before cut-off) **plus** the next 7 calendar days. Up to 8 dates. D-05. |
| 8 | Cash is same-day only, but same-day ordering closes at 10:00. Consequence not stated. | Kept as specified and made explicit: public cash orders are only possible between 00:00 and 10:00 SAST for that day. Flagged for owner confirmation in §23 with a suggested alternative. D-06. |
| 9 | Notifications mention "emailed token link" but checkout collects no email. | No email in v1. Token URL is shown, copyable, and shareable via Web Share API; lookup remains the recovery path. SMS is an optional feature-flagged add-on. D-07. |
| 10 | "allow_after_cutoff permission, owner/manager, default deny" — unclear who can grant it. | Setting `assisted_after_cutoff_enabled` (default false). Owner toggles it; when on, owner or manager may create an after-cut-off assisted order with a mandatory reason. D-11. |
| 11 | "lock list" on the kitchen board undefined. | `trading_days.kitchen_locked_at`. Locking freezes the printed prep list; anything confirmed afterwards is shown in an **Added after lock** band. D-17. |
| 12 | Hold extension "optional setting". | Mandatory: `max_hold_extensions = 1`, `hold_extension_minutes = 15`, `orders.hold_extensions` counter. D-08. |
| 13 | Close-of-day / uncollected handling described but not owned. | Explicit staff **Close out day** action plus a nightly safety job. D-16. |
| 14 | Technical shape "not mandatory". | Stack selected and fixed (§17) so the build can start without further discovery. D-13. |
| 15 | No schema, no test plan, no error-code contract, no environment/config list. | `schema_v1_1.sql`, §20.5 test plan, Appendix C error codes, Appendix D environment variables. |
| 16 | Staff password reset path undefined (would require an email provider). | Owner sets a temporary password in `/manage/staff`; forced change on next login. No email provider in v1. D-12. |
| 17 | VAT / receipt treatment unstated for a home business. | `settings.vat_registered` (default false) and `vat_number`. Receipt states "Not a tax invoice" until the owner registers. D-19. |
| 18 | Staff correction of mis-taps (e.g. accidental "collected") unhandled. | Bounded corrections: `ready → in_kitchen`, `collected → ready` within 10 minutes, audited. D-20. |

### 0.2 Additions specific to a home-based business

- Address, gate and parking instructions are released only in `confirmed_prep`, `cash_due`, `in_kitchen`, `ready` (unchanged) **and** are excluded from Open Graph tags, sitemaps and search indexing (`noindex` on all `/orders/*` pages). No map embed anywhere. No exterior photo of the property on the site.
- A single `collection_instructions` block (e.g. "Park on the road, do not hoot, WhatsApp on arrival, ring the side gate bell") is shown with the address and printed on the collection board ticket.
- Kitchen board is batch-oriented (dish → option combination → total units) because a home kitchen cooks per pot, not per ticket.
- Cash on the door is deliberately capped (20/day) and recorded per handover so the owner has a reconcilable cash figure per day.

---

## 1. Purpose

Build a website-first ordering and collection system that:

1. Lets a customer complete an ordinary order on a phone without WhatsApp.
2. Gives two staff members one shared operational system for payment, kitchen production, and collection handover.
3. Enforces capacity at dish, slot, day and cash level so the kitchen is never committed to unsecured or oversold work.
4. Treats a submitted checkout as a **request**. The kitchen may prepare the order only after the payment rule for that order is satisfied.

WhatsApp remains a marketing and support channel. It is not an order database.

## 2. Scope

### 2.1 In scope (v1 / pilot)

- Public mobile-first website: home, menu, dish, cart, checkout, EFT instructions, order lookup, help/policies, contact.
- Guest checkout (no customer password account).
- Same-day and advance collection orders (today + next 7 calendar days, see D-05).
- 15-minute collection slots inside a configurable daily window (default 16:00–18:00).
- Payment: EFT (hold + proof + staff verification) and same-day cash (staff accept + collect at handover), with a daily cash cap.
- Staff dashboard used concurrently by two managers and the owner: inbox, EFT queue, kitchen board, collection board, calendar, menu editor, daily controls, settings, reports, staff admin.
- Assisted orders captured by staff (WhatsApp / phone / in person) into the same order model and the same capacity rules.
- All operating parameters editable in settings without deploy.
- Full audit trail of status, payment, capacity and settings changes.
- Background jobs: hold expiry, trading-day materialisation, proof retention purge, nightly close-out safety.

### 2.2 Explicitly out of scope (v1)

- Delivery, driver dispatch, Uber Eats / Uber Direct / Mr D.
- Card / instant-EFT gateway checkout. (Schema extension point: a gateway `payments.method = 'gateway'` would move an order `awaiting_eft → confirmed_prep` in one step via the `verify_eft` transition with `actor = system`. Nothing else changes.)
- Customer password accounts, loyalty, coupons, gift cards, discounts (`discount_cents` column exists, always 0).
- Native iOS/Android apps.
- WhatsApp Business Platform / chatbot automation.
- Multi-branch, multi-kitchen, table service, POS hardware.
- Accounting export, SARS tax invoices beyond a simple receipt.
- Email sending of any kind.
- AI recommendations.

Do not delay v1 for any out-of-scope item.

## 3. Confirmed operating model

All values below are **defaults seeded into `settings`** and editable by the owner. None are hard-coded.

| Item | v1 default | Setting key | Notes |
|---|---|---|---|
| Volume planning | ~100 direct orders/day | — | Also the default daily cap |
| Collection window | 16:00–18:00 SAST | `default_window_start`, `default_window_end` | Overridable per trading day |
| Same-day cut-off | 10:00 SAST | `same_day_cutoff` | Public checkout stops taking today's orders at 10:00:00 |
| Preorder horizon | Today + next 7 days | `preorder_days = 7` | D-05 |
| Slot length | 15 min | `slot_minutes` | Must divide the window evenly; else last partial slot is dropped |
| Per-slot cap | 13 orders | `default_slot_capacity` | Soft; 8 × 13 = 104 but daily cap is 100 |
| Daily cap | 100 orders | `default_daily_order_cap` | Counts active commitments, not expired holds |
| Cash | Same-day only, max 20/day | `cash_enabled`, `cash_same_day_only`, `cash_daily_cap` | See D-06 |
| EFT hold | 30 min from entering `awaiting_eft` | `eft_hold_minutes` | Then auto-expire and release capacity |
| Hold extension | Once, +15 min | `max_hold_extensions = 1`, `hold_extension_minutes = 15` | Staff action only |
| Review SLA | 15 min | `payment_review_sla_minutes` | Display-only flag on the queue |
| Collection grace | 15 min after window end | `collection_grace_minutes` | Late arrivals still collectable |
| After-cut-off assisted | Disabled | `assisted_after_cutoff_enabled` | Owner toggle; reason required when used |
| Kitchen rule | EFT: after verification. Cash: after staff accept. | — | Unverified EFT never appears on kitchen totals |
| Team | 2 managers + 1 owner | — | Concurrent use, named actions |
| Address | Shown after confirm/ready only | `collection_address_line`, `collection_instructions` | Never on public menu or in metadata |
| VAT | Not registered | `vat_registered = false`, `vat_number = null` | D-19 |
| Proof retention | 90 days after collection | `proof_retention_days` | Unless `orders.dispute_flag` |
| Order retention | 18 months | `order_retention_months` | Purge job is v1.1+ (manual in pilot) |

## 4. Roles and authentication

| Role | Access | Typical device |
|---|---|---|
| Customer (guest) | Public site; own order via `public_token` or order number + mobile | Phone browser |
| Manager | Inbox, assisted entry, EFT queue, kitchen board, collection board, calendar, daily controls, menu editor, reports | Phone / tablet |
| Owner | Everything above plus settings, staff admin, owner-only exceptions (§19) | Phone or laptop |

Both managers may cover either operational role. There is no separate "order lead" / "fulfilment lead" permission; the v1.0 role names describe *who is doing what*, not access control. Every status change stores `actor_user_id` and `occurred_at`.

**Staff authentication (D-12):** email + password. Argon2id hashing. Session absolute lifetime 12 hours, sliding idle timeout 2 hours, `httpOnly; Secure; SameSite=Lax` cookie. No shared generic login. Password reset: owner sets a temporary password in `/manage/staff`; `users.must_change_password` forces a change on next login. Five failed logins lock the account for 15 minutes. Magic links are not in v1 (no email provider).

## 5. Glossary

| Term | Meaning |
|---|---|
| Trading day | A calendar date (SAST) on which collection is offered, with its own hours, slots, caps and dish availability |
| Slot | A 15-minute collection interval on a trading day |
| Dish | An item on the monthly menu |
| Option / value | Structured choice on a dish (Spice: Mild/Medium/Hot). A value may carry a price delta |
| Unit | One quantity of one dish on one order line. Dish caps are in units |
| Request | Checkout completed; kitchen is not yet committed (`awaiting_eft`, `payment_review`, `cash_request`) |
| Confirmed | Payment rule satisfied; counts toward kitchen production (`confirmed_prep`, `cash_due`, `in_kitchen`, `ready`) |
| Active commitment / occupying order | An order whose status is in the **occupying set** (§8.1). Occupies day, slot, dish and (if cash) cash capacity |
| Dish units consumed | An order that reached `in_kitchen`; its dish units are never returned to that day's cap regardless of later status |
| Assisted order | Created by staff on behalf of a customer; `source ≠ website` |
| Hold | The `eft_hold_minutes` window during which an `awaiting_eft` order occupies capacity without payment |
| Hold lapsed | `payment_review` order whose `hold_expires_at` has passed; not auto-expired, flagged for staff |
| Close out | Staff action at end of trading day that resolves every `ready` order to `collected` or `cancelled/no_show` |

## 6. Information architecture

### 6.1 Customer site

| Route | Purpose |
|---|---|
| `/` | Home |
| `/menu?date=YYYY-MM-DD` | Menu for a trading day (default: first orderable date) |
| `/dishes/:slug?date=` | Dish detail. Permalinks are stable and used in WhatsApp Status, Instagram, TikTok |
| `/cart` | Cart |
| `/checkout` | Checkout |
| `/orders/:public_token` | Order status / EFT instructions / confirmed view. `noindex, nofollow` |
| `/orders/lookup` | Order number + mobile lookup form |
| `/help` | How to order, collection, payment, cut-off |
| `/policies` | Cancellation, allergens, privacy (POPIA) |
| `/contact` | Support; WhatsApp deep link |
| `/robots.txt`, `/sitemap.xml` | Sitemap lists `/`, `/menu`, `/dishes/*`, `/help`, `/policies`, `/contact` only |

### 6.2 Staff app (all under `/manage`, authenticated)

| Route | Purpose |
|---|---|
| `/manage/login` | Login |
| `/manage/inbox` | New cash requests, assisted drafts, orders with notes, hold-lapsed reviews, exceptions |
| `/manage/payments` | EFT queue |
| `/manage/kitchen?date=` | Kitchen board (default today) |
| `/manage/collection?date=` | Collection board (default today) |
| `/manage/calendar` | 8-day load and capacity grid |
| `/manage/orders/:id` | Order detail + audit + actions |
| `/manage/orders/new` | Assisted create |
| `/manage/menu`, `/manage/menu/:id` | Dish list and editor |
| `/manage/days/:date` | Daily controls |
| `/manage/settings` | Owner only |
| `/manage/reports` | Pilot metrics |
| `/manage/staff` | Owner only |

Staff UI is mobile-first. Collection and payment queues must be usable one-handed with the phone in portrait.

## 7. Domain model

The authoritative DDL is `schema_v1_1.sql`. This section explains intent and the non-obvious rules. All timestamps are `timestamptz` stored in UTC; all business-rule evaluation converts to Africa/Johannesburg first. Money is integer cents (ZAR). Primary keys are `bigint identity` except where noted.

### 7.1 `users` (staff)
`id, email (unique, citext), name, role (owner|manager), password_hash, active, must_change_password, failed_login_count, locked_until, last_login_at, created_at`.

### 7.2 `settings` (single row, `id = 1` enforced by CHECK)
Typed columns, one per key in §3 plus: `collection_address_line`, `collection_instructions`, `bank_name`, `account_name`, `account_number`, `branch_code`, `account_type`, `support_whatsapp_e164`, `public_site_name`, `allergen_disclaimer`, `home_kitchen_notice`, `sms_enabled`, `sms_ready_template`, `updated_by`, `updated_at`. Every save writes a `settings_events` row with a JSON diff. Bank details are shown to customers only on the EFT page and never written to logs.

### 7.3 `dishes`
As v1.0, plus `archived_at` (soft delete, D-25) and `image_media_id`. `slug` is immutable after first publish (permalinks are marketing assets). `is_active_on_menu` is the monthly visibility switch; day-level overrides live in `day_dish_availability`.

### 7.4 `dish_options`, `dish_option_values`
As v1.0. `dish_options.required` means exactly one value must be chosen. `dish_option_values.is_available = false` hides the value from new carts; existing snapshots are unaffected.

### 7.5 `trading_days`
`date (PK, SAST calendar date), is_open, window_start, window_end, cutoff_time, daily_order_cap, next_order_seq (default 1), kitchen_locked_at, kitchen_locked_by, closed_out_at, closed_out_by, notes_internal, created_at, updated_at`.

Lazy materialisation: when any code path needs a date inside the horizon and no row exists, insert one from settings defaults with `ON CONFLICT (date) DO NOTHING` and generate its slots (§10). A nightly job also ensures the next 10 days exist. Staff overrides persist on the row and are never overwritten by defaults.

### 7.6 `slots`
`id, trading_day, start_at (time), end_at (time), capacity, is_closed`. Unique on `(trading_day, start_at)`. Slot `label` is derived (`HH:MM–HH:MM`), not stored.

### 7.7 `day_dish_availability`
`(trading_day, dish_id) PK, is_available, max_units`. Absent row ⇒ available if `dishes.is_active_on_menu AND archived_at IS NULL`, uncapped.

### 7.8 `customers`
`id, full_name, mobile_e164 (unique), first_seen_at, last_order_at, order_count`. Upsert on checkout by mobile; name is updated to the latest given. Orders keep their own name/mobile snapshots.

### 7.9 `orders`
As v1.0 plus: `dish_units_consumed boolean`, `hold_extensions smallint`, `balance_due_cents`, `refund_note`, `dispute_flag boolean`, `after_cutoff_reason`, `in_kitchen_at`, `slot_id` nullable only in the `cancelled`/`payment_expired` states after a slot is deleted (never in practice — slots with orders cannot be deleted). `order_number` format `CT-YYMMDD-NNNN` where `YYMMDD` is the **collection date** and `NNNN` is that day's sequence (D-04). `public_token` is 22+ chars from 128 bits of CSPRNG, base64url.

### 7.10 `order_lines`
As v1.0. `dish_id` is `ON DELETE SET NULL`; the snapshot columns are what the kitchen and receipts render. `options_snapshot` JSON shape: `[{"option":"Spice","value":"Mild","delta_cents":0}]`. A generated `option_key` text column (`"Spice=Mild|Starch=Rice"`, options sorted by name) enables kitchen grouping in SQL.

### 7.11 `payments` (exactly one row per order, `order_id` unique)
`method, amount_cents, reference (= order_number for EFT), current_proof_media_id, customer_declared_ref, status (pending|under_review|verified|rejected|expired|collected_cash|cancelled), verified_by, verified_at, rejected_reason, cash_received_by, cash_received_at, cash_amount_received_cents`. Proof re-uploads create a new `media` row and repoint `current_proof_media_id`; previous proofs stay linked to the order for audit until retention purge.

### 7.12 `order_events` (audit)
`order_id, from_status, to_status, action, actor_user_id (null = system or customer), actor_kind (staff|customer|system), payload jsonb, occurred_at`. Every transition, slot change, item amendment, hold extension, proof upload, cash receipt and capacity override writes a row.

### 7.13 `media`
`id, kind (proof|dish_image), storage_key, mime_type, byte_size, sha256, order_id nullable, dish_id nullable, uploaded_by nullable, created_at, purged_at`. Proofs: private MinIO bucket, signed GET URLs valid 5 minutes, staff-only. Dish images: public MinIO bucket served over the media subdomain (D-28). Accepted proof types: `image/jpeg, image/png, image/webp, application/pdf`, max 8 MB, validated by magic bytes not extension.

### 7.14 `idempotency_keys`
`key (PK), request_sha256, order_id, response_status, created_at`. Checkout requires an `Idempotency-Key`. Same key + same hash ⇒ return the original order. Same key + different hash ⇒ `409 idempotency_conflict`. Rows expire after 24 h.

### 7.15 `throttle_events`
`scope, key, occurred_at`. Postgres-backed rate limiting (no Redis dependency). Counted with a rolling window; rows older than 1 hour are purged by the job runner.

### 7.16 `settings_events`
`id, user_id, diff jsonb, occurred_at`.

## 8. Capacity engine

This is the critical backend. **Every reservation change happens in one database transaction** with row locks (`SELECT ... FOR UPDATE`) on, in this order: the `trading_days` row, the `slots` row, then each affected `day_dish_availability` row ordered by `dish_id`. Fixed lock ordering prevents deadlocks between concurrent checkouts.

### 8.1 What counts as occupied

**Occupying set (day, slot and cash ceilings):**
`awaiting_eft, payment_review, cash_request, confirmed_prep, cash_due, in_kitchen, ready`.

**Not occupying:** `payment_expired, cancelled, collected`.

**Dish-unit ceiling** counts units on orders that are in the occupying set **OR** have `dish_units_consumed = true` (D-03). `dish_units_consumed` is set when an order enters `in_kitchen` and is never cleared, so a collected or no-show order keeps its units allocated for that day. Slot occupancy for a collected order is irrelevant after the slot has ended.

```sql
-- occupying orders (day / slot / cash ceilings)
CREATE VIEW v_occupying_orders AS
SELECT * FROM orders
 WHERE status IN ('awaiting_eft','payment_review','cash_request',
                  'confirmed_prep','cash_due','in_kitchen','ready');

-- dish unit consumption per day/dish
CREATE VIEW v_dish_units_used AS
SELECT o.trading_day, l.dish_id, SUM(l.quantity) AS units
  FROM orders o JOIN order_lines l ON l.order_id = o.id
 WHERE l.dish_id IS NOT NULL
   AND (o.status IN ('awaiting_eft','payment_review','cash_request',
                     'confirmed_prep','cash_due','in_kitchen','ready')
        OR o.dish_units_consumed)
 GROUP BY o.trading_day, l.dish_id;
```

### 8.2 Four independent ceilings

Checkout, assisted create, reinstate, slot change and item amendment must pass every ceiling that applies. Evaluation order and error code on failure:

| # | Ceiling | Rule | Error code |
|---|---|---|---|
| 0 | Day open | `trading_days.is_open` | `day_closed` |
| 0 | Horizon | date ∈ orderable dates (§8.4) | `outside_horizon` |
| 0 | Cut-off | if date is today: `now_sast < cutoff_time` (public) | `cutoff_passed` |
| 0 | Slot open | `slots.is_closed = false` and slot belongs to date | `slot_closed` |
| 1 | Day order cap | occupying orders on day `< daily_order_cap` | `day_full` |
| 2 | Slot order cap | occupying orders in slot `< slots.capacity` | `slot_full` |
| 3 | Dish availability | dish active, not archived, not hidden that day | `dish_unavailable` |
| 3 | Dish unit cap | `used_units + line_quantity <= max_units` when `max_units` is set | `dish_qty_exceeded` |
| 4 | Cash day cap | if `method = cash`: occupying cash orders on day `< cash_daily_cap` | `cash_cap` |
| 4 | Cash same-day | if `method = cash` and `cash_same_day_only`: date = today | `cash_not_allowed` |

Cash requests not yet accepted still occupy the cash cap and the day/slot/dish ceilings, so two customers cannot both take the last cash place. All ceiling errors return HTTP 422 with the structured body in Appendix C, including `alternatives` (next open slots on the same day, and the next open day) where computable.

### 8.3 Reservation transaction (checkout)

```
BEGIN;
  day  := SELECT * FROM trading_days WHERE date = :date FOR UPDATE;
  slot := SELECT * FROM slots WHERE id = :slot_id AND trading_day = :date FOR UPDATE;
  avail := SELECT * FROM day_dish_availability
            WHERE trading_day = :date AND dish_id = ANY(:dish_ids)
            ORDER BY dish_id FOR UPDATE;
  -- ceilings 0..4 (§8.2); on first failure ROLLBACK and return 422
  -- snapshot prices from current dishes / dish_option_values (§11.6 step 2)
  seq := day.next_order_seq;  UPDATE trading_days SET next_order_seq = seq + 1 WHERE date = :date;
  order_number := format('CT-%s-%04d', to_char(:date,'YYMMDD'), seq);
  INSERT orders (status = awaiting_eft | cash_request, hold_expires_at = now()+eft_hold_minutes for EFT);
  INSERT order_lines ...; INSERT payments (status = pending);
  INSERT order_events (from_status NULL, to_status ..., actor_kind customer);
  INSERT idempotency_keys ...;
COMMIT;
```

Statement timeout for this transaction: 5 s. Serialisation is by row lock, not by `SERIALIZABLE` isolation; `READ COMMITTED` is sufficient because every count is executed after the locks are held.

### 8.4 Orderable dates and same-day cut-off (D-05)

`orderable_dates(now_sast)`:
1. `today` is included only if its trading day `is_open` **and** `now_sast.time < cutoff_time` (strict; at exactly 10:00:00 today is closed).
2. Then each of `today+1 … today+preorder_days` that `is_open`.
3. Dates are materialised on demand.

Existing holds for today continue until their own `hold_expires_at`; the cut-off does not expire them. Staff may create an assisted order for today after cut-off only when `assisted_after_cutoff_enabled = true`, with a mandatory `after_cutoff_reason` (D-11).

### 8.5 Hold vs commit

| Event | Capacity effect | Status | Timer |
|---|---|---|---|
| EFT checkout succeeds | Occupy | `awaiting_eft` | `hold_expires_at = now + eft_hold_minutes` |
| Proof uploaded | Occupy | `payment_review` | Timer remains for display; **no auto-expiry** in this state |
| Staff extends hold | Occupy | unchanged | `+hold_extension_minutes`, max `max_hold_extensions` times |
| EFT verified | Occupy | `confirmed_prep` | `hold_expires_at` cleared |
| Hold timeout while `awaiting_eft` | **Release all ceilings** | `payment_expired` | — |
| Cash checkout | Occupy (incl. cash cap) | `cash_request` | none |
| Cash accepted | Occupy | `cash_due` | none |
| Cash rejected / any cancel before `in_kitchen` | Release all ceilings | `cancelled` | — |
| Cancel from `in_kitchen` / `ready` | Release day/slot; **dish units stay consumed** | `cancelled` | — |

**Hold lapsed in review:** when `payment_review` and `hold_expires_at < now`, the queue shows a red **hold lapsed** flag and the inbox counts it. A second flag, **SLA breached**, appears when `now - proof_uploaded_at > payment_review_sla_minutes`. Staff must verify or reject; nothing is dropped silently.

### 8.6 Concurrency

- Re-validate at submit, never trust the rendered slot list.
- Cart pages may warn optimistically from `GET /api/availability`; the server is authoritative.
- Two staff acting on the same order: every transition carries `expected_status`; if the row's status differs, return `409 stale_state` with the current status. First writer wins; second sees a refreshed screen.
- Slot capacity may not be reduced below its current occupying count (§18.16). Window may not be shortened past a slot with occupying orders (§18.19).

## 9. Order state machine

Statuses: `awaiting_eft, payment_review, confirmed_prep, cash_request, cash_due, in_kitchen, ready, collected, payment_expired, cancelled`. Terminal: `collected, payment_expired, cancelled` (with the bounded corrections in D-20 / §9.1).

```
EFT path                                   CASH path
checkout ──► awaiting_eft                  checkout ──► cash_request
              │  proof_uploaded                            │ accept_cash
              ▼                                            ▼
          payment_review ──reject_eft──► awaiting_eft    cash_due
              │  verify_eft                                │
              ▼                                            │
         confirmed_prep ◄──────────────────────────────────┘
              │  start_kitchen  (sets dish_units_consumed)
              ▼
          in_kitchen ◄──── revert_ready ──┐
              │  mark_ready                │
              ▼                            │
            ready ─────────────────────────┘
              │  mark_collected            ◄── uncollect (≤10 min, correction)
              ▼
          collected

awaiting_eft ──expire_hold (system/staff)──► payment_expired ──reinstate──► awaiting_eft
any non-terminal ──cancel──► cancelled
cash_request ──reject_cash──► cancelled (reason cash_rejected)
ready ──close_out_no_show──► cancelled (reason no_show, dish units stay consumed)
```

### 9.1 Transition matrix

Unknown or disallowed transitions return `409 illegal_transition`. All rows write `order_events`. "Staff" = manager or owner unless stated.

| Action | From | To | Actor | Guards | Side effects |
|---|---|---|---|---|---|
| `checkout` | — | `awaiting_eft` / `cash_request` | customer / staff (assisted) | §8.2 ceilings; idempotency | Create order, lines, payment(pending); set hold for EFT |
| `proof_uploaded` | `awaiting_eft`, `payment_review` | `payment_review` | customer via token, or staff | media valid; ≤5 uploads/hour/token | New media row; `payments.current_proof_media_id`; `payments.status = under_review`; `proof_uploaded_at` |
| `verify_eft` | `payment_review`, `awaiting_eft`* | `confirmed_prep` | staff | *from `awaiting_eft` requires reason (e.g. seen in bank app without proof) | `payments.status = verified`, `verified_by/at`; `confirmed_at`; clear `hold_expires_at`; if `kitchen_locked_at` set, flag `added_after_lock` in event payload |
| `reject_eft` | `payment_review` | `awaiting_eft` | staff | reason required | `payments.status = pending`, `rejected_reason`; keep current proof for audit; hold unchanged (staff may `extend_hold`) |
| `extend_hold` | `awaiting_eft`, `payment_review` | unchanged | staff | `hold_extensions < max_hold_extensions` | `hold_expires_at += hold_extension_minutes`; `hold_extensions += 1` |
| `expire_hold` | `awaiting_eft` | `payment_expired` | system (job) or staff ("Expire now") | job: `hold_expires_at < now`; staff: none | Release capacity; `payments.status = expired` |
| `reinstate` | `payment_expired` | `awaiting_eft` | staff | full §8.2 recheck (cut-off ignored for reinstatement of an existing order, but day must be open); reason | Fresh `hold_expires_at = now + eft_hold_minutes`; `hold_extensions = 0`; `payments.status = pending`; same order number |
| `accept_cash` | `cash_request` | `cash_due` | staff | — | `confirmed_at` |
| `reject_cash` | `cash_request` | `cancelled` | staff | reason optional, default `cash_rejected` | Release capacity; `payments.status = cancelled` |
| `start_kitchen` | `confirmed_prep`, `cash_due` | `in_kitchen` | staff (single or bulk) | — | `in_kitchen_at`; `dish_units_consumed = true` |
| `mark_ready` | `in_kitchen` | `ready` | staff (single or bulk) | — | `ready_at`; optional SMS if enabled |
| `revert_ready` | `ready` | `in_kitchen` | staff | not yet collected | correction, reason optional |
| `mark_collected` | `ready` | `collected` | staff | if `payment_method = cash`: `cash_amount_received_cents` supplied (defaults to total) | `collected_at`; cash: `payments.status = collected_cash`, `cash_received_by/at`; EFT: unchanged (already verified) |
| `uncollect` | `collected` | `ready` | staff | `now - collected_at <= 10 min`; reason required | Clears `collected_at`; cash receipt row retained in event payload and cleared on payment |
| `cancel` | any non-terminal | `cancelled` | staff; owner only from `in_kitchen`/`ready` | reason enum required | Release day/slot/cash; release dish units only if `dish_units_consumed = false`; if EFT verified, set `refund_note = 'refund_pending'` |
| `close_out_no_show` | `ready` | `cancelled` (`no_show`) | staff via Close out day, or nightly job | `now_sast > window_end + collection_grace_minutes` | Dish units stay consumed; `payments.status` unchanged (cash never received; EFT stays verified with `refund_note` blank — owner policy) |
| `change_slot` | any non-terminal except `ready`, `collected` | unchanged | staff | new slot on same day, open, capacity available (lock + recheck) | `slot_id` updated; payload `{from_slot, to_slot}` |
| `amend_items` | `awaiting_eft`, `payment_review`, `cash_request`, `confirmed_prep`, `cash_due` | unchanged | staff | dish ceilings rechecked for increased units; reason | Lines replaced with new snapshots; totals recalculated; if EFT verified and total increased: `balance_due_cents`; if decreased: `refund_note` |

Only legal next actions are rendered as buttons for the order's current status and the user's role.

### 9.2 Customer-facing copy (unchanged from v1.0, plus two states)

| Internal status | Customer wording |
|---|---|
| `awaiting_eft` | We received your order request. Your collection slot is held pending EFT. Use reference **{order_number}**. Pay by **{hold_expires_at}**. |
| `payment_review` | We are verifying your payment. |
| `confirmed_prep` | Your order is confirmed for collection on {date} at {slot_label}. |
| `cash_request` | We received your cash order request. We will confirm shortly. |
| `cash_due` | Your order is confirmed. Pay cash on collection. Bring reference **{order_number}**. |
| `in_kitchen` | Your order is being prepared. |
| `ready` | Your order is ready. Collect using reference **{order_number}**. |
| `collected` | Thank you — your order has been collected. |
| `payment_expired` | The order could not be confirmed because payment was not received in time. |
| `cancelled` (`no_show`) | This order was not collected during the collection window. |
| `cancelled` (other) | This order was cancelled. |

Collection address and instructions render only on `confirmed_prep`, `cash_due`, `in_kitchen`, `ready`.

### 9.3 Board membership

| Board | Statuses |
|---|---|
| Inbox | `cash_request`; `payment_review` with hold lapsed or SLA breached; any open order with a non-empty `note`; assisted orders created in the last 24 h; `payment_expired` in last 24 h (for reinstatement) |
| EFT queue | `awaiting_eft`, `payment_review` |
| Kitchen | `confirmed_prep`, `cash_due`, `in_kitchen`, `ready` |
| Collection | `ready` (primary), `in_kitchen` (greyed, "not ready"), `collected` (today, collapsed) |
| Uncollected | `ready` after `window_end + grace` |

## 10. Default slot grid and materialisation

With defaults 16:00–18:00 / 15 min, eight slots: 16:00–16:15, 16:15–16:30, 16:30–16:45, 16:45–17:00, 17:00–17:15, 17:15–17:30, 17:30–17:45, 17:45–18:00.

Generation: starting at `window_start`, emit `[t, t+slot_minutes)` while `t + slot_minutes <= window_end`. Each slot gets `capacity = default_slot_capacity`.

Rules:
- Staff may close a slot, change its capacity (not below current occupancy), or change the day's window.
- Changing the window regenerates only **empty** future slots (no occupying orders). A slot with occupying orders is never deleted; staff must close it and move its orders first.
- Slot `end_at` is exclusive; a slot's ticket count on the collection board is by `slot_id`, not by time.

## 11. Customer application

### 11.1 General UX
- Mobile-first, thumb reach, ≥44 px tap targets, no hamburger-only primary CTA.
- Performance budget: menu page LCP < 2.5 s on simulated 4G, total JS < 60 kB gzipped. Images WebP with `srcset`, max display width 1200 px, lazy-loaded below the fold.
- English first. Currency `R 185.00` (space thousands, two decimals).
- No account. No email field.
- Every `/orders/*` page: `<meta name="robots" content="noindex, nofollow">`, no Open Graph image, generic `og:title`.

### 11.2 Home
Brand/cuisine paragraph; today's status line computed live ("Order today until 10:00 for collection 16:00–18:00" / "Today's orders are closed — order for tomorrow"); 3–6 featured dishes; primary **Order now** → `/menu`; three-step "how it works". **No street address, no map, no exterior photo.**

### 11.3 Menu
Date switcher listing `orderable_dates` only. Dish cards: photo, name, price, spice/dietary badges, **Sold out** state for the selected date (visible, greyed, not addable). Card links to `/dishes/:slug?date=`.

### 11.4 Dish
Gallery; description; portion; allergens; price; required options as radio; optional add-ons; quantity stepper (1–20); **Add to cart**. Cart is date-aware: one cart, one collection date. Changing date re-validates every line; unavailable lines are removed with an inline notice listing what was removed.

### 11.5 Cart
Lines with option summary, qty stepper, line total, remove; selected date with change control; subtotal; **Continue**; empty state → menu. Cart state is client-side (localStorage on the customer's own site is acceptable here) plus server validation at checkout.

### 11.6 Checkout

| Field | Required | Validation |
|---|---|---|
| Full name | Yes | 2–80 chars, trimmed |
| Mobile | Yes | SA mobile; accept `082…`, `+2782…`, `2782…`, `0027…`; normalise to E.164 `+27…`; must match `^\+27[6-8]\d{8}$` |
| Order note | No | ≤200 chars |
| Collection date | Yes | ∈ `orderable_dates` |
| Slot | Yes | Open slot on that date with remaining capacity |
| Payment method | Yes | `eft` always if `eft` bank details set; `cash` only if `cash_enabled` ∧ date = today ∧ cash remaining > 0 |
| Accept policies | Yes | Checkbox; link to `/policies` |

On submit (`POST /api/checkout` with `Idempotency-Key`):
1. Validate fields (400 on failure).
2. Run §8.3 transaction: lock, ceilings, price snapshot from **current** records (show a notice if any line price differs from the cart's cached price; the current price is charged — §18.13), order number, insert.
3. Redirect to `/orders/:public_token`. Show **Copy link** and **Share** (Web Share API) with the text "Your order {order_number}: {url}".

### 11.7 EFT page (`awaiting_eft`, `payment_review`)
Large order number with copy button; amount; bank details from settings; "Use this exact reference"; countdown to `hold_expires_at` (server time, not client clock); proof upload control (camera/file, 8 MB, JPEG/PNG/WebP/PDF); current status; items, date, slot label; WhatsApp link for payment problems only. After upload: "We are verifying your payment" and the countdown is replaced by "Your proof is with us — no further action needed."

### 11.8 Cash request page (`cash_request`)
Explain staff must accept; items, slot; "Cash due on collection if accepted"; no bank details; no address.

### 11.9 Confirmed / ready page
Status banner; order number; slot and date; **address + collection instructions**; items; payment badge (Paid / Cash due R x); lookup reminder.

### 11.10 Lookup
Inputs: order number (`CT-…` case-insensitive) + mobile (any accepted format; compared on the last 9 digits of the E.164 national number). On match, set a 24 h `httpOnly` cookie scoped to that token and redirect to the token URL. Throttle: 10 attempts/hour/IP and 10/hour/order number (`throttle_events`). Failures return a generic message.

### 11.11 Reorder
On a `collected` order page: **Order these again** → new cart with the same lines for dishes that are active and unarchived, at current prices; dropped lines listed in a notice. Customer chooses date, slot and payment method afresh.

### 11.12 Help / policies (required copy blocks)
Must state: 10:00 same-day cut-off; 7-day horizon; 15-minute slots 16:00–18:00 unless varied; EFT 30-minute hold and reference = order number; cash same-day only, limited, staff acceptance, due at collection; kitchen starts after EFT verify or cash accept; cancellation rules (§19); allergen and home-kitchen disclaimer (owner wording); POPIA notice — what is stored (name, mobile, order, payment proof), purpose (fulfilment and payment reconciliation), retention (proofs 90 days, orders 18 months), how to request deletion (support WhatsApp); **where it is stored — data is processed and stored on a server in the EU (Finland) on the owner's behalf and remains subject to POPIA (§17.6)**; "Do not place routine orders on WhatsApp."

## 12. Staff application

### 12.1 Shared requirements
- Live-enough: HTMX polling every 15 s on inbox, payments, collection; 30 s on kitchen. Each poll returns a fragment with an `ETag`; unchanged ⇒ 304. (WebSockets are not required for 3 users.)
- Visible assignee on each open order; **Assign to me**.
- Action buttons show only legal transitions for status + role (§9.1) and carry `expected_status` (§8.6).
- Global search by order number, name, mobile (last digits OK).
- Sound/badge on new proof and new `ready`: nice-to-have, not a blocker.
- Every screen shows the current SAST time in the header (staff phones may be on another locale).

### 12.2 Inbox
Sections in order: **Cash requests** (accept → `cash_due`, reject), **Hold lapsed / SLA breached reviews**, **Orders with notes**, **Recent assisted**, **Recently expired** (reinstate if feasible). Row actions: open, assign, contact (shows mobile + `wa.me` link), change slot.

### 12.3 EFT payment queue
Sort: hold expiry ascending (lapsed first), then slot start. Columns: order number, name, amount, slot, hold remaining / lapsed, proof thumbnail, status, flags. Actions per §9.1: open proof (signed URL), **Verify**, **Reject** (reason), **Extend hold**, **Expire now**, **Reinstate** (expired only). Verifier and time recorded. Proof viewer shows the customer-declared reference alongside the expected order number.

### 12.4 Kitchen board
Date selector (default today). **Summary view** (primary): grouped by `dish_name_snapshot → option_key → SUM(quantity)`, e.g. `Butter chicken / Medium / Rice × 18`. **Exceptions band**: orders with non-empty `kitchen_note` or `note`, and allergen-flagged dishes. **Drill-down**: orders contributing to a group. Actions: **Lock prep list** (sets `kitchen_locked_at`; totals confirmed afterwards appear in an **Added after lock** band), **Start kitchen** (bulk `start_kitchen`), **Mark ready** (single/bulk), **Print** (print stylesheet). Never shows `awaiting_eft`, `payment_review`, `cash_request`, `payment_expired`, `cancelled`, `collected`.

### 12.5 Collection board
Default today, grouped by slot in time order, current slot highlighted. Ticket: very large order number, name, item count, payment badge **PAID** / **CASH R x**, ready badge, assignee. Actions: mark ready (if `in_kitchen`), **Collected** (cash: amount field defaults to total, must confirm), uncollect (≤10 min), change slot. After `window_end + grace`, remaining `ready` tickets move to **Uncollected**. **Close out day** button (visible after grace): lists uncollected tickets; staff confirms `no_show` per ticket or all; sets `closed_out_at`. Nightly job (23:30 SAST) applies `no_show` to anything still `ready` and marks the day closed out with `actor = system`.

### 12.6 Preorder calendar
Eight-day grid (today + 7): open/closed, orders vs cap, cash count vs cap, slot heat (occupancy/capacity per slot), dish warnings (≥80 % of `max_units`). Tap through to `/manage/days/:date` or kitchen preview.

### 12.7 Menu editor
CRUD dishes, options, values, image upload, allergens, dietary tags, active flag, sort, category; archive (soft delete). Slug is set once. Price changes never touch existing orders. Archiving a dish with occupying orders is allowed (snapshots persist); the editor warns with the count.

### 12.8 Daily controls (`/manage/days/:date`)
Open/close day; override window and cut-off; daily cap; per-slot close/capacity; per-dish available toggle and `max_units`; internal notes. Closing a day or slot that has occupying orders requires typed confirmation and lists the affected orders with a **Move all to…** helper.

### 12.9 Assisted order entry
Same validation and the same §8.3 transaction as web checkout; `source` tagged. Staff may place an EFT assisted order directly into `payment_review` (customer says they have paid — attach proof if available) or `confirmed_prep` (staff has seen the funds — reason required, counts as `verify_eft`). Cash assisted follows all cash rules. After cut-off requires D-11.

### 12.10 Reports (pilot)
On-screen tables with CSV export, date range: orders per day by source and by final status; confirmed vs expired vs cancelled (by reason); payment mix; EFT median time-to-proof, median time-to-verify, expire rate; cash no-shows; orders per slot; dish units sold; website vs assisted share; assisted-after-cut-off count; hold extensions used.

## 13. Notifications (v1)

| Event | Customer | Staff |
|---|---|---|
| Order created | On-screen + token URL + Copy/Share | Inbox / payments increment |
| Proof uploaded | On-screen | Payment queue increment |
| EFT verified / cash accepted | On-screen status | — |
| Ready | On-screen; **optional SMS** if `sms_enabled` | Collection board |
| Expired / cancelled | On-screen | — |

SMS (D-07): behind `sms_enabled`; provider adapter interface `send_sms(e164, text) -> provider_message_id`; first implementation BulkSMS or Clickatell (both SA). Templated transactional text only, e.g. `{site}: order {order_number} is ready. Collect {slot_label} at {address_line}. {instructions}`. Ordering is the opt-in. Failure to send never blocks a transition; it is logged in `order_events` payload.

## 14. WhatsApp during migration

No API integration. Dish page URLs are the catalogue/status targets. Header/footer/help: "Questions? WhatsApp us" via `https://wa.me/<number>?text=<urlencoded>`. Staff canned reply (operations, not software):

> Thank you. Please place collection orders at {site}, where you can choose a time and get an order reference. Reply HELP if you cannot use the website.

If they cannot use the site, staff creates an assisted order. Never accept a chat order that is not entered into the dashboard.

## 15. Security, privacy, audit

- HTTPS only; HSTS; TLS via Caddy with automatic certificates.
- Argon2id password hashing; login throttling and lockout (§4).
- `public_token` ≥128 bits CSPRNG, base64url; constant-time comparison.
- Lookup throttled and requires order number + mobile.
- Proof files in a private bucket; signed URLs 5 min; never listed publicly; magic-byte validation; stored under a random key, never the original filename.
- CSRF protection on all staff forms; CORS limited to the site origin (single origin — the staff app is served from the same host).
- Security headers: CSP (self + CDN image host), `X-Content-Type-Options`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy` minimal.
- Role checks on every `/manage` route and API; owner-only routes enforced server-side.
- Audit: every status/payment/capacity/settings change (§7.12, §7.16).
- Logging: structured JSON; never log bank details, proof URLs, full mobile numbers (mask to `+27 82 *** 1234`), or passwords. Request IDs on every log line.
- POPIA: information officer = owner; **cross-border processing — personal data is stored in the EU (Finland) on Clawsrv; transfer basis is POPIA §72 comparable-protection via the GDPR; disclosed in `/policies` (§11.12, §17.6)**; retention job purges proof media `proof_retention_days` after `collected_at` unless `dispute_flag`; deletion requests handled by owner via an "Anonymise customer" action (replaces name/mobile snapshots with `[deleted]`, keeps order totals for records).
- Backups (self-hosted, so both halves matter): daily `pg_dump -Fc` **and** a `mc mirror` of the proofs bucket, written to an **off-Clawsrv** destination (owner's choice of another VPS, Backblaze B2, or an encrypted rclone remote — a backup that lives only on Clawsrv is not a backup). 14-day retention, GPG- or rclone-encrypted at rest, restore of both DB and bucket tested before pilot (§21).

## 16. Non-functional requirements

| Area | Requirement |
|---|---|
| Time | All business rules evaluate in Africa/Johannesburg; DB stores UTC; tests pin the zone |
| Load | 100 orders/day; bursty 09:00–10:00 checkout (design for 20 checkouts/min) and 16:00–18:00 staff polling (3 users × 4 boards × 4 polls/min) |
| Concurrent staff | ≥3 simultaneous dashboard users |
| Availability | 99 % during 08:00–19:00 SAST in pilot; deploys outside those hours. Note Clawsrv is shared: an outage or resource spike from another tenant is an availability risk, bounded by the `mem_limit`s in §17.5 |
| Latency | Origin is in Helsinki (~160–200 ms RTT from Cape Town). Page budgets and their mitigations in §17.6; staff polling unaffected |
| Backup | Daily automated DB **and proofs-bucket** backup to an off-Clawsrv destination, 14-day retention, quarterly restore drill (§15) |
| Images | Dish images served from the public MinIO bucket via Caddy with long `Cache-Control` (`public, max-age=31536000, immutable`, hashed keys); ≤1200 px; WebP. A CDN in front is optional and can be added later without code change |
| Host | Clawsrv is shared; curry-orders runs isolated per §17.5 and must not degrade existing tenants |
| Accessibility | WCAG 2.1 AA contrast; labelled inputs; errors adjacent to fields; keyboard-operable staff screens |
| Browser | Last two versions Chrome, Safari, Samsung Internet; desktop Chrome for staff |
| Locale | en-ZA, ZAR, SAST |
| Observability | Health endpoint `/healthz` (DB + job heartbeat); error tracking (Sentry free tier); uptime ping |

## 17. Selected technical stack (D-13 — fixed for v1)

v1.0 left the stack open. That is the single largest source of schedule risk for a solo developer, so it is now fixed. Rationale: one deployable, one database, no queue broker, no email provider, no Redis, low hosting cost, and a language the developer already ships in.

| Layer | Choice | Notes |
|---|---|---|
| Language / framework | Python 3.12, Django 5.x | Monolith: templates + a thin JSON API for the same views |
| Database | PostgreSQL 16 | `citext`, `pgcrypto` extensions; migrations via Django, schema mirrored in `schema_v1_1.sql` |
| Front-end | Django templates + HTMX + Alpine.js + Tailwind CSS | No SPA. Polling fragments via HTMX. Cart state in Alpine + localStorage |
| Jobs | `manage.py run_scheduler` long-running process (APScheduler in-process) | Jobs in §17.1. Heartbeat written to `job_heartbeats` for `/healthz` |
| Files | Self-hosted MinIO on Clawsrv (S3-compatible): private bucket `curry-proofs`, public-read bucket `curry-media` for dish images, both served through Caddy on a media subdomain | `django-storages` with `AWS_S3_ENDPOINT_URL` pointing at MinIO; signed URLs unchanged. No AWS account. D-28 |
| Hosting | **Clawsrv VPS** — Hetzner, Helsinki; Ubuntu 24.04, 8 vCPU / 15 GB / 150 GB, shared with several existing projects. Docker Compose stack: `web` (gunicorn, published on `127.0.0.1:8102`), `scheduler`, `db` (Postgres 16, internal only), `minio` (internal only). **No `caddy` container** — the host's existing Caddy service owns 80/443 and gains two site blocks | Surveyed 2026-08-28; full inventory, port map and isolation rules in §17.5. Latency and POPIA consequences of the Helsinki location in §17.6. D-28 |
| Auth | Django sessions in `httpOnly` cookies | §4 |
| Error tracking | Sentry (free tier) | |
| SMS (optional) | BulkSMS adapter | Feature-flagged |
| CI | GitHub Actions: lint (ruff), type-check (mypy strict on `core/`), tests (pytest + pytest-django), build image | Merge blocked on red |

Do not introduce a separate mobile app, a second database, a message broker, or a WhatsApp integration.

### 17.1 Background jobs (scheduler process)

| Job | Cadence | Behaviour |
|---|---|---|
| `expire_holds` | every 60 s | `awaiting_eft` with `hold_expires_at < now` → `expire_hold` transition, `actor = system`. Never touches `payment_review`. Batch of ≤200 per run, each in its own transaction |
| `materialise_days` | daily 00:05 SAST and on startup | Ensure `today … today+10` exist with slots |
| `close_out_days` | daily 23:30 SAST | For today: `ready` → `cancelled/no_show`; set `closed_out_at` if null |
| `purge_proofs` | daily 02:00 SAST | Delete proof media where `collected_at + proof_retention_days < now` and `dispute_flag = false`; set `purged_at` |
| `purge_throttle_and_idempotency` | hourly | Delete `throttle_events` > 1 h and `idempotency_keys` > 24 h |
| `heartbeat` | every 30 s | Update `job_heartbeats`; `/healthz` fails if stale > 3 min |
| `backup` | daily 03:00 SAST (host cron, not the scheduler process) | `pg_dump -Fc` + `mc mirror` of the proofs bucket to the off-Clawsrv destination; prune > 14 days; write result to `job_heartbeats` so a silently failing backup is visible on `/healthz` |
| `disk_check` | daily 03:30 SAST | Warn to Sentry when the Clawsrv volume holding `curry_pgdata` or `curry_minio` exceeds 80 % |

### 17.2 Repository layout

```
curry-orders/
  pyproject.toml            # ruff, mypy, pytest config
  docker-compose.yml        # web, scheduler, db, minio  (Clawsrv, D-28; no caddy container)
  deploy/
    backup.sh               # pg_dump + mc mirror to the off-host target (§15)
    minio-bootstrap.sh      # create buckets, service account, public policy on media only
    caddy-site.conf         # site blocks to append to the host's /etc/caddy/Caddyfile (§17.5)
  .env.example              # Appendix D
  schema_v1_1.sql           # reference DDL (Django migrations are the runtime source)
  docs/
    SPEC_v1.1.md            # this document
    RUNBOOK.md              # deploy, backup/restore, rotate secrets, common ops
    DECISIONS.md            # Appendix A, maintained going forward
  src/
    config/                 # settings.py (split base/prod/test), urls.py, asgi/wsgi
    core/                   # domain: models, capacity.py, transitions.py, ordering.py (order numbers), tz.py, phone.py, money.py
    public/                 # customer views, templates, forms, api
    manage/                 # staff views, templates, forms, api
    jobs/                   # scheduler + job functions
    storage/                # media handling, signed URLs, validation
    notifications/          # sms adapter interface + BulkSMS
  tests/
    unit/                   # tz, phone, money, order numbers, transitions
    integration/            # capacity transactions under concurrency (pytest-xdist + real Postgres)
    e2e/                    # Playwright: customer EFT flow, cash flow, staff verify → kitchen → collect
    fixtures/
```

`core/` has no HTTP imports. `capacity.py` exposes `reserve(order_request) -> Order | CapacityError`; `transitions.py` exposes `apply(order, action, actor, payload, expected_status)`. Views are thin.

### 17.3 API contract

All responses JSON, `application/json; charset=utf-8`. Times in ISO 8601 with offset (`2026-09-05T16:15:00+02:00`). Money as integer cents plus a formatted string.

**Public**

| Method | Path | Notes |
|---|---|---|
| GET | `/api/dates` | `orderable_dates` with per-date cash availability |
| GET | `/api/menu?date=` | Dishes with availability and sold-out state for date |
| GET | `/api/dishes/:slug?date=` | Dish with options |
| GET | `/api/availability?date=` | Slots with remaining capacity, cash remaining, dish caps remaining (optimistic) |
| POST | `/api/checkout` | Header `Idempotency-Key`. Body: name, mobile, note, date, slot_id, payment_method, lines[{dish_id, quantity, option_value_ids[], kitchen_note}], accept_policies. 201 `{order_number, public_token, status}`; 422 Appendix C |
| GET | `/api/orders/:token` | Customer view of order; address only in address-bearing statuses |
| POST | `/api/orders/:token/proof` | multipart; 5/hour/token |
| POST | `/api/orders/lookup` | `{order_number, mobile}`; sets cookie; 200 `{redirect}` or 404 generic |
| POST | `/api/orders/:token/reorder` | Returns cart payload |

**Staff (session auth, CSRF)**

| Method | Path | Notes |
|---|---|---|
| GET | `/api/manage/orders?view=inbox\|payments\|kitchen\|collection&date=` | Board payloads (§9.3) |
| GET | `/api/manage/orders/search?q=` | |
| GET | `/api/manage/orders/:id` | Detail + events |
| POST | `/api/manage/orders` | Assisted create; body as checkout + `source`, optional `initial_status`, `reason`, `after_cutoff_reason` |
| POST | `/api/manage/orders/:id/transition` | `{action, expected_status, reason?, payload?}`; 409 `stale_state` / `illegal_transition` |
| POST | `/api/manage/orders/:id/assign` | |
| GET/PATCH | `/api/manage/days/:date` | Daily controls; slot edits nested |
| GET/POST/PATCH/DELETE | `/api/manage/dishes`, `/api/manage/dishes/:id/options` | Menu editor |
| GET/PATCH | `/api/manage/settings` | Owner |
| GET | `/api/manage/reports/:report?from=&to=&format=json\|csv` | |
| GET/POST/PATCH | `/api/manage/staff` | Owner |
| GET | `/healthz` | Public, unauthenticated, no data |

All mutating endpoints are idempotent where practical; transitions are made idempotent by `expected_status`.

### 17.4 Configuration, secrets, deploy

Configuration by environment variables only (Appendix D). Secrets never in the repo; on Clawsrv they live in `/srv/curry-orders/.env`, mode `0600`, owned by the deploy user, and are never inside the git working tree. Deploy: GitHub Actions builds an image on tag `v*` and pushes it to GHCR; Clawsrv pulls and runs `docker compose up -d` after `manage.py migrate`; migrations are backward-compatible within a release. Rollback = redeploy previous tag. `RUNBOOK.md` documents: first deploy, rotate `SECRET_KEY` and MinIO keys, restore DB **and bucket** from backup, change bank details, add staff user, force-expire a hold, what to do if the scheduler heartbeat is stale, and how to restart the stack without disturbing Clawsrv's other services.

### 17.5 Clawsrv — surveyed environment (D-28)

Surveyed 2026-08-28 over `ssh clawusr@100.78.70.2` (Tailscale address; the host is also publicly reachable at its Hetzner IP).

| Property | Actual | Verdict for this build |
|---|---|---|
| Provider / location | Hetzner Online, **Helsinki, Finland** (AS24940), public IP `204.168.249.99` | **Adequate, but see §17.6 — this is not Cape Town.** Drives the latency and POPIA items below |
| CPU | 8 vCPU, AMD EPYC-Rome | Ample; §20.5 load target (20 checkouts/min) is not CPU-bound here |
| RAM | 15 GB total, **7.7 GB already in use, ~7.5 GB available**, **no swap configured** | Enough, but not spare. Budget ≤2.5 GB for the whole curry stack and add 4 GB of swap before first deploy |
| Disk | 150 GB, 62 GB used, **83 GB free** | Enough. Proof budget ~20 GB steady state (100 orders/day × ≤8 MB × 90 days); `disk_check` warns at 80 % of the volume |
| OS | Ubuntu 24.04.4 LTS, kernel 6.8, `unattended-upgrades` and `fail2ban` active, uptime 136 days | Exceeds the minimum |
| Docker | Engine 29.5.2, Compose v5.1.4 | Exceeds the minimum |
| Host timezone | `Etc/UTC` | Correct and expected — §16 requires UTC storage; SAST conversion is in `core/tz.py`, never from the host clock. Do not change the host timezone |
| Monitoring already present | `uptime_kuma` (:3002) and `grafana` (:3030) containers | Reuse for the `/healthz` check instead of a new service — **plus** one external check (see below) |

**Existing tenants (must not be disturbed):** `skulcozm_*` (frontend/backend/redis/postgres), `lekkerswot_*` (frontend/backend/redis/postgres), `oracle_postgres`, `grafana`, `uptime_kuma`, `opensandbox-server`, host `ollama`, and assorted uvicorn/next processes.

**Port map — what is already taken:** 80, 443 (host Caddy), 22, 3000, 3002, 3030, 3579, 5000, 5432, 5433, **5434**, 6379, **6380**, 8000–8004, 8010, 8080, 8088, 8089, 8100, 8101, 8642, 11434, 18789, 2019 (Caddy admin). This project claims **8102** (`web`, loopback-only) and **8103** (MinIO S3 API, loopback-only) — both free against this map.

**Isolation rules, resolved against the survey:**
- Own compose project (`curry-orders`), own Docker network, own named volumes (`curry_pgdata`, `curry_minio`). Nothing shared with existing tenants — in particular **do not reuse** `lekkerswot_postgres` or `oracle_postgres`.
- **The `caddy` container from §17 is dropped.** Clawsrv runs Caddy as a host systemd service that already owns 80/443 and serves `admin.rwc.org.za`. Deployment adds two site blocks to `/etc/caddy/Caddyfile` (site → `127.0.0.1:8102`, media → `127.0.0.1:8103`) followed by `systemctl reload caddy`. The compose stack publishes `web` on `127.0.0.1:8102` and MinIO's S3 API (media bucket and signed proof URLs only, never the admin console) on `127.0.0.1:8103` — both free ports, chosen against the map above.
- Postgres and MinIO are **not published to the host at all** (no `ports:` entry); they are reachable only on the private compose network. The host already has Postgres on 5432/5433/5434 and Redis on 6379/6380, several of them bound to `0.0.0.0` — this stack does not add to that exposure.
- `mem_limit` on every service (`web` 1 GB, `scheduler` 512 MB, `db` 768 MB, `minio` 512 MB) so a curry-orders spike cannot starve Skulcozm or Lekker Swot on a box with no swap.
- Register `/healthz` in the existing Uptime Kuma. Uptime Kuma runs **on Clawsrv**, so it cannot report Clawsrv being down — add one external check (Better Stack / UptimeRobot free tier) against the public URL as well.
- DNS: the owner already controls `rwc.org.za` (evidenced by the existing vhost). Site and media hostnames come from §23; Caddy issues certificates automatically on first request.

**Risks accepted by self-hosting on shared infrastructure:** no managed-database failover, no provider-side snapshot of the object store, host patching and uptime are the owner's responsibility, and a noisy neighbour on this box degrades ordering during service hours. Mitigated only by the §15 backup regime — which is therefore load-bearing and must have a verified restore before go-live (§21 item 2). Hetzner Storage Box is the natural off-host backup destination (same provider, cheap, but **a different failure domain than this VM's disk**).

### 17.6 Consequences of hosting in Helsinki

The v1.0 stack chose AWS `af-south-1` for proximity to Cape Town. Clawsrv is ~9 500 km away, so expect **~160–200 ms RTT** from a Cape Town mobile network. Three consequences, all manageable, none ignorable:

1. **Customer page budget (§11.1).** LCP < 2.5 s on 4G now has ~200 ms of unavoidable round-trip in every request, and TLS/connection setup costs several of them. Mitigations, all cheap and all in scope: HTTP/3 and 0-RTT resumption enabled in Caddy (default), `Cache-Control` and `Early Hints` on menu pages, inlined critical CSS, and dish images served from a CDN in front of the public MinIO bucket (Cloudflare free tier in front of the media hostname) so the heaviest bytes come from a Johannesburg or Cape Town edge. **The budget stays at 2.5 s and is re-measured on a throttled run in milestone 2; if it fails after the mitigations above, putting the whole site behind Cloudflare is the next step, not moving the host.**
2. **Checkout p95 < 800 ms (§20.5).** Server-side work is unaffected; add ~200 ms of transit. Measure the budget **server-side** (time to last byte at the origin) and track the client-observed figure separately, so a network floor is not mistaken for a capacity-engine regression.
3. **Staff boards.** 15 s and 30 s HTMX polling is entirely insensitive to 200 ms. No change.

**POPIA — cross-border processing (new obligation).** Customer names, mobile numbers, order history and **payment proof screenshots** will now be stored in Finland rather than South Africa. POPIA §72 permits this where the recipient jurisdiction has comparable protection; Finland is subject to the GDPR, which satisfies that test. Two things must follow:
- `/policies` must state that data is processed and stored in the EU (Finland) by a service provider on the owner's behalf, and remains subject to POPIA. This is added to the required copy blocks in §11.12.
- The owner is the information officer and should record this transfer basis in writing. Not a blocker; it is one paragraph, and it must not be skipped because it is one paragraph.

## 18. Edge cases (must handle) — with resolutions

| # | Case | Resolution |
|---|---|---|
| 1 | Last slot taken between render and submit | §8.3 lock + recheck; `422 slot_full` with `alternatives` |
| 2 | Dish sells out while in cart | `422 dish_qty_exceeded` / `dish_unavailable` naming the line; cart UI removes/blocks the line |
| 3 | Date change in cart with mixed availability | Re-validate each line; remove unavailable; notice lists removals |
| 4 | Today after 10:00 | Today not in `orderable_dates`; tomorrow first |
| 5 | Closed trading day | Not in `orderable_dates` |
| 6 | Proof uploaded at 29:50, job at 30:00 | `expire_holds` only touches `awaiting_eft`; order is `payment_review` → stays, flagged hold lapsed |
| 7 | Wrong EFT reference on proof | `reject_eft` with reason → `awaiting_eft`; staff may `extend_hold` once (+15) or `cancel` |
| 8 | Double-click checkout | `Idempotency-Key`; second request returns the first order |
| 9 | Two staff verify the same EFT | `expected_status` → second gets `409 stale_state`; first wins |
| 10 | Cash cap reached mid-day | `/api/availability` reports `cash_remaining = 0`; checkout hides cash; server enforces `422 cash_cap` |
| 11 | Advance date + cash via API manipulation | `422 cash_not_allowed` |
| 12 | Dish deactivated/archived with open holds | Snapshots persist; new carts cannot add it; editor warns with count |
| 13 | Price change after cart loaded | Current price charged; response includes `price_changes[]`; UI shows notice before redirect |
| 14 | Uncollected `ready` after 18:15 | Uncollected list; close-out → `no_show`; dish units stay consumed |
| 15 | Customer arrives for expired unpaid order | Not on collection board; staff `reinstate` only if ceilings pass (day open, slot/day/dish/cash capacity), then verify |
| 16 | Slot capacity reduced below occupancy | `422 capacity_below_occupancy`; UI offers close + move |
| 17 | Malicious upload | Magic-byte check, size cap, random storage key, private bucket, `Content-Disposition: attachment` on download, never executed or served inline from origin |
| 18 | Mobile formats `082…`, `+2782…`, `2782…`, `0027…` | `core/phone.py` normalises to E.164; rejects non-mobile prefixes |
| 19 | Window shortened past occupied slots | `422 slot_has_orders`; must close + move first |
| 20 | Assisted after cut-off | Requires `assisted_after_cutoff_enabled` and `after_cutoff_reason`; audited |
| 21 | Customer uploads proof, then staff verifies from bank app before opening proof | Allowed; proof retained |
| 22 | EFT verified after kitchen lock | Allowed; `added_after_lock` flag on kitchen board |
| 23 | Staff taps Collected on wrong ticket | `uncollect` within 10 min, reason |
| 24 | Cash customer collects but has only R 150 of R 185 | `mark_collected` with `cash_amount_received_cents = 15000`; short amount recorded; report shows shortfalls |
| 25 | Owner changes `eft_hold_minutes` while holds are live | Existing `hold_expires_at` unchanged; new orders use the new value |
| 26 | Owner changes window on a day with orders | Only empty future slots regenerated (§10) |
| 27 | Server clock drift / customer device clock wrong | Countdown uses server-provided `hold_expires_at` and server `now` at render, then counts down locally; expiry decisions are server-only |
| 28 | Scheduler process down | `/healthz` fails; uptime ping alerts; holds expire late but nothing over-commits because `expire_holds` only releases; staff **Expire now** is the manual fallback |
| 29 | Same mobile, two orders same day | Allowed; both counted; lookup by number + mobile returns the matching order |
| 30 | Order number sequence exhausted (>9999) | Impossible at cap 100; hard-fail with alert rather than wrap |

## 19. Cancellation and amendment policy (system behaviour)

| Situation | System |
|---|---|
| Customer asks to cancel while `awaiting_eft` / `payment_review` / `cash_request` | Staff `cancel` (reason `customer_request`); release capacity; no refund object |
| Cancel `confirmed_prep` / `cash_due` before kitchen | Staff decision; if cancelled, release capacity; verified EFT refund is manual off-platform; `refund_note = refund_pending` |
| `in_kitchen` or `ready` | **Owner only**; dish units stay consumed; day/slot released (irrelevant after slot) |
| Slot change | Allowed for any non-terminal status except `ready`; same day only; capacity recheck; audit old→new |
| Item change | Staff only, pre-kitchen; recalc total; verified EFT + increase ⇒ `balance_due_cents` shown as **Balance due R x** on collection board; decrease ⇒ `refund_note`. Keep rare |
| Date change | Not supported as an amendment. Cancel and re-create (capacity semantics differ per day) |

## 20. Acceptance criteria and test plan

### 20.1 Customer
- [ ] Complete an EFT order on a phone without a staff chat.
- [ ] Complete a same-day cash order when cash cap remains; cash hidden on advance dates and when cap reached.
- [ ] Cannot select today at or after 10:00:00 SAST.
- [ ] Cannot select a full slot, closed slot or closed day.
- [ ] Cannot order an inactive, archived or sold-out dish.
- [ ] EFT page shows order number, amount, bank details, deadline; countdown matches server time.
- [ ] Proof upload moves status to `payment_review`; proof visible to staff, not to the public.
- [ ] Unpaid EFT without proof expires at 30 minutes and frees day, slot, dish and (n/a) cash capacity.
- [ ] Lookup by order number + mobile (any accepted format) returns the order; 11th attempt in an hour is throttled.
- [ ] Confirmed view shows address; menu, home, cash-request and EFT pages do not; `/orders/*` are `noindex`.
- [ ] Reorder from a collected order seeds a cart at current prices and drops archived dishes with a notice.
- [ ] Copy/Share of the token link works on Android Chrome and iOS Safari.

### 20.2 Staff
- [ ] Two users logged in simultaneously see the same state within 15 s; conflicting actions produce `stale_state`, not a double transition.
- [ ] Verify places the order on the kitchen board and not before.
- [ ] Cash accept places the order on the kitchen board; reject frees capacity including the cash cap.
- [ ] Kitchen summary equals `SUM(quantity)` of lines on kitchen-member orders for the date, grouped by `option_key`.
- [ ] Lock prep list freezes the printed list; later verification shows under Added after lock.
- [ ] Collection board groups by slot; Collected records cash amount; uncollect works within 10 min and fails after.
- [ ] Close out day converts remaining `ready` to `no_show`; dish units remain consumed in the calendar.
- [ ] Daily control can sell out one dish and close one slot without editing the monthly menu.
- [ ] Assisted order occupies the same caps as a website order; after-cut-off assisted blocked unless enabled, and then requires a reason.
- [ ] Every transition, slot change, amendment, hold extension and settings change writes an audit row with actor.
- [ ] Owner-only routes return 403 to a manager.

### 20.3 Rules
- [ ] Day cap 100 enforced including holds, reviews, cash requests and accepted cash.
- [ ] Slot cap 13 enforced; slot capacity cannot be set below occupancy.
- [ ] Cash cap 20 enforced; unaccepted cash requests count.
- [ ] Dish `max_units` enforced; collected and no-show orders still consume units; pre-kitchen cancellations release them.
- [ ] Cut-off, hold minutes, extension, grace, caps, bank details, address editable without deploy; changes audited.
- [ ] Timezone tests around 09:59:59 vs 10:00:00 SAST pass, including when the server runs in UTC and when the test date crosses UTC midnight (e.g. 01:30 SAST = previous day UTC).

### 20.4 Pilot metrics available
- [ ] Orders by slot, expire rate, cash no-shows, website vs assisted share, time-to-proof, time-to-verify.

### 20.5 Test plan

| Layer | Tooling | Must cover |
|---|---|---|
| Unit | pytest | `tz.py` (today/orderable dates at 09:59:59, 10:00:00, 23:59:59, 00:00:01 SAST; UTC server), `phone.py` (all formats, invalid prefixes), `money.py` formatting, order-number formatting, transition matrix (every allowed pair passes, every other pair raises), `option_key` derivation, slot generation for windows 16:00–18:00, 16:00–17:50, 11:00–14:00 |
| Integration (real Postgres) | pytest-django + pytest-xdist | 20 concurrent checkouts against a slot with capacity 13 → exactly 13 succeed; 120 concurrent checkouts on a day with cap 100 → exactly 100; dish `max_units = 5` with concurrent quantity 3 + 3 → one fails; cash cap 20 under concurrency; idempotent double submit; expire job ignores `payment_review`; reinstate fails when day full; capacity reduce below occupancy fails; verify/verify race → one `stale_state`; retention purge respects `dispute_flag` |
| E2E | Playwright (mobile viewport) | EFT: browse → cart → checkout → EFT page → upload → staff verify → kitchen → ready → collected. Cash: checkout before 10:00 → staff accept → kitchen → collected with cash amount. Expiry: checkout → advance clock → expired → reinstate → verify. Lookup and throttle. Staff role restrictions. Print stylesheet renders |
| Load | k6 (single script) | 20 checkouts/min for 10 min against Clawsrv; p95 checkout < 800 ms **measured server-side at the origin** (client-observed figure tracked separately, ~200 ms higher from ZA — §17.6); no over-commit; existing Clawsrv tenants unaffected during the run (watch Grafana) |
| Security | Manual checklist + ZAP baseline scan | Token entropy, `noindex`, signed URL expiry, upload validation, CSRF, headers, lockout |

CI gate: unit + integration green, ruff clean, mypy clean on `core/`. E2E and load run before each pilot deploy.

## 21. Pilot configuration, seed and go-live checklist

**Seed (`manage.py seed_pilot`):** settings with §3 defaults and owner-supplied values from §23; 1 owner + 2 manager users with temporary passwords and `must_change_password`; monthly dish catalogue from the owner's list; trading days today+10 open with default slots. **No fake customer orders in production.** A separate `seed_dev` command creates placeholder dishes and sample orders for local development only.

**Go-live checklist**
1. Owner inputs in §23 received and entered.
2. Backup taken and a restore verified on a scratch database **and a scratch MinIO bucket** (a signed proof URL must resolve after the restore); backup destination confirmed to be off Clawsrv.
3. `/healthz` green; registered in Clawsrv's existing Uptime Kuma **and** in one external monitor off the host; Sentry alerts routed to the developer and owner.
3a. Clawsrv prepared: 4 GB swap added, `mem_limit`s in place, host Caddy site blocks added and reloaded without interrupting `admin.rwc.org.za`, and every existing tenant (`skulcozm_*`, `lekkerswot_*`, `oracle_postgres`, `grafana`, `uptime_kuma`) confirmed still healthy after the first deploy.
4. Bank details verified by the owner on the live EFT page using a R 1 test order, then that order cancelled.
5. Both managers complete one assisted order, one verify, one cash accept, one collect on their own phones.
6. Print stylesheet checked on the kitchen printer/phone.
7. `robots.txt` and `noindex` verified with a crawler check.
8. Canned WhatsApp reply set in WhatsApp Business quick replies.
9. Pilot start date and the two-week review date in the calendar.

**Pilot:** two operating weeks, then review slot balance, handover time, EFT-before-expiry rate, cash no-shows, cap pressure, website share, failed checkouts (from `throttle_events` and 422 counts). Changing caps is a settings change, not a code change.

## 22. Implementation sequence with definition of done

Build in this order so the pilot can run on a subset of customers. Each milestone ends with its tests green.

| # | Milestone | Done when |
|---|---|---|
| 1 | Schema, settings, staff auth, `tz.py`, `phone.py`, `money.py`, trading-day + slot materialisation, scheduler skeleton with heartbeat | Unit tests for tz/phone/money/slot generation pass; `/healthz` green; owner can log in and edit settings |
| 2 | Menu, dish, availability APIs and public pages | Menu renders per date with sold-out states; LCP budget met on a throttled run |
| 3 | Cart, checkout, capacity transaction, order numbers, idempotency | Concurrency integration tests pass; order created with correct number and status |
| 4 | EFT page, proof upload, `expire_holds` job | E2E EFT flow to `payment_review`; expiry test passes |
| 5 | Transitions engine, audit, EFT queue, `stale_state` handling | Full transition matrix tests; verify race test |
| 6 | Kitchen board (aggregates, lock, print) and collection board (collect, cash amount, uncollect, close out) | Staff acceptance items for both boards |
| 7 | Cash path and cash cap | Cash E2E; cash cap concurrency test |
| 8 | Daily controls and menu editor | Daily-control acceptance items; archive-with-orders warning |
| 9 | Assisted create, calendar, lookup, reorder, inbox flags | Assisted after-cut-off gating; lookup throttle; reorder notice |
| 10 | Help/policies, reports + CSV, retention purge, backups, runbook, hardening, load and security passes | Go-live checklist items 2–7 satisfiable |

Do not start with visual polish on the marketing home page. The capacity transaction and payment queue are the product.

## 23. Owner inputs (blocking for pilot, not for development)

| Input | Needed for | Status |
|---|---|---|
| Final dish list: name, price, portion, options, allergen text, dietary tags, photos | Milestone 2 real content; pilot | Outstanding |
| Bank details (bank, account name, number, branch code, type) | EFT page; go-live item 4 | Outstanding |
| Collection address line and arrival instructions (gate, parking, no hooting, what to say on arrival) | Confirmed pages, collection ticket | Outstanding |
| Allergen / home-kitchen disclaimer wording | `/policies`, dish pages | Outstanding |
| Support WhatsApp number | Header, help, EFT page | Outstanding |
| Logo, brand colours | Theme | Outstanding (placeholder theme in development) |
| Names and emails of the two managers + owner | Seed | Outstanding |
| ~~Clawsrv facts (D-28)~~ | §17.5 sizing and isolation | **Resolved 2026-08-28 by direct survey — see §17.5** |
| **Off-Clawsrv backup destination** and its credentials (Hetzner Storage Box recommended — same provider, different failure domain) | §15 backups; go-live item 2 | Outstanding |
| **Site and media hostnames** under `rwc.org.za` (or another domain), e.g. `orders.` and `media.` | Caddy site blocks; MinIO public URLs | Outstanding |
| Confirmation that hosting customer data in the EU is acceptable, and the one-paragraph POPIA cross-border disclosure wording | §11.12, §15, §17.6 | Outstanding — owner to confirm |
| VAT registration status (and number if registered) | Receipt wording | Outstanding — default not registered |
| **Decision on cash ordering window (D-06):** keep cash orderable only 00:00–10:00 same day, **or** allow cash for tomorrow's collection (drop `cash_same_day_only`). Recommendation: keep v1.0 rule for the pilot and review with the no-show data | Checkout cash availability | Owner to confirm |
| Confirmation that `no_show` on a verified EFT order carries no automatic refund (owner exception only) | §19 | Owner to confirm |

Development starts now with placeholder content; pilot cannot start until every "Outstanding" row is filled.

## 24. Design intent (do not dilute)

1. One order book.
2. Money rule before kitchen, except accepted same-day cash, which is a conscious, capped risk.
3. Slots exist to protect the 16:00–18:00 door of a private home, not as decoration.
4. Monthly menu and daily trading controls are different screens.
5. WhatsApp may send people to a dish URL. It may not store the day's truth.

If a proposed feature weakens any of those five, it does not belong in v1.

---

## Appendix A — Decision log

| ID | Decision | Rationale |
|---|---|---|
| D-01 | No `new_request` status; checkout writes the first real status inside the reservation transaction | A transient state would need recovery logic for no benefit; a failed transaction leaves nothing behind |
| D-02 | One `cancelled` status with `cancellation_reason` enum (`customer_request, staff, cash_rejected, payment_rejected, no_show, day_closed, duplicate, owner_exception, other`) | Simpler matrix; reason carries the semantics; reports group by reason |
| D-03 | `orders.dish_units_consumed`, set on `start_kitchen`, never cleared; dish-unit ceiling counts occupying set ∪ consumed | Resolves the §8.1/§19 contradiction without a parallel ledger |
| D-04 | Order sequence from `trading_days.next_order_seq` under the existing `FOR UPDATE` lock | Zero extra locking; per-collection-date numbering as v1.0 intended |
| D-05 | Horizon = today (if open and before cut-off) + next 7 days (up to 8 dates) | Matches the literal v1.0 wording "today through +7" |
| D-06 | Cash same-day only, therefore public cash checkout only 00:00–10:00 SAST; flagged to owner | Preserves the v1.0 confirmed model; the alternative is a settings toggle, not code |
| D-07 | No email anywhere in v1; token URL + Copy/Share + lookup; SMS optional adapter | Avoids an email provider, deliverability work and extra POPIA data |
| D-08 | Hold extension is mandatory: once, +15 min, staff-only, audited | Wrong-reference proofs are common; without extension staff would cancel paying customers |
| D-09 | `payment_review` never auto-expires; hold-lapsed and SLA-breached flags instead | A submitted proof is evidence of intent; silent drops create disputes |
| D-10 | Reinstate keeps the same order number and re-runs all ceilings | Customer already has the reference; capacity must still be honest |
| D-11 | `assisted_after_cutoff_enabled` owner setting; when on, any staff with mandatory reason | Clear ownership of the risk; default deny preserved |
| D-12 | Staff password reset via owner-set temporary password + forced change | No email provider; three users; owner is always reachable |
| D-13 | Django 5 + Postgres 16 + HTMX/Alpine/Tailwind, in-process APScheduler, single deployable | One deployable, developer's primary language, no broker/Redis. *(Hosting clause superseded by D-28.)* |
| D-28 | Host on the existing **Clawsrv VPS** instead of a new AWS VM; object storage is self-hosted MinIO in the same compose stack instead of S3 `af-south-1` | Uses infrastructure already paid for and administered; removes the AWS account, IAM and egress entirely; `django-storages` speaks the same S3 API so only `S3_ENDPOINT` changes in code. Trade-offs accepted: no managed-DB failover, no provider-side object snapshots, host patching is the owner's job, and Cape Town latency depends on where Clawsrv actually sits — hence the mandatory off-host backup regime (§15), the isolation rules and the re-measured LCP budget (§17.5) |
| D-14 | `customers.mobile_e164` unique; upsert; order-level snapshots | Enables reorder history later without a login |
| D-15 | Slot change allowed up to `in_kitchen`; never from `ready`; same day only | Kitchen batches by day; a date change is a new capacity event |
| D-16 | Close out day = explicit staff action after grace, with a nightly safety job | Home kitchen closes the door at a known time; no order may remain `ready` forever |
| D-17 | Kitchen lock = `trading_days.kitchen_locked_at`; later confirmations flagged, not blocked | Cooking in batches must not stop the payment queue |
| D-18 | Verify from `awaiting_eft` without proof allowed with reason | Staff see funds in the bank app before customers upload screenshots |
| D-19 | `vat_registered` default false; receipt says "Not a tax invoice" | Home business is below the VAT threshold until proven otherwise |
| D-20 | Bounded corrections: `revert_ready`, `uncollect` (≤10 min), both audited | Mis-taps on a phone at the gate are certain; unbounded undo would corrupt reports |
| D-21 | Rate limits: checkout 5/min/IP, proof 5/h/token, lookup 10/h/IP and 10/h/order number, login 5 failures → 15 min lock | Cheap abuse resistance without CAPTCHA |
| D-22 | Idempotency keys stored 24 h with request hash | Double-taps on slow mobile networks are the norm |
| D-23 | Address never in metadata, sitemaps, OG tags, or on any page before confirmation; no map; no exterior photo | Private residence |
| D-24 | Settings is a single typed row with an events table | Type safety and diff-able audit beat a key-value bag for ~40 keys |
| D-25 | Dishes are archived, never hard-deleted | Permalinks are marketing assets; snapshots reference them |
| D-26 | Staff app served from the same origin as the public site under `/manage` | Removes CORS entirely |
| D-27 | Postgres-backed throttling, no Redis | Three staff and 100 orders/day do not justify another service |

## Appendix B — Settings reference

| Key | Type | Default | Constraint |
|---|---|---|---|
| `public_site_name` | text | — | required |
| `collection_address_line` | text | — | required for pilot |
| `collection_instructions` | text | — | required for pilot |
| `bank_name`, `account_name`, `account_number`, `branch_code`, `account_type` | text | — | required for pilot; `account_number` digits only |
| `default_window_start` / `default_window_end` | time | 16:00 / 18:00 | start < end |
| `slot_minutes` | int | 15 | 5–60 |
| `default_slot_capacity` | int | 13 | ≥1 |
| `default_daily_order_cap` | int | 100 | ≥1 |
| `same_day_cutoff` | time | 10:00 | < `default_window_start` |
| `preorder_days` | int | 7 | 0–14 |
| `eft_hold_minutes` | int | 30 | 5–120 |
| `max_hold_extensions` | int | 1 | 0–3 |
| `hold_extension_minutes` | int | 15 | 5–60 |
| `payment_review_sla_minutes` | int | 15 | 5–120 |
| `cash_enabled` | bool | true | |
| `cash_same_day_only` | bool | true | |
| `cash_daily_cap` | int | 20 | 0–`default_daily_order_cap` |
| `collection_grace_minutes` | int | 15 | 0–60 |
| `assisted_after_cutoff_enabled` | bool | false | |
| `support_whatsapp_e164` | text | — | E.164 |
| `allergen_disclaimer`, `home_kitchen_notice` | text | — | required for pilot |
| `vat_registered` | bool | false | |
| `vat_number` | text | null | required if `vat_registered` |
| `proof_retention_days` | int | 90 | 30–365 |
| `order_retention_months` | int | 18 | 6–60 |
| `sms_enabled` | bool | false | |
| `sms_ready_template` | text | see §13 | placeholders validated |

## Appendix C — Error contract

HTTP 422 body for capacity/rule failures:

```json
{
  "error": "slot_full",
  "message": "That collection time is now full.",
  "line_index": null,
  "alternatives": {
    "slots": [{"slot_id": 812, "label": "17:00-17:15", "remaining": 4}],
    "next_open_date": "2026-09-06"
  }
}
```

| Code | HTTP | When |
|---|---|---|
| `day_closed`, `outside_horizon`, `cutoff_passed`, `slot_closed`, `day_full`, `slot_full`, `dish_unavailable`, `dish_qty_exceeded` (with `line_index`), `cash_cap`, `cash_not_allowed` | 422 | §8.2 |
| `capacity_below_occupancy`, `slot_has_orders` | 422 | Daily controls |
| `validation_error` (with `fields{}`) | 400 | Field validation |
| `idempotency_conflict` | 409 | Same key, different payload |
| `stale_state` (with `current_status`) | 409 | `expected_status` mismatch |
| `illegal_transition` | 409 | Not in §9.1 |
| `after_cutoff_disabled`, `reason_required`, `owner_only` | 403 | Permission/policy |
| `throttled` (with `retry_after_seconds`) | 429 | D-21 |
| `upload_invalid` (with `detail`: type/size/corrupt) | 400 | Proof upload |

## Appendix D — Environment variables

| Variable | Purpose |
|---|---|
| `DJANGO_SECRET_KEY` | Sessions/CSRF |
| `WEB_BIND_PORT`, `MINIO_API_BIND_PORT` | Host loopback ports for `web` (`8102`) and MinIO's S3 API (`8103`) on Clawsrv (§17.5 port map) |
| `DJANGO_ENV` | `dev` / `prod` / `test` |
| `DATABASE_URL` | Postgres DSN |
| `TIME_ZONE` | Fixed `Africa/Johannesburg` (also asserted at startup) |
| `SITE_URL` | Canonical origin, e.g. `https://orders.example.co.za` |
| `S3_ENDPOINT` | MinIO internal endpoint, e.g. `http://minio:9000` |
| `S3_PUBLIC_ENDPOINT` | Externally reachable media host used to build public/signed URLs, e.g. `https://media.orders.example.co.za` |
| `S3_REGION`, `S3_ACCESS_KEY`, `S3_SECRET_KEY` | MinIO region label (`us-east-1` is fine) and credentials; keys are MinIO service-account keys, not root |
| `S3_BUCKET_PROOFS` (private), `S3_BUCKET_PUBLIC` (dish images), `CDN_BASE_URL` (optional) | Media |
| `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | MinIO container bootstrap only; rotated after service accounts are created |
| `BACKUP_TARGET`, `BACKUP_ENCRYPTION_KEY` | Off-Clawsrv rclone/B2 destination and at-rest encryption (§15) |
| `SENTRY_DSN` | Error tracking (optional) |
| `SMS_PROVIDER`, `SMS_API_KEY`, `SMS_SENDER_ID` | Only if `sms_enabled` |
| `GUNICORN_WORKERS` | Default 3 |
| `LOG_LEVEL` | Default `INFO` |
